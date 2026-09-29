import statistics as stats_lib
from collections import defaultdict
from zoneinfo import ZoneInfo

# The outcome rules are subtle - the journal's own status column wins over the sign of the
# P&L, and a scratch is neither a win nor a loss. Re-deriving them here would be a second
# definition of "did this trade work", and the two would drift.
from analytics.statistics import REVENGE_WINDOW_MINUTES, _is_loss, _is_win, clean_label
from analytics.formatting import minutes as minutes_text
from analytics.formatting import money, percent, ratio
from analytics.formatting import trades as trade_count



# ------------------------- THE DEVIATION ENGINE START ------------------------- #
#
# The mentor's whole reason to exist. Everything here is computed in Python and handed to the
# model finished - the same iron rule the profile and the chat live under.
#
# What it compares is deliberate: **what Larson already knew** against **what just arrived**.
# Not "the last 30 days" and not a rolling window - the baseline is the resume as it stood
# before this file, and the recent side is exactly the trades the trader just confirmed. That
# is what makes the answer land: it is a reaction to what he did, not a periodic report.

# Below this there is nothing to say. Three trades that went badly are a bad afternoon, not
# a deviation, and calling them one teaches the trader to distrust the mentor.
MIN_RECENT_TRADES = 5

# A baseline this thin is not yet a description of anyone.
MIN_BASELINE_TRADES = 20

# How far a metric has to move before it is worth a sentence. Everything drifts a little.
MIN_RELATIVE_CHANGE = 0.25



def _mean(values):
    return stats_lib.fmean(values) if values else 0.0


def _relative(before, after):
    """How far `after` moved from `before`, as a fraction. Guards a zero baseline."""
    if not before:
        return 0.0 if not after else 1.0

    return (after - before) / abs(before)


def _times(before, after):
    """The same move said the way a trader says it: 'x2.4'."""
    if not before:
        return None

    return round(after / before, 2)


def _by_day(trades, tz):
    days = defaultdict(list)

    for trade in trades:
        days[trade.executed_at.astimezone(tz).date()].append(trade)

    return days



# ------------- EXPOSURE:
def _exposure(baseline, recent, ctx):
    """
    How big he is betting.

    Quantity is the honest measure and is used whenever the journal carries it. When it does
    not, average risk is approximated by the average size of a result - and the sentence says
    so, because a proxy presented as a measurement is a lie with a number attached.
    """
    currency = ctx["currency"]

    sizes = lambda rows: [t.quantity for t in rows if t.quantity]

    before, after = sizes(baseline), sizes(recent)
    measure = "גודל הפוזיציה הממוצע"
    fmt = lambda v: f"{round(v, 2)} חוזים"

    if not before or not after:
        before = [abs(t.pnl) for t in baseline if t.pnl is not None]
        after = [abs(t.pnl) for t in recent if t.pnl is not None]
        measure = "גודל התוצאה הממוצעת (בהיעדר כמות ביומן, זה הקירוב לחשיפה)"
        fmt = lambda v: money(v, currency)

    if not before or not after:
        return None

    mean_before, mean_after = _mean(before), _mean(after)
    change = _relative(mean_before, mean_after)

    if abs(change) < MIN_RELATIVE_CHANGE:
        return None

    factor = _times(mean_before, mean_after)
    direction = "קפץ" if change > 0 else "ירד"

    return {
        "key": "exposure",
        "title": f"{measure} {direction} " + (f"פי {factor}" if factor else percent(abs(change) * 100)),
        "detail": f"מ-{fmt(mean_before)} ל-{fmt(mean_after)}.",
        "evidence": f"{trade_count(len(after))} חדשות מול {trade_count(len(before))} קודמות",
        # Betting bigger is not automatically wrong - it is wrong when the bigger trades lose.
        "is_worse": change > 0 and _mean([t.pnl for t in recent if t.pnl is not None]) < 0,
        "magnitude": abs(change),
    }


