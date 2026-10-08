"""
How much of the model a single trader may spend, and how much is left.

**This is not the same thing as the rate limits, and it is the one that protects the bill.**
`project/throttling.py` counts requests: forty an hour, a hundred and fifty a day. But one
request is not one price - measured on a 400-trade resume, an ordinary answer costs about
4,200 input tokens and a few hundred out, while a single call is allowed to keep generating
far past that. Counting requests cannot tell those apart, so a limit that looks strict can
still empty an account.

So the meter runs on tokens the API actually reported, and the limit is on what they cost.


### Why units and not tokens

Output on this model is priced at five times input. A budget that added the two together
would let a thousand tokens of generated text and a thousand tokens of prompt cost the same
amount of somebody's day, when one of them is five times the money. So the figure spent is:

    units = input + 5 x output

which is the price ratio, and therefore a straight stand-in for cost. **The trader never sees
it.** He sees a percentage, and a percentage of a number chosen to mean "a generous day" is
easier to reason about than tokens are.


### Why a rolling window and not a daily reset

A window that resets at midnight can be spent twice in two minutes - all of Monday at 23:59
and all of Tuesday at 00:01 - which is exactly the shape a runaway loop produces. A rolling
window has no such edge: what frees up is whatever fell out the back, whenever it was spent.

It also gives a better answer to somebody who has just run out. "It resets at midnight" is
eleven hours of nothing; "you get some back in 40 minutes" is true and useful.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import TokenSpend


# The four prices `claude-opus-5` charges, as multiples of ordinary input. A unit is
# therefore "one input token of money", whatever kind of token actually produced it.
#
#   input        $5  / MTok   x1
#   cache write  $10 / MTok   x2      (an HOUR-long prefix; the five-minute one is x1.25)
#   cache read   $0.50/ MTok  x0.1    (a tenth - this is the whole point of caching)
#   output       $25 / MTok   x5
#
# If the model or its pricing changes, these four lines are the only ones to move.
#
# **The write weight and the cache's lifetime are one decision and must move together.**
# `chat/context.py` asks for a one-hour prefix, which Anthropic prices at twice input rather
# than the five-minute prefix's 1.25. Leaving this at 1.25 would not raise an error anywhere:
# the meter would simply under-count every write by 60%, the trader would sail past a ceiling
# that is supposed to be the thing guaranteeing a profit, and the first sign of it would be
# the invoice. If the TTL is ever shortened again, this number comes back down with it.
OUTPUT_WEIGHT = 5
CACHE_WRITE_WEIGHT = 2.0
CACHE_READ_WEIGHT = 0.1

# What one ordinary answer costs, measured in October 2026 against a 233-trade resume: a
# cached turn at `effort: medium`. **It exists so the trader is never shown a bare
# percentage.** "10% left" is a fraction of a number he has never seen and cannot act on;
# "about 12 more answers" is the only unit he thinks in.
#
# **Deliberately the medium figure and not the cheaper one.** Past the warning line Larson
# drops to `low`, which costs 4,747 - so the count quoted here is the floor and he gets at
# least that many. A promise that runs out early is the one direction this must not fail in.
TYPICAL_ANSWER = 5_937

# **How few answers have to be left before anything is said at all**, and it is a count and
# not a percentage because a percentage of a week means something different from a percentage
# of a day. Ten per cent of the week is twenty-five answers - a notice there would be
# arriving two full sessions early and teaching exactly the rationing the panel exists to
# avoid. Ten per cent of the day is five, which is a real warning.
#
# Ten is about two sessions of notice: enough that the ceiling is never a surprise, not so
# much that a line hovers over the chat for days.
WARN_BELOW_ANSWERS = 10


def warn_at():
    """
    How full it has to be before anything is said, and it is late on purpose.

    Below it the meter is not on screen at all. **The notice exists so that the wall is not a
    surprise - not so that the trader can budget around it**, and somebody who finishes the
    day at 80% never needed to know a limit existed. A bar that is always visible teaches
    people to ration themselves, and rationing is the opposite of what this product asks of
    them: the mentor only works if he is told everything.
    """
    return settings.AI_WARN_AT


def units(input_tokens, output_tokens, cache_write_tokens = 0, cache_read_tokens = 0):
    """
    What one call cost, in input-token-equivalents.

    **`input_tokens` is the uncached remainder only**, never the whole prompt - the total the
    model read is the three input figures added together. Counting only the first would make
    a well-cached request look almost free while it was still being billed for the write.
    """
    return int(
        int(input_tokens)
        + CACHE_WRITE_WEIGHT * int(cache_write_tokens)
        + CACHE_READ_WEIGHT * int(cache_read_tokens)
        + OUTPUT_WEIGHT * int(output_tokens)
    )


def window():
    """The budget that bounds the **money**: a rolling week."""
    return timedelta(hours = settings.AI_USER_WINDOW_HOURS)


def allowance():
    return settings.AI_USER_UNITS


def burst_window():
    """The budget that bounds a **runaway loop**: a rolling day."""
    return timedelta(hours = settings.AI_BURST_WINDOW_HOURS)


def burst_allowance():
    """
    **Why a second, shorter ceiling exists at all.**

    The week is what makes a loss impossible - a week's worth of units is a week's worth of
    dollars, and thirty days of them is less than the subscription. But a week-long budget
    on its own can be emptied in an evening, and then the trader is locked out for the six
    days it takes to roll back. **That is the one failure this design cannot have**: the
    whole point of the ceiling is that he does not notice it.

    So the day caps how fast the week can be spent. It is set at five full sittings, and the
    heaviest trader measured does one and a half - it is not there to ration anybody, it is
    there so that nobody can empty the week before the week is over. With it, the worst
    lock-out drops from six days to about three, and no real usage reaches either.
    """
    return settings.AI_BURST_UNITS


def traders_with_a_resume():
    """
    How many people have actually handed Larson a trading history.

    **Counted rather than "how many signed up", and that is the whole safety of scaling the
    site ceiling by it.** A thousand bot registrations would lift a ceiling tied to accounts
    and defeat the thing it is there for; lifting this one costs a parseable export per
    account, which is work, and which is also exactly the population that legitimately calls
    the model.
    """
    from trades.models import Trade

    return Trade.objects.values("user").distinct().count()


def site_allowance():
    """
    The ceiling on everybody together - **and it grows with the people paying for it.**

    It used to be a flat $20 a day, which was right when it was written and became wrong the
    moment the per-trader budget started bounding the money. A trader is capped at $1.75 a
    day and $31 a month, so the site total is already bounded at `traders x their own cap`,
    automatically. **A second, flat bound on top of that cannot protect anything the first
    one does not - the only thing it can still do, once there are customers, is refuse one
    of them.** Measured before this changed: 11.4 traders could max their day, and the beta
    is ten. One more sign-up and somebody who had paid would read that the system had run
    out of money.
    

    So it is the larger of a floor and what the active traders are collectively entitled to,
    and never more than a maximum set here:

        max(AI_GLOBAL_DAILY_UNITS, traders x AI_BURST_UNITS)  capped at AI_GLOBAL_MAX_UNITS

    **It can no longer be the thing that stops a legitimate trader**, because every one of
    them maxing out at once still fits underneath it. What it does catch is spend that
    should have been impossible - a hole in the per-trader accounting - which is the only
    job left for a ceiling at this level, and the one it was really there for.

    `AI_GLOBAL_MAX_UNITS` is the number to raise deliberately as the business grows, and the
    only one that can ever cost a customer an answer. Set it to 0 to lift it.
    """
    floor = settings.AI_GLOBAL_DAILY_UNITS

    if not floor:
        return 0                          # the ceiling is off entirely

    earned = traders_with_a_resume() * settings.AI_BURST_UNITS
    ceiling = settings.AI_GLOBAL_MAX_UNITS

    return min(max(floor, earned), ceiling) if ceiling else max(floor, earned)


def _since(span = None):
    return timezone.now() - (span or window())


# `__gt` and not `__gte`, which is the difference between "within the last 24 hours" and
# "within the last 24 hours, plus this instant". A spend that is exactly the window old has
# aged out - and on a clock with coarse resolution (Windows ticks about every 16ms) "exactly"
# happens far more often than it sounds like it would.
WITHIN = "created_at__gt"


def spent(user, span = None):
    """What this trader has used inside a window, in units. Defaults to the weekly one."""
    rows = TokenSpend.objects.filter(user = user, **{WITHIN: _since(span)})

    return sum(units(row.input_tokens, row.output_tokens,
                     row.cache_write_tokens, row.cache_read_tokens) for row in rows)


def burst_spent(user):
    return spent(user, burst_window())


def renews_at(user, span = None):
    """
    When the next piece of the budget comes back.

    The oldest spend still inside the window is the first thing to fall out of it, so that is
    the moment something frees up. It is not when the whole allowance returns - and saying so
    would be a promise the window does not make.
    """
    span = span or window()
    oldest = (TokenSpend.objects
              .filter(user = user, **{WITHIN: _since(span)})
              .order_by("created_at")
              .first())

    return (oldest.created_at + span) if oldest else None


def fully_renewed_at(user, span = None):
    """
    When the window is empty again - the clock time he actually wants.

    `renews_at` is when the *first* piece comes back, which is the honest thing to promise
    and is also the less useful of the two: "some of it in about four hours" tells him to
    keep checking. **The last spend inside the window is the last to fall out of it**, so
    that moment is when the whole allowance is his again, and it is a time he can plan
    around rather than a countdown he has to re-read.
    """
    span = span or window()
    newest = (TokenSpend.objects
              .filter(user = user, **{WITHIN: _since(span)})
              .order_by("-created_at")
              .first())

    return (newest.created_at + span) if newest else None


def _wall_clock(moment):
    """
    His clock, and **which day it is**, which the first version left out.

    Two things go wrong without the day. The server runs in UTC and Israel is hours ahead
    of it, so a renewal at 21:40 printed as 18:40 is worse than printing nothing - he would
    wait and nothing would happen. And a bare "20:41" for something twenty-three hours away
    reads as this evening: **the hour was right and the sentence was still misleading**,
    which is the harder of the two to notice.
    """
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Jerusalem")
    local = timezone.localtime(moment, zone)
    today = timezone.localtime(timezone.now(), zone).date()

    days = (local.date() - today).days
    clock = local.strftime("%H:%M")

    # A phrase rather than a bare time, so the caller never has to glue a preposition onto
    # it - which is where the one-line mess this replaced came from.
    if days <= 0:
        return f"ב-{clock}"
    if days == 1:
        return f"מחר ב-{clock}"

    # **A weekday, because the window is a week now and a date is something he has to
    # decode.** "ביום שלישי" lands immediately; "ב-13/10" makes him look at a calendar to
    # find out whether that is soon. Monday is 0 in Python and Sunday starts the week here.
    if days <= 6:
        names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        return f"ביום {names[local.weekday()]} ב-{clock}"

    # Seven days out a weekday name stops being unambiguous - "Tuesday" could be either one.
    return local.strftime("ב-%d/%m בשעה ") + clock


def near_ceiling(user):
    """
    Whether he is into the last tenth of whichever budget binds.

    **Separate from `should_warn`, and the split is the point.** The panel asks "is this
    worth his attention yet", which is a question about how many answers are left. This asks
    "should Larson start spending less per answer", which is a question about how much money
    is left - and tying the second to the first would mean every time the notice got quieter
    the budget stretched less, for no reason anybody intended.
    """
    return binding(user)[0] >= warn_at()


def answers_left(user):
    """
    Roughly how many more ordinary answers the remaining budget buys, on whichever ceiling
    is nearer. Floored, so it is never an over-promise.
    """
    share, span = binding(user)
    total = burst_allowance() if span == burst_window() else allowance()

    return max(int(total * (1 - min(share, 1.0))) // TYPICAL_ANSWER, 0)


def _frees_at(user, span, total, needed):
    """
    When enough of a rolling window has aged out to pay for `needed` units.

    **A rolling window gives budget back a little at a time, and that is exactly what makes
    it hard to describe.** "Some of it in about forty minutes" is true and answers nothing -
    he cannot tell whether that buys one question or none. So instead of narrating the
    mechanism, the spends are walked oldest-first and the moment the freed total covers one
    answer is returned. That moment is the only thing he wants to know.
    """
    room = total - spent(user, span)

    if room >= needed:
        return None                       # he can ask right now; nothing to wait for

    rows = (TokenSpend.objects
            .filter(user = user, **{WITHIN: _since(span)})
            .order_by("created_at"))

    freed = 0
    for row in rows:
        freed += units(row.input_tokens, row.output_tokens,
                       row.cache_write_tokens, row.cache_read_tokens)

        if room + freed >= needed:
            return row.created_at + span

    # Everything in the window ages out and it is still not enough - which can only happen
    # if one answer costs more than the whole allowance. Say when the window empties.
    return fully_renewed_at(user, span)


def next_answer_at(user):
    """
    When he can ask his next question. **Both ceilings have to clear, so it is the later
    of the two** - telling him the day has freed up while the week still refuses him is the
    same broken promise in a smaller package.
    """
    moments = [_frees_at(user, window(), allowance(), TYPICAL_ANSWER)]

    if burst_allowance():
        moments.append(_frees_at(user, burst_window(), burst_allowance(), TYPICAL_ANSWER))

    waits = [m for m in moments if m]

    return max(waits) if waits else None


def binding(user):
    """
    Which of the trader's two ceilings he is nearest, as (share, span).

    **One number reaches the screen, and it has to be the one that will actually stop him.**
    Showing the week while the day is the thing about to refuse him would say 30% a moment
    before he is told no - and a meter that disagrees with what happens next is worse than
    no meter, because the next time it says 30% he will not believe it either.
    """
    week = (spent(user) / allowance()) if allowance() else 0.0

    if not burst_allowance():
        return week, window()

    day = burst_spent(user) / burst_allowance()

    return (day, burst_window()) if day > week else (week, window())


def state(user):
    """Everything the client needs to decide whether to say anything, in one read."""
    share, span = binding(user)
    share = min(share, 1.0)

    when = renews_at(user, span)

    nxt = next_answer_at(user)

    return {
        "used_percent": round(share * 100),
        "remaining_percent": round(max(1 - share, 0) * 100),
        "exhausted": not has_room(user),
        # **Both, and they answer different halves of the same question.** The share says
        # he is near a ceiling; the count says whether that is worth his attention yet.
        "should_warn": share >= warn_at() and answers_left(user) <= WARN_BELOW_ANSWERS,
        "renews_at": when.isoformat() if when else None,
        # **The panel above the chat is the one he reads**, and it only had the partial
        # time - the half that is a countdown rather than something he can plan around.
        "fully_renews_at": (lambda f: f.isoformat() if f else None)(
            fully_renewed_at(user, span)),
        "window_hours": int(span.total_seconds() // 3600),

        # **The three the screen actually says a sentence out of**, and all three exist
        # because a percentage of an unseen number is not something anybody can act on.
        "answers_left": answers_left(user),
        "next_answer_at": nxt.isoformat() if nxt else None,
        # Which ceiling stopped him. "today" and "this week" recover on completely
        # different scales, and promising the wrong one is the whole failure.
        "scope": "day" if span == burst_window() else "week",
    }


def site_window():
    """
    **A day, and not the trader's window.** The two answer different questions - his decides
    how long a cap may punish him, this one is the money - and they shared a window until
    his was shortened to six hours. Sharing it would have turned "$20 a day" into "$20 every
    six hours", with nothing anywhere saying it had changed.
    """
    return timedelta(hours = settings.AI_GLOBAL_WINDOW_HOURS)


def site_spent():
    """What everyone together has used inside the site's own day."""
    rows = TokenSpend.objects.filter(**{WITHIN: timezone.now() - site_window()})

    return sum(units(row.input_tokens, row.output_tokens,
                     row.cache_write_tokens, row.cache_read_tokens) for row in rows)


