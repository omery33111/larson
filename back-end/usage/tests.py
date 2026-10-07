from datetime import timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework import status

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone

import json

from chat.context import (EFFORT, NEAR_THE_CEILING_EFFORT, build_messages,
                          build_system, effort_for)
from chat.models import Conversation, Message as ChatMessage
from chat.tests import FakeUsage, fake_client, make_trades, read_events
from trades.models import Trade

from . import budget
from .models import TokenSpend


# Small enough to reach in a test, and the shape of the real one.
# `AI_BURST_UNITS = 0` lifts the day entirely, so these keep testing the one ceiling they
# were written for. The day has a test class of its own.
SMALL = dict(AI_USER_UNITS = 20000, AI_USER_WINDOW_HOURS = 24, AI_BURST_UNITS = 0,
             AI_GLOBAL_DAILY_UNITS = 0, AI_WARN_AT = 0.90)



# ------------------------- THE UNIT TESTS START ------------------------- #

class UnitTests(APITestCase):

    def test_output_counts_five_times_input(self):
        # It is priced at five times input on this model, so a budget that added the two
        # together would let a token of generated text cost the same slice of somebody's day
        # as a token of prompt - when it is five times the money.
        self.assertEqual(budget.units(1000, 0), 1000)
        self.assertEqual(budget.units(0, 1000), 5000)
        self.assertEqual(budget.units(1000, 200), 2000)


    def test_a_missing_usage_block_records_a_zero_rather_than_nothing(self):
        user = User.objects.create_user(username = "omer", password = "Kestrel-Vault-72")

        row = budget.record(user, "chat", object())

        # A call that vanished from the ledger because its shape was unfamiliar is worse than
        # one recorded as free: the row is what says a call happened at all.
        self.assertEqual(row.input_tokens, 0)
        self.assertEqual(TokenSpend.objects.filter(user = user).count(), 1)

# ------------------------- THE UNIT TESTS END ------------------------- #

# ------------------------- THE CACHE TESTS START ------------------------- #