# ------------- FREQUENCY:
def _frequency(baseline, recent, ctx):
    tz = ctx["tz"]
    before_days, after_days = _by_day(baseline, tz), _by_day(recent, tz)

    if not before_days or not after_days:
        return None

    before = _mean([len(v) for v in before_days.values()])
    after = _mean([len(v) for v in after_days.values()])
    change = _relative(before, after)

    if abs(change) < MIN_RELATIVE_CHANGE:
        return None

    direction = "עלה" if change > 0 else "ירד"

    return {
        "key": "frequency",
        "title": f"קצב המסחר היומי {direction} מ-{round(before, 1)} ל-{round(after, 1)} עסקאות ביום",
        "detail": f"על פני {trade_count(len(recent))} ב-{len(after_days)} ימי מסחר.",
        "evidence": f"{len(after_days)} ימים חדשים מול {len(before_days)} קודמים",
        "is_worse": change > 0,
        "magnitude": abs(change),
    }


# ------------- THE HOURS HE IS ACTUALLY GOOD IN:
def _session(baseline, recent, ctx):
    """Whether he is still trading in the windows that used to work for him."""
    tz = ctx["tz"]
    by_hour = defaultdict(list)

    for trade in baseline:
        by_hour[trade.executed_at.astimezone(tz).hour].append(trade.pnl or 0.0)

    strong = {hour for hour, pnls in by_hour.items()
              if len(pnls) >= MIN_RECENT_TRADES and _mean(pnls) > 0}

    if not strong:
        return None

    before_share = sum(1 for t in baseline
                       if t.executed_at.astimezone(tz).hour in strong) / len(baseline)
    after_share = sum(1 for t in recent
                      if t.executed_at.astimezone(tz).hour in strong) / len(recent)

    change = after_share - before_share

    if abs(change) < 0.15:
        return None

    window = ", ".join(f"{h:02d}:00" for h in sorted(strong)[:4])
    direction = "יותר" if change > 0 else "פחות"

    return {
        "key": "session",
        "title": f"אתה סוחר {direction} בשעות שעובדות לך ({window})",
        "detail": f"{percent(after_share * 100)} מהעסקאות החדשות נפלו שם, מול "
                  f"{percent(before_share * 100)} בעבר.",
        "evidence": trade_count(len(recent)),
        "is_worse": change < 0,
        "magnitude": abs(change) * 2,
    }


# ------------- REVENGE:
def _revenge(baseline, recent, ctx):
    def share(rows):
        if len(rows) < 2:
            return None

        hits = 0
        for previous, current in zip(rows, rows[1:]):
            opened = current.opened_at or current.executed_at
            gap = (opened - previous.executed_at).total_seconds() / 60

            if _is_loss(previous) and 0 <= gap <= REVENGE_WINDOW_MINUTES:
                hits += 1

        return hits / (len(rows) - 1)

    before, after = share(baseline), share(recent)

    if before is None or after is None:
        return None

    change = after - before

    if abs(change) < 0.10:
        return None

    direction = "עלה" if change > 0 else "ירד"

    return {
        "key": "revenge",
        "title": f"החלק של העסקאות שנפתחות מיד אחרי הפסד {direction}",
        "detail": f"{percent(after * 100)} מהעסקאות החדשות נפתחו תוך "
                  f"{REVENGE_WINDOW_MINUTES} דקות מסגירת מפסידה, מול {percent(before * 100)} בעבר.",
        "evidence": trade_count(len(recent)),
        "is_worse": change > 0,
        "magnitude": abs(change) * 2.5,
    }


