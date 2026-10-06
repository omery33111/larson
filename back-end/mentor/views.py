import logging

from collections import Counter
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from analytics.formatting import quoted
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from project.throttling import AIBurstThrottle, AIDailyThrottle
from chat.models import ASSISTANT, USER, Conversation, Message
from chat.serializers import MessageSerializer
from chat.failures import configuration_fault
from chat.views import _answer, _error_stream, _sse
from trades.models import Trade, TradeFile

from analytics.statistics import clean_label, compute_statistics
from chat import retrieval

from .compliance import check_plan
from .interpret import (MAX_RULE_LENGTH, coverage, interpret, per_term, read_back,
                        validate_a_reading, validate_his_own, vocabulary)
from .models import DismissedSuggestion, TraderRule
from .rules import conflicts_with, declared_rules
from .suggestions import asked_for_one, propose, standings
from .serializers import TraderRuleSerializer

from .context import (GREETING, baseline_set, mentor_messages, mentor_system, receipt,
                      suggestion_brief, update_prompt)
from .deviation import build_deviation



log = logging.getLogger(__name__)

MENTOR_TITLE = "המנטור"

# Past a handful, a debrief that answers every one of them stops being readable.
MAX_CUSTOM_RULES = 5



# ------------------------- THE ONE CONVERSATION START ------------------------- #
#
# One conversation per trader, forever. It is not a list with a single row by accident - the
# mentor is a standing relationship, and being unable to open a second one is the feature:
# there is exactly one place where the record of "how have I been doing" lives.

def _conversation(user):
    row = Conversation.objects.filter(user = user, is_mentor = True).first()

    if not row:
        row = Conversation.objects.create(user = user, is_mentor = True, title = MENTOR_TITLE)

        # He speaks first, and what he says is the ask. An empty screen would put the burden
        # of starting on the trader, which is the opposite of what this page is for.
        Message.objects.create(conversation = row, role = ASSISTANT, content = GREETING)

    _note_baseline(row, user)

    return row


def _note_baseline(conversation, user):
    """
    The line that says there is finally something to compare against.

    It answers to the state rather than to an event: the moment the resume stops being empty,
    the mentor says so and names what he is waiting for next. That makes it right however the
    founding trades arrived - through this screen, or filed through "my resume" before he ever
    came here.

    The thread is its own guard. It is written only while the greeting is still the only thing
    in it, so it can be said exactly once without a flag of its own to keep in sync.
    """
    if conversation.messages.count() != 1:
        return

    total = Trade.objects.filter(user = user).count()

    if not total:
        return

    Message.objects.create(conversation = conversation, role = ASSISTANT,
                           content = baseline_set(total))


def _resume_state(user):
    """
    What Larson currently knows, and how stale it is.

    `last_trade` rather than "last upload" on purpose: the gap that matters is between the
    trading he has done and the trading he has told anyone about.
    """
    trades = Trade.objects.filter(user = user)
    total = trades.count()

    if not total:
        return {"total_trades": 0, "last_trade": None, "days_since": None}

    last = trades.order_by("-executed_at").first().executed_at

    return {
        "total_trades": total,
        "last_trade": last,
        "days_since": (timezone.now() - last).days,
    }