class CacheTests(APITestCase):
    """
    **Caching fails silently, which is the only reason this class exists.**

    When it breaks, nothing errors: requests keep succeeding and the bill is simply higher.
    The usual shape is not a bad first implementation but a regression months later - somebody
    interpolates a timestamp into the persona, or makes the resume serialisation
    non-deterministic, and every read quietly becomes a write.

    The only ground truth is the prompt bytes and the `usage` fields, so both are pinned here.
    """

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Kestrel-Vault-72")
        make_trades(self.user)


    # ------------- WHERE THE BREAKPOINTS ARE:
    def test_the_system_prefix_carries_one_marker_on_its_last_block(self):
        blocks = build_system(self.user)

        # On the last one, which caches everything before it. `tools` render ahead of
        # `system`, so this marker would cover those too if the product ever had any.
        self.assertNotIn("cache_control", blocks[0])
        self.assertIn("cache_control", blocks[-1])


    def test_a_trader_with_no_trades_is_still_cached(self):
        empty = User.objects.create_user(username = "new", password = "Kestrel-Vault-72")

        # The persona alone is most of the prefix and never changes; leaving it uncached
        # would charge every new trader full price for the same bytes.
        self.assertIn("cache_control", build_system(empty)[-1])


    def test_the_thread_carries_a_marker_on_its_last_turn(self):
        row = Conversation.objects.create(user = self.user)
        ChatMessage.objects.create(conversation = row, role = "user", content = "שאלה")
        ChatMessage.objects.create(conversation = row, role = "assistant", content = "תשובה")
        ChatMessage.objects.create(conversation = row, role = "user", content = "והמשך")

        messages = build_messages(row)

        # This is what makes a follow-up cheap: the entry it writes is what the NEXT request
        # reads, so each turn pays the write premium only on what it added.
        self.assertIsInstance(messages[-1]["content"], list)
        self.assertIn("cache_control", messages[-1]["content"][0])

        # Everything earlier stays a plain string - a marker there would spend a breakpoint
        # on a position already covered by the one above it.
        for message in messages[:-1]:
            self.assertIsInstance(message["content"], str)


    def test_it_stays_inside_the_four_breakpoint_limit(self):
        row = Conversation.objects.create(user = self.user)
        for i in range(12):
            ChatMessage.objects.create(conversation = row, role = "user", content = "שאלה")
            ChatMessage.objects.create(conversation = row, role = "assistant", content = "תשובה")

        markers = sum("cache_control" in block for block in build_system(self.user))
        for message in build_messages(row):
            if isinstance(message["content"], list):
                markers += sum("cache_control" in block for block in message["content"])

        # The API rejects a fifth. Two is the design; this catches a third arriving by
        # accident when the prompt grows a section.
        self.assertLessEqual(markers, 4)
        self.assertEqual(markers, 2)


    # ------------- AND THAT THE PREFIX ACTUALLY REPEATS:
    def test_the_prefix_is_byte_identical_between_two_requests(self):
        first = json.dumps(build_system(self.user), ensure_ascii = False, sort_keys = True)
        second = json.dumps(build_system(self.user), ensure_ascii = False, sort_keys = True)

        # **The test that catches the regression this class is about.** A prefix that differs
        # by one byte between two requests caches nothing, and the only symptom is a larger
        # bill. A `datetime.now()` in the persona would fail here and nowhere else.
        self.assertEqual(first, second)


    def test_the_prefix_changes_when_the_resume_does(self):
        before = json.dumps(build_system(self.user), ensure_ascii = False, sort_keys = True)

        Trade.objects.create(user = self.user, executed_at = "2026-08-20T10:00:00Z",
                             symbol = "MNQU6", instrument = "NQ", pnl = 75.0,
                             outcome = "win", dedup_hash = "fresh")

        after = json.dumps(build_system(self.user), ensure_ascii = False, sort_keys = True)

        # It must change here, or the model would answer from a stale resume - the one thing
        # caching may never be allowed to buy.
        self.assertNotEqual(before, after)


    def test_two_traders_do_not_share_a_prefix(self):
        other = User.objects.create_user(username = "someone", password = "Kestrel-Vault-72")

        # Not a caching failure - it is the point. The resume sits in the prefix, so each
        # trader necessarily has an entry of his own.
        self.assertNotEqual(build_system(self.user), build_system(other))


    # ------------- AND THAT THE METER SEES ALL FOUR PRICES:
    def test_a_cache_read_is_a_tenth_of_ordinary_input(self):
        self.assertEqual(budget.units(0, 0, cache_read_tokens = 1000), 100)


    def test_a_cache_write_is_twice_input_because_the_prefix_lasts_an_hour(self):
        """
        **The one number that breaks the budget silently if it drifts.** `chat/context.py`
        asks for an hour-long prefix, which Anthropic bills at twice input; the five-minute
        prefix it replaced was 1.25. Nothing errors if this is left behind - the meter just
        under-counts every write by 60%, the trader walks past the ceiling that is supposed
        to guarantee a margin, and the first anyone hears of it is the invoice.
        """
        self.assertEqual(budget.units(0, 0, cache_write_tokens = 1000), 2000)

    def test_the_weight_matches_the_ttl_that_is_actually_requested(self):
        """Locks the two together, so changing one without the other fails here and not
        in production three weeks later."""
        from chat.context import CACHE

        self.assertEqual(CACHE.get("ttl"), "1h")
        self.assertEqual(budget.CACHE_WRITE_WEIGHT, 2.0)


    def test_the_ledger_stores_what_the_api_reported(self):
        usage = FakeUsage(input_tokens = 40, output_tokens = 600,
                          cache_creation_input_tokens = 0, cache_read_input_tokens = 4200)

        row = budget.record(self.user, "chat", usage)

        self.assertEqual(row.cache_read_tokens, 4200)
        self.assertEqual(row.input_tokens, 40)


    def test_a_cached_call_costs_a_fraction_of_an_uncached_one(self):
        # The same answer, cold and warm. `input_tokens` is only the uncached remainder,
        # which is why the first figure does not simply reappear in the second.
        cold = budget.units(4200, 600)
        warm = budget.units(40, 600, cache_read_tokens = 4200)

        self.assertLess(warm, cold)
        self.assertLess(warm / cold, 0.6)


    def test_the_meter_counts_cached_tokens_at_all(self):
        TokenSpend.objects.create(user = self.user, kind = "chat",
                                  input_tokens = 0, output_tokens = 0,
                                  cache_read_tokens = 10000)

        # A ledger reading only `input_tokens` would call this call free, and a budget built
        # on it would be wrong by most of the traffic the moment caching was switched on.
        self.assertEqual(budget.spent(self.user), 1000)

