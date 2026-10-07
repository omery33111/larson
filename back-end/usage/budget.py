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


def site_allowance():
    return settings.AI_GLOBAL_DAILY_UNITS


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

    # The window is capped at a day, so this cannot happen today - but a config change
    # should not quietly turn the sentence back into a lie.
    return local.strftime("ב-%d/%m בשעה ") + clock


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

    return {
        "used_percent": round(share * 100),
        "remaining_percent": round(max(1 - share, 0) * 100),
        "exhausted": not has_room(user),
        "should_warn": share >= warn_at(),
        "renews_at": when.isoformat() if when else None,
        # **The panel above the chat is the one he reads**, and it only had the partial
        # time - the half that is a countdown rather than something he can plan around.
        "fully_renews_at": (lambda f: f.isoformat() if f else None)(
            fully_renewed_at(user, span)),
        "window_hours": int(span.total_seconds() // 3600),
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


def exhausted_message(user):
    """
    Said in the product's voice rather than as an error code, and it says when.

    A limit with no horizon reads as a fault; the same limit with "in about two hours" reads
    as a queue.
    """
    # The site ceiling is not this trader's fault and must not be described as his doing.
    if site_exhausted() and spent(user) < allowance():
        return ("המערכת הגיעה לתקרת השימוש היומית הכוללת שלה. "
                "זה לא קשור למכסה שלך — נסה שוב עוד זמן קצר.")

    # **Stopped by the day is a different sentence from stopped by the week**, and saying the
    # wrong one costs trust in opposite directions: "come back in a few hours" to somebody
    # who has days to wait is a lie, and "come back in a few days" to somebody with hours
    # sends him away for nothing.
    _, span = binding(user)
    when = renews_at(user, span)

    if not when:
        return "הגעת למכסת השימוש. היא מתחדשת בהמשך היום."

    # Rounded rather than floored: an hour away is 3,599.9 seconds by the time this runs,
    # and flooring turns "about an hour" into "about 59 minutes" - which is true, and reads
    # like the number was measured rather than estimated.
    minutes = max(round((when - timezone.now()).total_seconds() / 60), 1)

    if minutes < 60:
        soon = f"חלק ממנה מתפנה בעוד כ-{minutes} דקות"
    else:
        hours = minutes // 60
        soon = "חלק ממנה מתפנה בעוד " + ("כשעה" if hours == 1 else f"כ-{hours} שעות")

    # **And the hour it is whole again, because "some of it, in about four hours" is a
    # countdown he has to keep re-reading.** A clock time is something he can plan around -
    # and it is the question he actually asked when he saw the first half of this sentence.
    full = fully_renewed_at(user, span)

    if full:
        return f"הגעת למכסת השימוש להיום. {soon}, והיא מלאה שוב {_wall_clock(full)}."

    return f"הגעת למכסת השימוש להיום. {soon}."