def has_room(user):
    """
    Whether this trader may make another call - against his own budget, and the site's.

    **The second one exists because the first does not bound anything by itself.** A per-user
    cap multiplied by however many people sign up tomorrow is not a ceiling, it is a rate; and
    the whole reason to have a budget is to be able to name the worst case out loud. With both,
    the worst case is a number that was chosen rather than one that emerges.

    Set `AI_GLOBAL_DAILY_UNITS` to 0 to lift it.
    """
    if spent(user) >= allowance():
        return False

    # **The day is checked second and separately, because it means something else.** The week
    # is the money; the day is the speed. A trader stopped by the day still has budget - he
    # gets it back in hours, not days - and the message he is shown has to say so, which it
    # cannot do if the two are collapsed into one test.
    if burst_allowance() and burst_spent(user) >= burst_allowance():
        return False

    ceiling = site_allowance()

    return not ceiling or site_spent() < ceiling


def record(user, kind, usage):
    """
    Store what an answer cost, straight from the API's own `usage` block.

    Anything unreadable is recorded as a zero rather than skipped: a row still marks that a
    call happened, and a call that vanished from the ledger because its shape was unfamiliar
    is worse than one recorded as free.
    """
    return TokenSpend.objects.create(
        user = user,
        kind = kind,
        input_tokens = getattr(usage, "input_tokens", 0) or 0,
        output_tokens = getattr(usage, "output_tokens", 0) or 0,
        cache_write_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0,
        cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0,
    )