# ------------------------- THE CACHE TESTS END ------------------------- #




# ------------------------- THE WINDOW TESTS START ------------------------- #

@override_settings(**SMALL)
class WindowTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Kestrel-Vault-72")


    def spend(self, input_tokens, output_tokens, hours_ago = 0):
        row = TokenSpend.objects.create(user = self.user, kind = "chat",
                                        input_tokens = input_tokens,
                                        output_tokens = output_tokens)
        if hours_ago:
            TokenSpend.objects.filter(pk = row.pk).update(
                created_at = timezone.now() - timedelta(hours = hours_ago))
        return row


    def test_it_adds_up_what_was_spent(self):
        self.spend(1000, 200)
        self.spend(1000, 200)

        self.assertEqual(budget.spent(self.user), 4000)


    def test_what_fell_out_of_the_window_no_longer_counts(self):
        self.spend(1000, 200, hours_ago = 25)
        self.spend(1000, 200)

        self.assertEqual(budget.spent(self.user), 2000)


    def test_one_trader_does_not_spend_another_traders_budget(self):
        other = User.objects.create_user(username = "someone", password = "Kestrel-Vault-72")
        TokenSpend.objects.create(user = other, kind = "chat",
                                  input_tokens = 100000, output_tokens = 100000)

        self.assertEqual(budget.spent(self.user), 0)
        self.assertTrue(budget.has_room(self.user))


    def test_the_room_runs_out(self):
        self.assertTrue(budget.has_room(self.user))

        self.spend(20000, 0)

        self.assertFalse(budget.has_room(self.user))


    def test_it_comes_back_as_the_window_rolls(self):
        self.spend(20000, 0, hours_ago = 24)

        # **This is the reason the window rolls rather than resetting at midnight.** A window
        # with an edge can be spent twice across it - all of one day at 23:59 and all of the
        # next at 00:01 - which is the exact shape a runaway loop produces.
        self.assertTrue(budget.has_room(self.user))


    def test_it_reports_when_the_next_piece_frees_up(self):
        self.spend(20000, 0, hours_ago = 20)

        when = budget.renews_at(self.user)
        hours = (when - timezone.now()).total_seconds() / 3600

        self.assertAlmostEqual(hours, 4, delta = 0.1)


    def test_the_message_says_when(self):
        # A limit with no horizon reads as a fault; the same limit with a time on it reads as
        # a queue.
        self.spend(20000, 0, hours_ago = 23.5)
        self.assertIn("דקות", budget.exhausted_message(self.user))

        TokenSpend.objects.all().delete()
        self.spend(20000, 0, hours_ago = 23)
        self.assertIn("כשעה", budget.exhausted_message(self.user))

        TokenSpend.objects.all().delete()
        self.spend(20000, 0, hours_ago = 20)
        self.assertIn("כ-4 שעות", budget.exhausted_message(self.user))


    # ------------- WHAT THE CLIENT IS TOLD:
    def test_the_state_is_a_percentage_and_not_a_token_count(self):
        self.spend(10000, 0)
        state = budget.state(self.user)

        self.assertEqual(state["used_percent"], 50)
        self.assertFalse(state["exhausted"])
        self.assertFalse(state["should_warn"])


    def test_it_stays_quiet_through_an_ordinary_heavy_day(self):
        self.spend(16000, 0)          # 80% of the budget

        # **Nothing is said here, and that is the design.** Somebody who finishes the day at
        # four fifths never needed to know a limit existed - and a meter he can see is one he
        # starts budgeting around, which is the exact behaviour this product cannot afford.
        self.assertFalse(budget.state(self.user)["should_warn"])


    def test_it_speaks_up_only_when_the_wall_is_close(self):
        self.spend(19000, 0)          # 95%

        # The notice exists so the wall is not a surprise, not so he can ration around it.
        self.assertTrue(budget.state(self.user)["should_warn"])


    def test_it_never_reports_past_full(self):
        self.spend(999999, 0)
        state = budget.state(self.user)

        self.assertEqual(state["used_percent"], 100)
        self.assertEqual(state["remaining_percent"], 0)

# ------------------------- THE WINDOW TESTS END ------------------------- #


# ------------------------- THE CEILING ON EVERYONE TESTS START ------------------------- #