# ------------- HOLDING LOSERS:
def _hold_time(baseline, recent, ctx):
    def asymmetry(rows):
        wins = [t.duration_seconds for t in rows if _is_win(t) and t.duration_seconds]
        losses = [t.duration_seconds for t in rows if _is_loss(t) and t.duration_seconds]

        if not wins or not losses:
            return None

        return _mean(losses) / _mean(wins), _mean(losses) / 60

    before, after = asymmetry(baseline), asymmetry(recent)

    if before is None or after is None:
        return None

    change = _relative(before[0], after[0])

    if abs(change) < MIN_RELATIVE_CHANGE:
        return None

    direction = "גדל" if change > 0 else "הצטמצם"

    return {
        "key": "hold_time",
        "title": f"הפער בין הזמן שאתה נותן למפסידות לזמן שאתה נותן לרווחיות {direction}",
        "detail": f"יחס של {ratio(after[0])} מול {ratio(before[0])} בעבר. "
                  f"מפסידה ממוצעת מוחזקת {minutes_text(after[1])}.",
        "evidence": trade_count(len(recent)),
        "is_worse": change > 0,
        "magnitude": abs(change),
    }


# ------------- THE RESULT ITSELF:
def _outcome_shift(baseline, recent, ctx):
    currency = ctx["currency"]

    def stats(rows):
        pnls = [t.pnl for t in rows if t.pnl is not None]
        wins = sum(1 for t in rows if _is_win(t))
        decided = wins + sum(1 for t in rows if _is_loss(t))

        if not pnls or not decided:
            return None

        return wins / decided * 100, sum(pnls) / len(pnls)

    before, after = stats(baseline), stats(recent)

    if before is None or after is None:
        return None

    change = _relative(before[1], after[1])

    if abs(change) < MIN_RELATIVE_CHANGE:
        return None

    direction = "עלתה" if after[1] > before[1] else "ירדה"

    # No "ל-" in front of the figure: a negative expectancy renders with its own minus, and
    # the two collided into "ל--$20.97".
    return {
        "key": "expectancy",
        "title": f"התוחלת לעסקה {direction}, ועכשיו היא {money(after[1], currency)}",
        "detail": f"מול {money(before[1], currency)} בבייסליין. אחוז ההצלחה: "
                  f"{percent(after[0])} מול {percent(before[0])}.",
        "evidence": trade_count(len(recent)),
        "is_worse": after[1] < before[1],
        "magnitude": abs(change),
    }


# ------------- SETUPS:
def _setups(baseline, recent, ctx):
    def tags(rows):
        found = defaultdict(int)
        for trade in rows:
            # **Cleaned for the same reason the breakdowns are**, and this is the second door
            # into the same room: a setup name goes from here into a finding, and a finding
            # goes into the prompt. A cell holding several lines of prose would arrive there
            # whole. See `clean_label`.
            for tag in (trade.setups or "").split(","):
                tag = clean_label(tag)
                if tag:
                    found[tag] += 1
        return found

    before, after = tags(baseline), tags(recent)

    if not before or not after:
        return None

    # A setup he used to lean on and has stopped taking. The reverse - something brand new -
    # is not a deviation from a baseline, it is simply not in it yet.
    core = {tag for tag, n in before.items() if n >= MIN_RECENT_TRADES}
    dropped = sorted(core - set(after))

    if not dropped:
        return None

    return {
        "key": "setups",
        "title": f"הפסקת לקחת סטאפ שהיה חלק מהבסיס שלך: {', '.join(dropped[:2])}",
        "detail": f"אף לא אחת מ-{trade_count(len(recent))} החדשות נושאת אותו.",
        "evidence": f"בעבר {before[dropped[0]]} עסקאות",
        "is_worse": True,
        "magnitude": 0.4,
    }