def _pending(user):
    """
    The confirmed file that is still waiting to be sent, if there is one.

    It is read from the database rather than held on the screen for one reason: the trader
    may attach a file, get called away, close the tab, and come back tomorrow on another
    machine. His trades are already saved - what is still owed is the conversation about
    them - and something he was in the middle of should not disappear because he navigated.
    """
    row = (TradeFile.objects
           .filter(user = user, confirmed = True, awaiting_debrief = True)
           .order_by("-uploaded_at")
           .first())

    if not row:
        return None

    return {
        "id": row.id,
        "original_name": row.original_name,
        "imported_count": row.imported_count,
        "duplicate_count": row.duplicate_count,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mentor(request):
    row = _conversation(request.user)

    return Response({
        "conversation_id": row.id,
        "messages": MessageSerializer(row.messages.all(), many = True).data,
        "resume": _resume_state(request.user),
        "pending_file": _pending(request.user),
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def pending(request):
    """
    Take the waiting file off the composer.

    It does not remove anything from the resume, and the screen says so: the trades were
    saved the moment he confirmed them, and undoing that is what "my resume" is for. All
    this drops is the debrief he decided not to ask for.
    """
    TradeFile.objects.filter(user = request.user, awaiting_debrief = True).update(
        awaiting_debrief = False)

    return Response({"pending_file": None})

# ------------------------- THE ONE CONVERSATION END ------------------------- #



# ------------------------- THE DEBRIEF START ------------------------- #

# Two windows on the meter, because this is the endpoint that spends money: one
# answer is allowed up to 64k output tokens. See project/throttling.py.
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIBurstThrottle, AIDailyThrottle])
def stream(request):
    row = _conversation(request.user)

    text = str(request.data.get("message", "")).strip()
    trade_file_id = request.data.get("trade_file_id")

    if not text and not trade_file_id:
        return _error_stream("אין מה לשלוח.")

    # A debrief with nothing to compare against is not a debrief. Talking to him before he has
    # seen a single trade would cost a model call to produce generalities, and would teach the
    # trader that the mentor has nothing specific to say - which is the one impression this
    # screen cannot afford to make first. Sending a file is always allowed: that is the way
    # out of this state.
    if not trade_file_id and not Trade.objects.filter(user = request.user).exists():
        return _error_stream(
            "לארסון עוד לא ראה אף עסקה שלך, אז אין לו למה להשוות. שלח לו קובץ עסקאות קודם.")

    if not settings.ANTHROPIC_API_KEY:
        return _error_stream(configuration_fault("ANTHROPIC_API_KEY is empty"))

    prelude = ""
    verdict = ""
    suggestion = None
    briefing = text

    if trade_file_id:
        trade_file = get_object_or_404(TradeFile, id = trade_file_id, user = request.user)

        if not trade_file.confirmed:
            # The gate is the point. Nothing is analysed until the trader has said yes to it
            # entering his record.
            return _error_stream("הקובץ עדיין לא אושר לקליטה.")

        # The baseline is the resume as it stood before this file - which is exactly what
        # "compared to what I already know about you" means.
        recent = list(Trade.objects.filter(user = request.user, trade_file = trade_file))
        baseline = list(Trade.objects.filter(user = request.user).exclude(trade_file = trade_file))

        currency = _currency(recent or baseline)
        zone = _timezone(recent or baseline)

        report = build_deviation(baseline, recent, currency, zone)

        # The second report, and the one that answers a session of one. The deviation needs a
        # sample; this needs a single trade, because a rule is broken or kept by each trade on
        # its own. Without it, closing a day on one trade got "come back with more" - which is
        # the mentor refusing to do the only job he has.
        # **His own commitments first, then what his history argues for.** `rules.py` gives
        # them the same shape, so the checker needs no special case and the offending trade
        # is named the same way either way.
        plan = check_plan(compute_statistics(baseline), baseline, recent, currency, zone,
                          declared = declared_rules(request.user, currency,
                                                    for_judging = True))

        # The plan check already decided this; reading it is free. Broken rules outrank kept
        # ones - a debrief that found a repeat offence is not a green day whatever else went
        # right in it.
        if plan.get("available"):
            verdict = "broken" if plan["broken"] else ("kept" if plan["kept"] else "")

        # Consumed the moment it is sent, not when the answer finishes: the screen has to
        # stop offering it immediately, and a second press must not produce a second debrief.
        if trade_file.awaiting_debrief:
            trade_file.awaiting_debrief = False
            trade_file.save(update_fields = ["awaiting_debrief"])

        # **Larson's one question, composed here and never by the model.** Python found the
        # condition and computed the figure; the model will not see this and cannot press
        # anything - the same shape as the receipt line directly below.
        try:
            suggestion = propose(request.user, recent, compute_statistics(baseline + recent),
                                 currency, zone)
        except Exception:
            # A debrief must not fail over an optional card.
            log.exception("Could not compose a suggestion")
            suggestion = None

        prelude = receipt(trade_file)
        # `text` is still whatever he typed here - the fallback title below has not run yet -
        # so a note sent with the file reaches the model instead of being replaced away.
        briefing = update_prompt(report, plan, len(baseline) + len(recent), len(recent),
                                 trade_file.original_name, is_first = not baseline, note = text)

        if not text:
            text = f"עדכון: {trade_file.original_name}"

    question = Message.objects.create(conversation = row, role = USER, content = text,
                                      attachment_name = trade_file.original_name
                                                        if trade_file_id else "")

    row.save()

    system = mentor_system(request.user)
    messages = mentor_messages(row)

    # The briefing replaces the last user turn rather than being appended as its own message:
    # what the trader typed is on screen, and what the model needs to see is the report.
    if messages and briefing != text:
        messages[-1]["content"] = briefing
    else:
        # **No file this turn, so this is a question** - and the mentor is the screen where
        # "what happened on the 18th" gets asked most. It is deliberately not attached to a
        # debrief turn: when a file was sent, the briefing is the point, and rows pulled for
        # a half-read question would compete with it.
        retrieval.attach(messages, retrieval.block_for(request.user, text,
                                                       billed_to = request.user))

        # **And if he asked for a rule in words, that is the moment.** The card normally
        # waits for a debrief where he has just repeated the pattern, because that is when
        # it is most likely to be accepted - but a trader who types "suggest me a rule" and
        # gets nothing back has been told the feature does not exist.
        if asked_for_one(text):
            try:
                own = list(Trade.objects.filter(user = request.user))
                suggestion = propose(request.user, [], compute_statistics(own),
                                     _currency(own), _timezone(own), asked = True)
            except Exception:
                log.exception("Could not compose a suggestion on request")

            # **And the words are told what the button is about to say.** He asked, Larson
            # proposed something in prose the checker cannot judge, and no button appeared -
            # from the outside that reads as broken. The card is still composed in python
            # and the model still writes nothing; this only stops the two contradicting.
            # **Through `attach` and never with `+=`.** The last turn's content is a list of
            # blocks once prompt caching is on, and `list += str` appends the string one
            # character at a time - which the API rejects with
            # `messages.N.content.1: Input should be an object`. It cost a production
            if messages:
                # The standings go with it, so the model can answer the forced choice
                # even when nothing clears the bar for a button.
                try:
                    figures = standings(request.user, _currency(own), _timezone(own))
                except Exception:
                    log.exception("Could not read the rule standings")
                    figures = []

                retrieval.attach(messages,
                                 chr(10) * 2 + suggestion_brief(suggestion, figures))

    return _sse(_answer(row, question, system, messages, prelude, verdict,
                        budget_kind = "mentor", suggestion = suggestion))


def _currency(trades):
    for trade in trades:
        if trade.currency:
            return trade.currency
    return "USD"


def _timezone(trades):
    """
    The one clock the whole debrief is judged in.

    **It is the trader's wall clock, not the file's** - "I do not enter before ten" is about
    the moment he clicked, wherever the export happened to be stamped. There is no field for
    where he sits, so the zone his files carry is the best evidence of it, and every rule
    about an hour uses this one answer rather than each trade's own.

    **Judging each trade in its own `source_timezone` was considered and is wrong**: a US
    broker exporting New York time does not move the trader to New York, and it would have
    compared his 10:00 against two different tens in the same debrief.

    What changed is only how the one zone is picked. It used to be whichever row came out of
    the database first - correct whenever his files agree, and an arbitrary coin toss when
    they do not. The commonest one is the same answer in the ordinary case and a defensible
    one in the rare case, for three lines.
    """
    counted = Counter(trade.source_timezone for trade in trades if trade.source_timezone)

    if not counted:
        return "Asia/Jerusalem"

    # `most_common` breaks ties by insertion order, so an even split still lands on the
    # zone that appears first - deterministic rather than whichever row the query returned.
    return counted.most_common(1)[0][0]

# ------------------------- THE DEBRIEF END ------------------------- #


# ------------------------- THE RULES HE SETS FOR HIMSELF ------------------------- #
#
# **Three endpoints and no more.** One rule of each structured kind, enforced in the database
# rather than in the screen: two ceilings on the same thing is not a stricter plan, it is a
# plan with no answer, and the debrief would then report both.
#
# **The free-text rule is the exception, and several of them are the point.** "Only with an
# IFVG" and "never during news" are both true at once. The cap is here rather than in the
# model because it is a judgement about a screen - past a handful, a debrief that answers
# every one of them stops being readable.


def _custom(row, trades = None):
    """
    One free-text rule, in the one shape both endpoints return.

    **What it looks for travels on every rule, not only the one just saved.** Frozen terms
    degrade quietly, and a line he can read at any time is how he notices. `terms` rides
    along because the editor needs the structure to render it as separate chips - he edits
    his own words there, never a paraphrase of them.

    **And `matched` rides along instead of a paragraph.** Earlier versions explained in
    prose what happens when a rule's words appear in none of his trades; a number that says
    `0` beside the rule says it faster, in every language, and without being read.
    """
    return {**TraderRuleSerializer(row).data,
            "looking_for": read_back(row.terms),
            "terms": row.terms,
            "matched": coverage(trades, row.terms)["matched"] if trades is not None else None}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rules(request):
    """What he has committed to, and the full menu of what he could."""
    rows = list(TraderRule.objects.filter(user = request.user))

    # Loaded once for all of them rather than per rule: it is the same list every time, and
    # the matcher is a string comparison.
    trades = (list(Trade.objects.filter(user = request.user))
              if any(row.kind == TraderRule.CUSTOM for row in rows) else [])

    return Response({
        "rules": [_custom(row, trades) if row.kind == TraderRule.CUSTOM
                  else TraderRuleSerializer(row).data
                  for row in rows],
        # The menu travels with the answer so the screen never holds its own copy of the
        # kinds - a second list of them is one release away from disagreeing with this one.
        "kinds": [{"kind": kind, "label": label} for kind, label in TraderRule.KINDS],
        # **Whether he has tagged anything at all**, because the free-text rule is built on
        # exactly that and nothing else. Learning it only after writing a rule and reading
        # the coverage line is learning it one step too late - the screen should say so
        # before he writes, not after.
        "has_labels": bool(vocabulary(request.user)),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_rule(request):
    """Create or replace one commitment."""
    kind = str(request.data.get("kind", "")).strip()

    if kind not in dict(TraderRule.KINDS):
        return Response({"error": "סוג כלל לא מוכר."}, status = status.HTTP_400_BAD_REQUEST)

    number = request.data.get("number")

    # ------------- THE ONE IN HIS OWN WORDS:
    #
    # Interpreted **here, once**, rather than on every trade of every debrief. If it cannot
    # be interpreted the rule is refused outright - a saved rule with no terms is a rule that
    # every trade keeps forever, which is worse than no rule at all.
    if kind == TraderRule.CUSTOM:
        text = clean_label(str(request.data.get("text", "")), MAX_RULE_LENGTH)

        if not text:
            return Response({"error": "צריך לכתוב את התנאי."},
                            status = status.HTTP_400_BAD_REQUEST)

        rule_id = request.data.get("id")
        existing = TraderRule.objects.filter(user = request.user, kind = TraderRule.CUSTOM)

        if not rule_id and existing.count() >= MAX_CUSTOM_RULES:
            return Response({"error": f"אפשר עד {MAX_CUSTOM_RULES} תנאים משלך."},
                            status = status.HTTP_400_BAD_REQUEST)

        # ------------- HE CORRECTED THE TERMS HIMSELF:
        #
        # **Then there is nothing to interpret, and no call to pay for.** He has told us
        # exactly what to look for, which is better information than any reading of his
        # sentence - he is the only one who knows that his FVG entries are tagged
        # `5m fvg retracement`.
        supplied = request.data.get("terms")

        # **A trader who tags nothing cannot have a rule in his own words, and he is told
        # why rather than left to find out.**
        #
        # Not every journal is tagged - plenty export a date, a symbol and a P&L and nothing
        # else - and a condition in his own words is matched against the labels he writes on
        # the trade. With no labels anywhere, every such rule is unjudgeable from the moment
        # it is saved: it would sit in the panel looking like a commitment and never once
        # fire. **A feature that quietly does nothing is worse than one that says it cannot
        # help**, and the gate is here and not only on the screen for the same reason the
        # empty-resume gate is: a screen is a courtesy, a condition in code is the rule.
        #
        # The sentence names the three columns that unlock it, because that is a thing he
        # can actually do before his next export - and says the templates still work, since
        # they read numbers his record already carries.
        if not vocabulary(request.user):
            # **Two different empties, and one message for both would be wrong for one of
            # them.** A trader with no trades at all has not failed to tag anything; he
            # simply has not started. Telling him to fill a column he has never exported
            # reads as the product misunderstanding him.
            seen_any = Trade.objects.filter(user = request.user).exists()

            return Response({
                "error": ("תנאי בניסוח שלך נבדק מול התגיות שאתה רושם על העסקאות, "
                          "ובעסקאות שלך אין אף תגית. מלא בייצוא הבא עמודת סטאפ, תגיות "
                          "או טעויות — והתנאים ייפתחו. התבניות המוכנות עובדות גם בלי."
                          if seen_any else
                          "לארסון עוד לא ראה אף עסקה שלך. העלה קובץ, ואז אפשר לכתוב תנאי "
                          "במילים שלך — הוא ייבדק מול התגיות שבקובץ."),
            }, status = status.HTTP_400_BAD_REQUEST)

        if supplied:
            terms = validate_his_own(supplied)

            if not terms:
                return Response({"error": "צריך לפחות מונח אחד לחפש."},
                                status = status.HTTP_400_BAD_REQUEST)
        else:
            # His own labels go in with the sentence, so a term comes back as a string that
            # exists in his record rather than as a guess about what it might be called.
            terms = interpret(text, billed_to = request.user,
                              known_labels = vocabulary(request.user))

        if not terms:
            return Response({
                "error": "לא הצלחנו לתרגם את התנאי הזה למשהו שאפשר לבדוק מול עסקה. "
                         "נסה לנסח אותו במונחים שאתה רושם על העסקאות עצמן — תגית, שם סטאפ "
                         "או מילה שאתה כותב בהערות.",
            }, status = status.HTTP_400_BAD_REQUEST)

        # **Refused rather than saved and reported later.** Two rules that cannot both hold
        # make one of them break on every trade, and the debrief would report that forever
        # without ever saying the two are arguing with each other.
        clash = conflicts_with(request.user, TraderRule.CUSTOM, terms = terms,
                               ignore_id = rule_id)

        if clash:
            other, word = clash

            if other is None:
                return Response({"error": f"התנאי הזה דורש {quoted(word)} ואוסר אותו באותה "
                                          f"נשימה — אין עסקה שיכולה לקיים אותו."},
                                status = status.HTTP_400_BAD_REQUEST)

            # `word` is None when the collision is that the two look for exactly the same
            # thing - nothing contradicts, so there is no term to name.
            if word is None:
                return Response({"error": f"זה בודק בדיוק את מה שכלל קיים כבר בודק — "
                                          f"{quoted(clean_label(other.text, MAX_RULE_LENGTH))}. "
                                          f"ערוך אותו במקום להוסיף עוד אחד."},
                                status = status.HTTP_400_BAD_REQUEST)

            # **Every term he wrote goes through `quoted`**, which keeps a latin run from
            # dragging the punctuation around it and swapping two tags in the sentence.
            # See `analytics.formatting.quoted` - it was measured on exactly this message.
            return Response({"error": f"התנאי הזה סותר כלל שכבר יש לך — "
                                      f"{quoted(clean_label(other.text, MAX_RULE_LENGTH))}. "
                                      f"שניהם מדברים על {quoted(word)}, "
                                      f"ולא ייתכן ששניהם יתקיימו."},
                            status = status.HTTP_400_BAD_REQUEST)

        if rule_id:
            row = TraderRule.objects.filter(user = request.user, id = rule_id,
                                            kind = TraderRule.CUSTOM).first()
            if not row:
                return Response({"error": "אין כלל כזה."}, status = status.HTTP_404_NOT_FOUND)
            row.text, row.terms, row.is_active = text, terms, True
            row.known_labels = vocabulary(request.user)
            row.save()
        else:
            row = TraderRule.objects.create(user = request.user, kind = TraderRule.CUSTOM,
                                            text = text, terms = terms,
                                            known_labels = vocabulary(request.user))

        # **How many of his trades can answer it at all.** Without this he reads "kept" over a
        # year of trades that recorded nothing, and believes he followed a plan he never did.
        # **The same shape the list returns, and that is the whole point of saying so here.**
        # It did not, and the screen fell back to printing the whole read-back inside one box
        # for a rule he had just saved while showing the same rule as separate chips after a
        # reload. Two paths returning different shapes for one object is a defect that only
        # ever shows up in the half of the session nobody tests.
        mine = list(Trade.objects.filter(user = request.user))

        return Response({**_custom(row, mine), "coverage": coverage(mine, terms)},
                        status = status.HTTP_201_CREATED)

    try:
        number = float(number)
    except (TypeError, ValueError):
        return Response({"error": "צריך מספר."}, status = status.HTTP_400_BAD_REQUEST)

    # ------------- THE TWO THAT ARE A TIME OF DAY:
    #
    # **Minutes from midnight, and midnight itself is a legitimate value.** The others are
    # thresholds where zero means "no rule", but 00:00 is a real wall clock time, so the
    # "greater than zero" check cannot apply to these two.
    if kind in (TraderRule.NO_BEFORE, TraderRule.NO_AFTER):
        if not 0 <= number <= 1439:
            return Response({"error": "שעה היא בין 00:00 ל-23:59."},
                            status = status.HTTP_400_BAD_REQUEST)
    elif number <= 0:
        return Response({"error": "המספר צריך להיות גדול מאפס."},
                        status = status.HTTP_400_BAD_REQUEST)

    clash = conflicts_with(request.user, kind, number = number)

    if clash:
        _, word = clash
        return Response({"error": f"זה סותר את הכלל שכבר יש לך — לא היית יכול לסחור "
                                  f"בשום שעה. הכלל האחר אומר {quoted(word)}."},
                        status = status.HTTP_400_BAD_REQUEST)

    row, _ = TraderRule.objects.update_or_create(
        user = request.user, kind = kind,
        defaults = {"number": number, "is_active": True})

    return Response(TraderRuleSerializer(row).data, status = status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_rule(request, rule_id):
    """Dropped entirely rather than switched off.

    **Keyed on the row and not on the kind**, which it used to be: a kind identified a rule
    only while there was one of each, and the free-text kind broke that. Deleting by kind
    would now take every custom rule he has with it.

    `is_active` exists for the day a trader wants to pause a rule without losing that he had
    it; nothing in the interface reaches that yet, and a flag with no way to set it would be
    a column pretending to be a feature.
    """
    deleted, _ = TraderRule.objects.filter(user = request.user, id = rule_id).delete()

    if not deleted:
        return Response({"error": "אין כלל כזה."}, status = status.HTTP_404_NOT_FOUND)

    return Response(status = status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_rule(request):
    """
    What a set of terms would find, right now, over his own record.

    **This is what turns editing the terms from guessing into feedback.** He sees
    `fair value gap - 0` beside `fvg - 23` and needs nothing explained: the dead term is
    visibly dead, and he fixes it before saving rather than a month after.

    No model and no cost - the same matcher the verdict uses, run over rows already in hand.
    It also hands back his own labels, because the fastest correct edit is picking the tag
    he actually writes instead of typing a guess at it.
    """
    terms = validate_his_own(request.data.get("terms") or {})

    rows = list(Trade.objects.filter(user = request.user))

    return Response({
        "per_term": per_term(terms, rows) if terms else {},
        "coverage": coverage(rows, terms),
        # Capped for the screen rather than for the prompt: a list he has to scroll past is
        # a list he stops reading.
        "labels": vocabulary(request.user)[:120],
    })


# ------------------------- ANSWERING LARSON'S QUESTION ------------------------- #
#
# **Two endpoints, and between them is the line the whole security argument rests on.**
# Python found the condition and composed the card; the trader presses a button; python
# writes the row. The model is not in this path at all and never was - it cannot create a
# rule, delete one, or reach these endpoints, which is what keeps "the model has no tools"
# true after this feature exists.

def _card(message_id, user):
    """The message carrying the open question, or `None` if it is already answered."""
    row = Message.objects.filter(id = message_id, conversation__user = user,
                                 conversation__is_mentor = True).first()

    return row if row and row.suggestion else None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_suggestion(request):
    """His yes, which is what turns Larson's observation into his own commitment."""
    row = _card(request.data.get("message_id"), request.user)

    if not row:
        return Response({"error": "ההצעה כבר נענתה."}, status = status.HTTP_404_NOT_FOUND)

    card = row.suggestion

    if card.get("action") == "retire":
        TraderRule.objects.filter(user = request.user, id = card.get("rule_id")).delete()

    else:
        kind = card.get("rule_kind")

        if kind not in dict(TraderRule.KINDS):
            return Response({"error": "סוג כלל לא מוכר."},
                            status = status.HTTP_400_BAD_REQUEST)

        known = vocabulary(request.user)

        # **The card's terms are the model's words, not his.** They went through
        # `validate_his_own` - the trusted path, which lifts the short-term gate and leaves
        # a self-contradiction standing - purely because the endpoint reads as "his yes".
        # His yes is to the *idea*; the spellings were still written by a reading, and a
        # reading gets the same checking here as it gets anywhere else.
        terms = (validate_a_reading(card.get("rule_terms") or {}, known_labels = known)
                 if kind == TraderRule.CUSTOM else None)

        # **And nothing checked this against the rules he already has.** Accepting a card
        # could plant a rule contradicting one of his, which then breaks on every trade and
        # is reported forever without anything saying the two are arguing - the exact
        # failure the check was written for, reached through the one door it did not cover.
        clash = conflicts_with(request.user, kind, terms = terms,
                               number = card.get("rule_number"))

        if clash:
            return Response({"error": "ההצעה מתנגשת עם כלל שכבר יש לך, ולא היה אפשר "
                                      "לקיים את שניהם. אפשר לדחות אותה."},
                            status = status.HTTP_400_BAD_REQUEST)

        if kind == TraderRule.CUSTOM:
            TraderRule.objects.create(
                user = request.user, kind = kind,
                text = clean_label(card.get("rule_text", ""), MAX_RULE_LENGTH),
                terms = terms, known_labels = known)
        else:
            TraderRule.objects.update_or_create(
                user = request.user, kind = kind,
                defaults = {"number": card.get("rule_number"), "is_active": True})

    # **Cleared either way**, so the card cannot be answered twice or reappear on a reload.
    row.suggestion = None
    row.save(update_fields = ["suggestion"])

    return Response({"done": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def dismiss_suggestion(request):
    """
    His no, remembered for good.

    The condition behind a suggestion is usually still true next week, so without this the
    same card returns every debrief until he gives in or stops reading them. **A mentor who
    asks the same question weekly is not persistent, he is ignorable.**
    """
    row = _card(request.data.get("message_id"), request.user)

    if not row:
        return Response({"error": "ההצעה כבר נענתה."}, status = status.HTTP_404_NOT_FOUND)

    key = row.suggestion.get("key")

    if key:
        DismissedSuggestion.objects.get_or_create(user = request.user, key = key)

    row.suggestion = None
    row.save(update_fields = ["suggestion"])

    return Response({"done": True})