@override_settings(AI_USER_UNITS = 20000, AI_USER_WINDOW_HOURS = 24, AI_BURST_UNITS = 0,
                   AI_GLOBAL_DAILY_UNITS = 30000)
class SiteCeilingTests(APITestCase):
    """
    The limit that makes the worst case a number somebody chose.

    **A per-trader budget does not bound anything on its own.** One dollar a day multiplied by
    however many people sign up tomorrow is a rate, not a ceiling - and being able to say the
    worst case out loud is most of the reason to have a budget at all.
    """

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Kestrel-Vault-72")
        self.other = User.objects.create_user(username = "someone", password = "Kestrel-Vault-72")


    def test_it_adds_up_across_traders(self):
        TokenSpend.objects.create(user = self.user, kind = "chat", input_tokens = 10000)
        TokenSpend.objects.create(user = self.other, kind = "chat", input_tokens = 10000)

        self.assertEqual(budget.site_spent(), 20000)


    def test_a_trader_well_inside_his_own_budget_is_still_stopped(self):
        # Two traders, each at half of their own allowance, together over the site's.
        TokenSpend.objects.create(user = self.other, kind = "chat", input_tokens = 19000)
        TokenSpend.objects.create(user = self.user, kind = "chat", input_tokens = 12000)

        self.assertTrue(budget.spent(self.user) < budget.allowance())
        self.assertFalse(budget.has_room(self.user))


    def test_the_message_does_not_blame_him_for_it(self):
        TokenSpend.objects.create(user = self.other, kind = "chat", input_tokens = 31000)

        message = budget.exhausted_message(self.user)

        # It is not this trader's doing and must not be described as his.
        self.assertIn("לא קשור למכסה שלך", message)


    @override_settings(AI_GLOBAL_DAILY_UNITS = 0)
    def test_zero_lifts_it(self):
        TokenSpend.objects.create(user = self.other, kind = "chat", input_tokens = 9999999)

        self.assertTrue(budget.has_room(self.user))

# ------------------------- THE CEILING ON EVERYONE TESTS END ------------------------- #




# ------------------------- THE METER ON A REAL ANSWER TESTS START ---------- #

class MeteredAnswerTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Kestrel-Vault-72")
        self.client.force_authenticate(user = self.user)
        self.conversation = Conversation.objects.create(user = self.user)
        make_trades(self.user)


    def ask(self, usage = None):
        with self.settings(ANTHROPIC_API_KEY = "test-key"):
            with patch("anthropic.Anthropic", fake_client(("שלום",), usage = usage)):
                response = self.client.post(
                    f"/chat/conversations/{self.conversation.id}/stream/",
                    {"message": "מה אחוז ההצלחה שלי?"})
                return response, read_events(response)


    def test_an_answer_is_billed_from_the_api_figure(self):
        self.ask(usage = FakeUsage(input_tokens = 4200, output_tokens = 600))

        row = TokenSpend.objects.get(user = self.user)

        # Not an estimate from the prompt's length: the API's own number is the only one that
        # counts the thinking, which is billed as output and can be several times the answer
        # the trader actually reads.
        self.assertEqual(row.input_tokens, 4200)
        self.assertEqual(row.output_tokens, 600)
        self.assertEqual(row.kind, "chat")


    def test_the_last_event_carries_the_fresh_state(self):
        _, events = self.ask()

        # It rides the `done` event so the meter is current without the client having to ask
        # after every answer - a meter that polls is a meter that costs something to watch.
        self.assertEqual(events[-1]["type"], "done")
        self.assertIn("usage", events[-1])
        self.assertIn("used_percent", events[-1]["usage"])


    @override_settings(**SMALL)
    def test_a_spent_budget_stops_the_next_answer_before_it_is_bought(self):
        TokenSpend.objects.create(user = self.user, kind = "chat",
                                  input_tokens = 20000, output_tokens = 0)

        _, events = self.ask()

        self.assertEqual(events[0]["type"], "error")
        self.assertIn("מכסת השימוש", events[0]["error"])


    @override_settings(**SMALL)
    def test_nothing_is_bought_when_the_budget_is_spent(self):
        TokenSpend.objects.create(user = self.user, kind = "chat",
                                  input_tokens = 20000, output_tokens = 0)
        before = TokenSpend.objects.count()

        self.ask()

        # The whole point is that the call never happens - a check after the fact would have
        # already paid for the answer it is refusing.
        self.assertEqual(TokenSpend.objects.count(), before)


    @override_settings(**SMALL)
    def test_the_refusal_carries_the_state_with_it(self):
        TokenSpend.objects.create(user = self.user, kind = "chat",
                                  input_tokens = 20000, output_tokens = 0)

        _, events = self.ask()

        self.assertTrue(events[0]["usage"]["exhausted"])
        self.assertIsNotNone(events[0]["usage"]["renews_at"])