# ------------------------- WHAT THE TRADER IS TOLD ------------------------- #

def site_exhausted():
    ceiling = site_allowance()
    return bool(ceiling) and site_spent() >= ceiling


def when_phrase(moment):
    """
    One time, said the way a person would say it.

    Under two hours a countdown is what he wants - "in about forty minutes" is something he
    can wait out. Past that a countdown is useless and a clock time is something he can plan
    around, which is the whole reason `_wall_clock` carries the day with it.
    """
    minutes = max(round((moment - timezone.now()).total_seconds() / 60), 1)

    if minutes < 60:
        return f"בעוד כ-{minutes} דקות"
    if minutes < 120:
        return "בעוד כשעה" if minutes < 90 else "בעוד כשעה וחצי"

    return _wall_clock(moment)


def exhausted_message(user):
    """
    What he reads the moment Larson refuses him, and it has to answer the only question he
    has: **when can I ask again.**

    Three things this replaced got wrong, and each produced a question rather than closing
    one. It said "today's quota" **whichever ceiling had stopped him** - so a trader held by
    the week was sent away until tomorrow and found the same wall. It said "some of it frees
    up in about forty minutes", and *some* is unanswerable: he cannot tell whether that buys
    a question or none of one. And it then gave a **second** time for when the allowance is
    whole, leaving him to work out which of the two he was supposed to plan around.

    So: the ceiling named correctly, one moment, and that moment is the next time an answer
    actually fits - not the next time anything at all frees up.
    """
    # **Not his fault, and not described as ours being stingy either.** Naming a system-wide
    # money ceiling to somebody who has paid reads as the operator holding back when he
    # could have given more - and it is the one sentence here that can make a limit feel
    # like a slight rather than a queue. It is a fault on our side, so it is said in the
    # sentence the product already uses for faults on our side, and the trader is told the
    # only two things that concern him: it is not his, and it is short.
    if site_exhausted() and spent(user) < allowance():
        return "לארסון לא זמין כרגע. זה לא קשור למכסה שלך — נסה שוב בעוד כמה דקות."

    period = "של היום" if binding(user)[1] == burst_window() else "השבועית"
    when = next_answer_at(user)

    if not when:
        return f"הגעת למכסת השימוש {period}. נסה שוב בעוד זמן קצר."

    return f"הגעת למכסת השימוש {period}. תוכל לשאול שוב {when_phrase(when)}."