# ------------- WHAT DID WORK:
def _bright_spot(baseline, recent, ctx):
    """
    The strongest slice of the window that just arrived, in its own right.

    The comparisons above can only produce good news when something measurably improved, and
    on a bad stretch nothing does - which left the debrief as pure bad news. This looks inside
    the new trades instead of across the two periods, so there is almost always something true
    to point at. It is not a consolation prize: a positive-expectancy pocket inside a losing
    stretch is the most useful thing the trader can be told.
    """
    currency = ctx["currency"]
    tz = ctx["tz"]

    def best(groups, label):
        pockets = [(key, pnls) for key, pnls in groups.items() if len(pnls) >= MIN_RECENT_TRADES]
        if not pockets:
            return None

        key, pnls = max(pockets, key = lambda p: _mean(p[1]))

        if _mean(pnls) <= 0:
            return None

        return {
            "key": "bright_spot",
            "title": f"מה שכן עבד: {label(key)}",
            "detail": f"תוחלת {money(_mean(pnls), currency)} לעסקה שם, בתוך אותה תקופה.",
            "evidence": trade_count(len(pnls)),
            "is_worse": False,
            "magnitude": 0.5,
        }

    by_setup = defaultdict(list)
    for trade in recent:
        for tag in (trade.setups or "").split(","):
            label = clean_label(tag)
            if label:
                by_setup[label].append(trade.pnl or 0.0)

    by_hour = defaultdict(list)
    for trade in recent:
        by_hour[trade.executed_at.astimezone(tz).hour].append(trade.pnl or 0.0)

    return (best(by_setup, lambda k: f"הסטאפ {k}")
            or best(by_hour, lambda k: f"השעה {int(k):02d}:00"))


COMPARISONS = [_exposure, _frequency, _session, _revenge, _hold_time, _outcome_shift, _setups]

MAX_DEVIATIONS = 3


def build_deviation(baseline, recent, currency = "USD", timezone_name = "Asia/Jerusalem"):
    """
    Returns {"available", "reason"?, "deviations", "reinforcement", "counts"}.

    Everything numeric is finished here. The model is handed this and asked to say it like a
    mentor - it never recomputes and never adds a figure of its own.
    """
    counts = {"baseline": len(baseline), "recent": len(recent)}

    if len(recent) < MIN_RECENT_TRADES:
        return {"available": False, "counts": counts,
                # Neutral on purpose. This is a statistic declining to speak, not the mentor
                # declining to answer - the plan check beside it answers at any size.
                "reason": f"העדכון מכיל {trade_count(len(recent))}. השוואה סטטיסטית מתחילה "
                          f"לומר משהו מ-{MIN_RECENT_TRADES} עסקאות ומעלה, ולכן אין כאן דוח "
                          f"סטיות — בדיקת הכללים שלצידו כן תקפה."}

    if len(baseline) < MIN_BASELINE_TRADES:
        return {"available": False, "counts": counts,
                "reason": f"הרזומה שלפני העדכון מכילה {trade_count(len(baseline))}, וזה עוד לא "
                          f"בייסליין שאפשר להשוות אליו. מ-{MIN_BASELINE_TRADES} עסקאות זה מתחיל לעבוד."}

    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")

    baseline = sorted(baseline, key = lambda t: t.executed_at)
    recent = sorted(recent, key = lambda t: t.executed_at)

    ctx = {"currency": currency, "tz": tz}

    found = [result for compare in COMPARISONS
             if (result := compare(baseline, recent, ctx))]

    worse = sorted([f for f in found if f["is_worse"]], key = lambda f: -f["magnitude"])
    better = sorted([f for f in found if not f["is_worse"]], key = lambda f: -f["magnitude"])

    # Exactly one, when there is one to give. A debrief that is only bad news stops being
    # read, so when nothing improved against the baseline the best pocket inside the new
    # window is looked for instead.
    reinforcement = better[0] if better else _bright_spot(baseline, recent, ctx)

    return {
        "available": True,
        "counts": counts,
        "deviations": [_public(f) for f in worse[:MAX_DEVIATIONS]],
        "reinforcement": _public(reinforcement) if reinforcement else None,
    }


def _public(finding):
    """`magnitude` is an internal ranking key with no unit, so it never leaves the engine."""
    return {k: v for k, v in finding.items() if k != "magnitude"}

# ------------------------- THE DEVIATION ENGINE END ------------------------- #