# ------------------------- THE METER ON A REAL ANSWER TESTS END ------------ #



# ------------------------- THE ENDPOINT TESTS START ------------------------- #

class StateEndpointTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Kestrel-Vault-72")


    def test_it_requires_authentication(self):
        self.assertEqual(self.client.get("/usage/").status_code, status.HTTP_401_UNAUTHORIZED)


    @override_settings(**SMALL)
    def test_it_reports_where_the_trader_stands(self):
        self.client.force_authenticate(user = self.user)
        TokenSpend.objects.create(user = self.user, kind = "chat",
                                  input_tokens = 5000, output_tokens = 0)

        body = self.client.get("/usage/").data

        self.assertEqual(body["used_percent"], 25)
        self.assertEqual(body["window_hours"], 24)


    def test_a_trader_who_has_used_nothing_gets_a_clean_answer(self):
        self.client.force_authenticate(user = self.user)
        body = self.client.get("/usage/").data

        self.assertEqual(body["used_percent"], 0)
        self.assertIsNone(body["renews_at"])
        self.assertFalse(body["should_warn"])

# ------------------------- THE ENDPOINT TESTS END ------------------------- #

# ------------------------- THE BETA REPORT TESTS START ------------------------- #

class ReportTests(APITestCase):
    """
    The command that turns the ledger into the figure worth looking at.

    **It exists so the limits can be set from evidence rather than from arithmetic.** The
    defaults came from one measured prompt on one synthetic resume; a month of real people is
    a better number, and this is what produces it.
    """

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Kestrel-Vault-72")
        self.other = User.objects.create_user(username = "someone", password = "Kestrel-Vault-72")


    def run_report(self, **options):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("usage_report", stdout = out, **options)
        return out.getvalue()


    def test_an_empty_ledger_says_so_rather_than_dividing_by_zero(self):
        self.assertIn("Nothing recorded", self.run_report())


    def test_it_reports_each_trader_and_the_total(self):
        TokenSpend.objects.create(user = self.user, kind = "chat",
                                  input_tokens = 100000, output_tokens = 20000)
        TokenSpend.objects.create(user = self.other, kind = "mentor",
                                  input_tokens = 50000, output_tokens = 10000)

        report = self.run_report()

        self.assertIn("omer", report)
        self.assertIn("someone", report)
        self.assertIn("2 traders", report)


    def test_the_money_is_arithmetic_from_the_prices_in_settings(self):
        # 1,000,000 input at $5 and 1,000,000 output at $25 is $30, and the report has to say
        # so - a cost figure that cannot be checked by hand is one nobody can act on.
        TokenSpend.objects.create(user = self.user, kind = "chat",
                                  input_tokens = 1000000, output_tokens = 1000000)

        self.assertIn("$30.00", self.run_report())


    def test_it_reports_the_busiest_single_day_and_not_only_the_total(self):
        TokenSpend.objects.create(user = self.user, kind = "chat", input_tokens = 5000)

        # A monthly total says nothing about whether a DAILY cap ever bound; the peak day is
        # the only figure that answers that.
        self.assertIn("busiest day", self.run_report().lower())


    def test_it_says_out_loud_whether_the_cap_was_binding(self):
        TokenSpend.objects.create(user = self.user, kind = "chat", input_tokens = 100)

        # The number alone leaves the reader to work out what it means, and the whole point of
        # the report is that it does not need me to interpret it.
        self.assertIn("nobody came close", self.run_report())


    def test_a_window_can_be_asked_for(self):
        old = TokenSpend.objects.create(user = self.user, kind = "chat", input_tokens = 5000)
        TokenSpend.objects.filter(pk = old.pk).update(
            created_at = timezone.now() - timedelta(days = 40))

        self.assertIn("Nothing recorded", self.run_report(days = 30))
        self.assertIn("omer", self.run_report(days = 60))

# ------------------------- THE BETA REPORT TESTS END ------------------------- #


# Six hours because these test the *clock*, not the policy - the arithmetic below is written
# against a window short enough to state in a sentence, and it holds for any length.
@override_settings(AI_USER_WINDOW_HOURS = 6, AI_BURST_UNITS = 0)
class RenewalClockTests(APITestCase):
    """
    **"Some of it, in about four hours" is a countdown he has to keep re-reading.**

    `renews_at` answers when the first piece comes back, which is the honest promise the
    rolling window makes and also the less useful half. The hour the whole allowance is his
    again is something he can plan around - and it is the question he asked the moment he
    read the first half of that sentence.
    """

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Tr4de-Pl4n!x")

    def spend(self, ago_hours, tokens = 1000):
        row = TokenSpend.objects.create(user = self.user, kind = "chat",
                                        input_tokens = tokens, output_tokens = tokens)
        # auto_now_add has to be written past, not set.
        TokenSpend.objects.filter(id = row.id).update(
            created_at = timezone.now() - timedelta(hours = ago_hours))
        return row

    def test_the_last_spend_is_the_one_that_frees_the_rest(self):
        self.spend(ago_hours = 5)
        self.spend(ago_hours = 1)

        first = budget.renews_at(self.user)
        whole = budget.fully_renewed_at(self.user)

        # One hour from now for the first piece; five for the whole thing.
        self.assertLess(first, whole)
        self.assertAlmostEqual((whole - timezone.now()).total_seconds() / 3600, 5, delta = 0.1)

    def test_the_message_names_the_hour(self):
        self.spend(ago_hours = 5)
        self.spend(ago_hours = 1)

        message = budget.exhausted_message(self.user)

        self.assertIn("מלאה שוב", message)
        self.assertRegex(message, "[0-9]{2}:[0-9]{2}")

    def test_the_hour_is_his_clock_and_not_the_server_s(self):
        """
        **The server runs in UTC and Israel is hours ahead of it.** A renewal at 21:40
        printed as 18:40 is worse than printing nothing, because he would wait and nothing
        would happen.
        """
        moment = timezone.now()

        said = budget._wall_clock(moment)
        israeli = timezone.localtime(moment, ZoneInfo("Asia/Jerusalem")).strftime("%H:%M")

        self.assertIn(israeli, said)
        if timezone.localtime(moment, ZoneInfo("UTC")).strftime("%H:%M") != israeli:
            self.assertNotEqual(said, moment.strftime("%H:%M"))

    @override_settings(AI_USER_WINDOW_HOURS = 24)
    def test_a_time_tomorrow_says_tomorrow(self):
        """
        **The hour was right and the sentence was still misleading**, which is the harder of
        the two to catch. A bare "20:41" for something twenty-three hours away reads as this
        evening, and he would plan around a time that is a day out.
        """
        self.spend(ago_hours = 1)

        message = budget.exhausted_message(self.user)

        self.assertIn("מחר ב-", message)

    def test_a_time_later_today_does_not(self):
        self.spend(ago_hours = 5.5)

        said = budget._wall_clock(timezone.now() + timedelta(minutes = 20))

        self.assertNotIn("מחר", said)
        self.assertTrue(said.startswith("ב-"), said)

    def test_the_panel_is_given_the_figure_too(self):
        """**The panel above the chat is the one he reads**, and it only had the partial
        time - the half that is a countdown rather than something he can plan around."""
        self.spend(ago_hours = 5)
        self.spend(ago_hours = 1)

        payload = budget.state(self.user)

        self.assertIsNotNone(payload["fully_renews_at"])
        # Oldest out first, newest out last - with one row they are the same moment, which
        # is right rather than a bug, so this needs two to say anything.
        self.assertGreater(payload["fully_renews_at"], payload["renews_at"])

    def test_nothing_spent_means_nothing_promised(self):
        self.assertIsNone(budget.fully_renewed_at(self.user))


class TwoWindowsTests(APITestCase):
    """
    **The trader's window and the site's are different numbers answering different
    questions**, and they shared one until his was shortened.

    There are three of them now, and the relationship inverted when the trader's budget
    became a **week**: his is the long one and the site's day is the short one.

      his week   168h   the money. A week of units is a week of dollars, and thirty days of
                        them is less than the subscription - which is what makes a loss
                        arithmetically impossible rather than unlikely.
      his day     24h   the speed. Without it the week can be emptied in an evening and he
                        is walled out for the six days it takes to roll back, which is the
                        one experience this whole design exists to prevent.
      the site    24h   everybody together, so one trader's rate cannot become the bill.

    **A budget exists to make the worst case sayable out loud, so a change that quietly
    multiplies it is the one failure it cannot have.** These keep the three independent.
    """

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Tr4de-Pl4n!x")

    def spend(self, ago_hours, tokens = 100_000):
        row = TokenSpend.objects.create(user = self.user, kind = "chat",
                                        input_tokens = tokens, output_tokens = tokens)
        TokenSpend.objects.filter(id = row.id).update(
            created_at = timezone.now() - timedelta(hours = ago_hours))

    def test_the_site_forgets_in_a_day_what_his_week_still_remembers(self):
        """Three days ago: long gone from the site's day and from his own, still inside the
        week that holds the money."""
        self.spend(ago_hours = 72)

        self.assertGreater(budget.spent(self.user), 0)
        self.assertEqual(budget.burst_spent(self.user), 0)
        self.assertEqual(budget.site_spent(), 0)

    def test_shortening_his_window_cannot_raise_the_site_ceiling(self):
        """The regression this class exists for."""
        with override_settings(AI_USER_WINDOW_HOURS = 1):
            self.spend(ago_hours = 8)

            # Still counted against the site, because the site has its own day.
            self.assertGreater(budget.site_spent(), 0)

    @override_settings(AI_BURST_UNITS = 150_000)
    def test_hitting_the_day_is_answered_in_hours_and_not_in_days(self):
        """
        **The promise the short window exists to keep**, carried over from when his only
        budget was six hours long: running out must not cost him the rest of the week.

        He is over the day here and nowhere near the week, so the ceiling that answers him
        has to be the day's - and the time he is told has to be hours away.
        """
        self.spend(ago_hours = 20, tokens = 100_000)       # 600,000 units, over the day

        self.assertFalse(budget.has_room(self.user))
        self.assertLess(budget.spent(self.user), budget.allowance())

        share, span = budget.binding(self.user)
        self.assertEqual(span, budget.burst_window())

        hours = (budget.renews_at(self.user, span) - timezone.now()).total_seconds() / 3600
        self.assertLess(hours, 5)

    def test_the_week_is_what_bounds_the_money(self):
        """The number the price is derived from: a month of weeks has to cost less than the
        subscription, or none of the rest of this means anything."""
        monthly = budget.allowance() * 30 / 7 * 5 / 1_000_000

        self.assertLess(monthly, 39)



# ------------------------- THE WEEK, THE DAY, AND THE SOFT LANDING ------------------------- #

@override_settings(AI_USER_UNITS = 1_450_000, AI_USER_WINDOW_HOURS = 168,
                   AI_BURST_UNITS = 350_000, AI_BURST_WINDOW_HOURS = 24,
                   AI_GLOBAL_DAILY_UNITS = 0, AI_WARN_AT = 0.90)
class WeeklyBudgetTests(APITestCase):
    """
    **The ceiling stopped being "a generous day" and became the thing that makes a loss
    impossible**, so it is now derived from the price rather than chosen to feel roomy.

    A week is 1,450,000 units, a unit is an input token of money, and thirty days of weeks is
    $31.07 against a $39 subscription. The worst user who can exist leaves $7.93. That is the
    whole argument, and these tests are what keep it true.

    The day inside the week is not a second budget - it is a speed limit on the first. Without
    it the week can be emptied on Monday, and six days of wall is exactly the experience the
    scheme exists to avoid.
    """

    def setUp(self):
        self.user = User.objects.create_user(username = "omer", password = "Tr4de-Pl4n!x")

    def spend(self, units_wanted, ago_hours = 0):
        """`units = input + 5 x output`, so input alone makes the arithmetic readable."""
        row = TokenSpend.objects.create(user = self.user, kind = "chat",
                                        input_tokens = units_wanted, output_tokens = 0)
        if ago_hours:
            TokenSpend.objects.filter(id = row.id).update(
                created_at = timezone.now() - timedelta(hours = ago_hours))
        return row

    # ------------- WHICH CEILING STOPS HIM:

    def test_the_day_stops_him_while_the_week_still_has_room(self):
        self.spend(400_000)

        self.assertFalse(budget.has_room(self.user))
        self.assertLess(budget.spent(self.user), budget.allowance())

    def test_the_week_stops_him_even_on_a_quiet_day(self):
        """Spent days ago, so the day is empty and only the week has anything to say."""
        for days in (2, 3, 4, 5):
            self.spend(400_000, ago_hours = days * 24)

        self.assertEqual(budget.burst_spent(self.user), 0)
        self.assertFalse(budget.has_room(self.user))

    def test_an_ordinary_trader_is_stopped_by_neither(self):
        """19% of the week is what the typical trader was measured at. **A ceiling he can
        feel is a ceiling that teaches him to ration himself**, which is the opposite of what
        this product needs from him."""
        self.spend(270_000)

        self.assertTrue(budget.has_room(self.user))
        self.assertFalse(budget.state(self.user)["should_warn"])

    # ------------- WHAT THE METER SAYS:

    def test_the_meter_shows_whichever_ceiling_is_nearest(self):
        """
        **One number reaches the screen and it has to be the one that will actually stop
        him.** Showing the week at 21% while the day is at 86% would read as plenty left,
        moments before he is refused - and a meter that disagrees with what happens next is
        worse than none, because the next reading is not believed either.
        """
        self.spend(300_000)                       # 86% of the day, 21% of the week

        share, span = budget.binding(self.user)

        self.assertEqual(span, budget.burst_window())
        self.assertEqual(budget.state(self.user)["used_percent"], 86)

    def test_the_week_takes_over_once_it_is_the_nearer_one(self):
        for days in (2, 3, 4):
            self.spend(400_000, ago_hours = days * 24)

        share, span = budget.binding(self.user)

        self.assertEqual(span, budget.window())
        self.assertEqual(budget.state(self.user)["window_hours"], 168)

    # ------------- THE SOFT LANDING:

    def test_larson_thinks_shorter_only_once_the_ceiling_is_near(self):
        """
        **The wall does not move in dollars; it moves 25% further out in answers.** The
        budget is denominated in money, so a cheaper answer does not lower the ceiling - it
        buys more answers underneath it. A cached turn is 5,937 units at `medium` and 4,747
        at `low`, which turns the last tenth of a week from 24 answers into 30.

        And it engages at the warning line and nowhere before it, so the answers on an
        ordinary day - every day, for 97% of traders - are the full-depth ones.
        """
        self.assertEqual(effort_for(self.user), EFFORT)

        self.spend(320_000)                       # 91% of the day: over the warning line

        self.assertTrue(budget.state(self.user)["should_warn"])
        self.assertEqual(effort_for(self.user), NEAR_THE_CEILING_EFFORT)

    def test_the_cheaper_answer_buys_more_answers_and_not_fewer(self):
        """The arithmetic the paragraph above rests on, so it cannot quietly stop being
        true if either constant moves."""
        left = int(budget.allowance() * 0.10)

        self.assertGreater(left // 4_747, left // 5_937)

    def test_an_unreadable_ledger_never_costs_him_his_answer(self):
        """**An optimisation must not be able to fail a reply.** If the spend table cannot be
        read, he gets the ordinary depth rather than an error."""
        with patch("usage.budget.state", side_effect = RuntimeError("no ledger")):
            self.assertEqual(effort_for(self.user), EFFORT)

    # ------------- AND THE PROMISE THE PRICE IS BUILT ON:

    def test_a_month_of_weeks_costs_less_than_the_subscription(self):
        """
        **The guarantee, stated as arithmetic rather than as a hope.** Whatever a trader
        does - loops, scripts, three debriefs a day for thirty days - he cannot spend more
        than a rolling week over and over, and that is $31.07 against $39.
        """
        worst = budget.allowance() * (30 / 7)
        dollars = worst * 5 / 1_000_000

        self.assertLess(dollars, 39)
        self.assertGreater(39 - dollars, 5, "the margin on the worst possible user is thin")

    def test_the_day_cannot_let_the_week_be_spent_in_one_sitting(self):
        """Without this the week is a Monday and then six days of wall."""
        days_to_empty_the_week = budget.allowance() / budget.burst_allowance()

        self.assertGreater(days_to_empty_the_week, 4)
