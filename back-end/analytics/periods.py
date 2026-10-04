from collections import defaultdict
from datetime import timedelta

from .formatting import days as day_count, money, percent, trades as trade_count
from .statistics import (MIN_TRADES_FOR_BREAKDOWN, _instrument_of, _is_loss, _is_win, _mean,
                         _safe_zone, _split_tags, clean_label)



# ------------------------- PERIODS START ------------------------- #
#
# **"Am I getting better?" was unanswerable, and it is the one question a mentor exists for.**
#
# Everything the model received was a single aggregate over the whole record: one win rate,
# one expectancy, one breakdown by hour. **A number computed over everything cannot say
# whether it is rising.** Asked how his last month compared with the one before, Larson had
# nothing and could only apologise - which is also why the opening questions were written to
# steer around it.
#
# This file is the missing axis. It is the same shape as every other engine here: a pure
# function over a list of trades, no database access, no model involved. What it adds is that
# the trades are cut into windows first and then compared, instead of being summed once.
#
# **Four cuts, because each answers a different question and no single one answers all three:**
#
#   months            - "how has it gone over time", the series a trader thinks in
#   recent vs before   - "what changed lately", a rolling 30 against the 30 before it
#   halves             - "am I better than when I started", and it works at any sample size
#   records            - "have I ever done better than this", which is what makes a first
#                        feel noticed rather than calculated
#
# **And three findings that only an axis can produce:** the drawdown as a span with dates
# rather than a number, the drift in when and what he trades, and what he has stopped doing.
# **Absence is the hardest thing for a person to notice about himself** and the cheapest thing
# for a loop to find.


# A window needs enough trades to mean anything. Below this the comparison is noise wearing
# the costume of a trend, which is worse than silence - the same floor the breakdowns use.
MIN_WINDOW_TRADES = MIN_TRADES_FOR_BREAKDOWN

# What counts as a real move rather than drift. Borrowed from the deviation engine, which
# settled on the same number for the same reason: under a quarter, two windows of a dozen
# trades differ by chance.
MIN_RELATIVE_CHANGE = 0.25

RECENT_WINDOW_DAYS = 30

MAX_MONTHS = 6
MAX_RECORDS = 4
MAX_DRIFT = 3
MAX_ABANDONED = 3



def build_periods(trades, currency = "USD", timezone_name = "Asia/Jerusalem"):
    """The record cut along time, instead of summed over it."""
    rows = sorted([t for t in trades if t.pnl is not None], key = lambda t: t.executed_at)

    if len(rows) < MIN_WINDOW_TRADES * 2:
        return {
            "available": False,
            "reason": f"צריך לפחות {MIN_WINDOW_TRADES * 2} עסקאות כדי להשוות בין תקופות, "
                      f"ויש {len(rows)}.",
        }

    tz = _safe_zone(timezone_name, rows)

    months = _months(rows, tz, currency)
    recent, previous = _rolling_windows(rows, tz)

    return {
        "available": True,
        "חודשים": _public(months[-MAX_MONTHS:]),
        "השוואה_אחרונה": _compare(recent, previous, "30 הימים האחרונים",
                                  "30 הימים שלפניהם", currency),
        "חצי_ראשון_מול_שני": _halves(rows, currency),
        "מגמה": _trend(months, currency),
        "שיאים": _records(rows, months, tz, currency)[:MAX_RECORDS],
        "הדראודאון_הגדול": _drawdown_story(rows, tz, currency),
        "נדידה": _drift(recent, previous, tz, currency)[:MAX_DRIFT],
        "מה_הפסקת": _abandoned(rows, tz, currency)[:MAX_ABANDONED],
    }



# ------------- THE CUTS:
def _months(rows, tz, currency):
    """One compact row per calendar month, oldest first.

    Each row carries `_expectancy` - the raw figure - beside the formatted one, because the
    trend has to compare months and **a formatted amount cannot be compared**. Parsing the
    symbol back out was the first version of this and it would have returned zero for every
    month of a euro account. `_public` strips it before the document leaves.
    """
    buckets = defaultdict(list)
    for trade in rows:
        local = trade.executed_at.astimezone(tz)
        buckets[(local.year, local.month)].append(trade)

    out = []
    for (year, month), group in sorted(buckets.items()):
        pnls = [t.pnl for t in group]
        out.append({
            "חודש": f"{month:02d}/{year}",
            "עסקאות": len(group),
            **_shape(group, currency),
            "_expectancy": sum(pnls) / len(pnls) if pnls else 0.0,
        })

    return out


def _public(months):
    """The months as the model sees them - without the raw figure the trend needed."""
    return [{k: v for k, v in month.items() if not k.startswith("_")} for month in months]


def _rolling_windows(rows, tz):
    """The last 30 days, and the 30 before them - measured from the newest trade, not today.

    **From the data and not from the clock**, because a trader who has not uploaded for two
    weeks would otherwise be told his recent window is empty - which is true of the calendar
    and useless as feedback.
    """
    newest = rows[-1].executed_at
    edge = newest - timedelta(days = RECENT_WINDOW_DAYS)
    older = edge - timedelta(days = RECENT_WINDOW_DAYS)

    recent = [t for t in rows if t.executed_at > edge]
    previous = [t for t in rows if older < t.executed_at <= edge]

    return recent, previous


def _halves(rows, currency):
    """Split down the middle of the record by count, not by date.

    By count rather than by date on purpose: a trader who took a month off would otherwise
    have one half holding almost everything, and the comparison would describe the break
    instead of the progress.
    """
    middle = len(rows) // 2
    return _compare(rows[middle:], rows[:middle], "החצי השני של ההיסטוריה",
                    "החצי הראשון", currency)



# ------------- COMPARING TWO WINDOWS:
def _shape(group, currency):
    """The handful of figures worth carrying per window. Deliberately not the full document."""
    pnls = [t.pnl for t in group]
    wins = [t for t in group if _is_win(t)]
    losses = [t for t in group if _is_loss(t)]
    decided = len(wins) + len(losses)

    return {
        "רווח_נקי": money(round(sum(pnls), 2), currency),
        "תוחלת": money(round(sum(pnls) / len(pnls), 2), currency) if pnls else money(0, currency),
        "אחוז_הצלחה": percent(round(len(wins) / decided * 100, 2)) if decided else percent(0),
    }


def _compare(after, before, after_name, before_name, currency):
    """Two windows, and a verdict only when both are large enough to carry one."""
    if len(after) < MIN_WINDOW_TRADES or len(before) < MIN_WINDOW_TRADES:
        return {
            "available": False,
            "reason": f"אין מספיק עסקאות בשני הצדדים ({len(after)} מול {len(before)}, "
                      f"צריך {MIN_WINDOW_TRADES} בכל אחד).",
        }

    after_expectancy = _mean([t.pnl for t in after])
    before_expectancy = _mean([t.pnl for t in before])

    change = _relative(before_expectancy, after_expectancy)

    return {
        "available": True,
        after_name: {"עסקאות": len(after), **_shape(after, currency)},
        before_name: {"עסקאות": len(before), **_shape(before, currency)},
        "פסיקה": _verdict(before_expectancy, after_expectancy, change, currency),
    }


def _relative(before, after):
    """How much the figure moved, as a fraction of where it started."""
    if not before:
        return None
    return (after - before) / abs(before)


def _verdict(before, after, change, currency):
    """**The sentence, not the number** - and it refuses to call noise a direction."""
    gap = money(round(after - before, 2), currency)

    if change is None or abs(change) < MIN_RELATIVE_CHANGE:
        return (f"התוחלת לעסקה כמעט לא זזה ({gap} הפרש). **זה לא שיפור ולא הרעה** — "
                f"זה אותו מסחר.")

    if after > before:
        return (f"**התוחלת לעסקה עלתה** מ-{money(round(before, 2), currency)} "
                f"ל-{money(round(after, 2), currency)}, הפרש של {gap}.")

    return (f"**התוחלת לעסקה ירדה** מ-{money(round(before, 2), currency)} "
            f"ל-{money(round(after, 2), currency)}, הפרש של {gap}.")


def _trend(months, currency):
    """Direction across the whole series, which a single pair of windows cannot see."""
    usable = [m for m in months if m["עסקאות"] >= MIN_WINDOW_TRADES]

    if len(usable) < 3:
        return {"available": False,
                "reason": "צריך שלושה חודשים עם מספר עסקאות מובהק כדי לדבר על מגמה."}

    # Expectancy is carried formatted, so the comparison runs on the raw figure instead.
    values = [m["_expectancy"] for m in usable]
    rises = sum(1 for a, b in zip(values, values[1:]) if b > a)
    falls = sum(1 for a, b in zip(values, values[1:]) if b < a)

    first, last = values[0], values[-1]
    span = f"{usable[0]['חודש']} עד {usable[-1]['חודש']}"

    if rises > falls and last > first:
        return {"available": True, "כיוון": "משתפר",
                "detail": f"על פני {len(usable)} חודשים ({span}) התוחלת עלתה "
                          f"ב-{rises} מתוך {len(usable) - 1} המעברים."}

    if falls > rises and last < first:
        return {"available": True, "כיוון": "מדרדר",
                "detail": f"על פני {len(usable)} חודשים ({span}) התוחלת ירדה "
                          f"ב-{falls} מתוך {len(usable) - 1} המעברים."}

    return {"available": True, "כיוון": "ללא מגמה",
            "detail": f"על פני {len(usable)} חודשים ({span}) התוחלת עולה ויורדת בלי כיוון — "
                      f"{rises} עליות מול {falls} ירידות."}


# ------------- WHAT ONLY AN AXIS CAN SAY:
def _records(rows, months, tz, currency):
    """Bests, and whether the newest window is one of them.

    **A record is the thing that makes a mentor sound like he was watching.** "Your best month
    so far" is a different sentence from "your expectancy is $47" even when both come from the
    same column, because one of them knows what came before.
    """
    out = []

    by_day = _by_day(rows, tz)
    totals = {day: sum(t.pnl for t in group) for day, group in by_day.items()}

    if totals:
        best_day = max(totals, key = totals.get)
        worst_day = min(totals, key = totals.get)
        out.append({"שיא": "היום הטוב ביותר",
                    "detail": f"{best_day:%d/%m/%Y} — {money(round(totals[best_day], 2), currency)} "
                              f"על {trade_count(len(by_day[best_day]))}."})
        out.append({"שיא": "היום הגרוע ביותר",
                    "detail": f"{worst_day:%d/%m/%Y} — {money(round(totals[worst_day], 2), currency)} "
                              f"על {trade_count(len(by_day[worst_day]))}."})

    green_run = _longest_day_run(totals, lambda amount: amount > 0)
    if len(green_run) >= 2:
        out.append({"שיא": "הרצף הירוק הארוך ביותר",
                    "detail": f"{len(green_run)} ימי מסחר ירוקים ברצף, "
                              f"{green_run[0]:%d/%m} עד {green_run[-1]:%d/%m}."})

    # Is the newest month the best one yet? This is the "first time" sentence, and it is only
    # worth saying when there is something behind it to beat.
    usable = [m for m in months if m["עסקאות"] >= MIN_WINDOW_TRADES]
    if len(usable) >= 2:
        values = [m["_expectancy"] for m in usable]
        if values[-1] == max(values):
            out.append({"שיא": "החודש הטוב ביותר שלך עד כה",
                        "detail": f"{usable[-1]['חודש']} — תוחלת {usable[-1]['תוחלת']} לעסקה, "
                                  f"הגבוהה מכל {len(usable) - 1} החודשים שלפניו."})

    return out


def _drawdown_story(rows, tz, currency):
    """The worst run down, as a span with dates - and what it started from.

    `max_drawdown` was already in the document as a single figure. **A figure says how bad;
    a span says when, for how long, and what preceded it** - and the last of those is the one
    a trader can act on, because a drawdown that begins the day after a record win is a story
    about size, not about the market.
    """
    peak = running = 0.0
    peak_at = rows[0]
    worst = {"amount": 0.0}

    for trade in rows:
        running += trade.pnl

        if running > peak:
            peak = running
            peak_at = trade

        fall = peak - running
        if fall > worst["amount"]:
            worst = {"amount": fall, "from": peak_at, "to": trade}

    if not worst["amount"]:
        return {"available": False, "reason": "אין דראודאון בהיסטוריה הזו."}

    start = worst["from"].executed_at.astimezone(tz)
    end = worst["to"].executed_at.astimezone(tz)
    # A list and not a set: **the chat's temporary document builds unsaved `Trade` objects**,
    # and an unsaved model instance has no primary key and is therefore unhashable. A set here
    # would have crashed the first time a trader attached a backtest, not in any test.
    span = [t for t in rows
            if worst["from"].executed_at <= t.executed_at <= worst["to"].executed_at]
    trading_days = len({t.executed_at.astimezone(tz).date() for t in span})

    detail = (f"מ-{start:%d/%m} עד {end:%d/%m} — {money(round(-worst['amount'], 2), currency)} "
              f"על פני {trading_days} ימי מסחר ו-{trade_count(len(span))}.")

    # What the peak itself was. A drawdown that starts right after the best day of the record
    # is a different conversation from one that starts in the middle of nothing.
    if worst["from"].pnl and worst["from"].pnl > 0:
        detail += (f" הוא התחיל מיד אחרי עסקה רווחית של "
                   f"{money(round(worst['from'].pnl, 2), currency)}.")

    return {"available": True, "detail": detail}


def _drift(recent, previous, tz, currency):
    """What moved between the two windows - the hour, the instrument, the setup.

    Not whether he is winning: **whether he is trading the same thing at all.** Drift is
    invisible in a lifetime aggregate by construction, because the aggregate contains both
    sides of it.
    """
    if len(recent) < MIN_WINDOW_TRADES or len(previous) < MIN_WINDOW_TRADES:
        return []

    out = []

    for label, of in (("השעה", lambda t: t.executed_at.astimezone(tz).hour),
                      ("הנכס", _instrument_of)):
        before = _dominant(previous, of)
        after = _dominant(recent, of)

        if before and after and before[0] != after[0]:
            out.append({
                "מה": label,
                "detail": f"{label} שבה סחרת הכי הרבה הייתה **{_pretty(label, before[0])}** "
                          f"({percent(before[1])} מהעסקאות), ועכשיו היא "
                          f"**{_pretty(label, after[0])}** ({percent(after[1])}).",
            })

    # Trade count per day is the drift that costs the most and is the easiest to miss.
    before_rate = _per_day(previous, tz)
    after_rate = _per_day(recent, tz)
    change = _relative(before_rate, after_rate)

    if change is not None and abs(change) >= MIN_RELATIVE_CHANGE:
        direction = "עלה" if after_rate > before_rate else "ירד"
        out.append({
            "מה": "קצב",
            "detail": f"מספר העסקאות ביום {direction} מ-{round(before_rate, 1)} "
                      f"ל-{round(after_rate, 1)}.",
        })

    return out


def _abandoned(rows, tz, currency):
    """Setups and instruments he used to trade and has not touched lately.

    **The hardest thing to notice about yourself is what you stopped doing** - it leaves no
    row anywhere, only a gap. Only profitable ones are reported: dropping a losing setup is
    the system working, and congratulating him on abandoning it would be noise.
    """
    newest = rows[-1].executed_at
    edge = newest - timedelta(days = RECENT_WINDOW_DAYS)

    out = []

    for field, label in (("setups", "הסטאפ"), (None, "הנכס")):
        buckets = defaultdict(list)
        for trade in rows:
            keys = _split_tags(getattr(trade, field)) if field else [_instrument_of(trade)]
            for key in keys:
                if key:
                    buckets[key].append(trade)

        for key, group in buckets.items():
            if len(group) < MIN_WINDOW_TRADES:
                continue

            last = max(t.executed_at for t in group)
            if last > edge:
                continue

            expectancy = _mean([t.pnl for t in group])
            if expectancy <= 0:
                continue

            gap = (newest - last).days
            out.append({
                "מה": f"{label} {clean_label(key)}",
                "detail": f"לא נגעת בו {day_count(gap)} — ובסך הכל הוא הניב לך "
                          f"{money(round(expectancy, 2), currency)} לעסקה על {trade_count(len(group))}.",
                "_rank": expectancy * len(group),
            })

    out.sort(key = lambda row: -row["_rank"])
    for row in out:
        row.pop("_rank")

    return out



# ------------- SMALL SHARED PIECES:
def _by_day(rows, tz):
    buckets = defaultdict(list)
    for trade in rows:
        buckets[trade.executed_at.astimezone(tz).date()].append(trade)
    return buckets


def _per_day(rows, tz):
    buckets = _by_day(rows, tz)
    return len(rows) / len(buckets) if buckets else 0.0


def _dominant(rows, of):
    """The most-traded value and what share of the window it held."""
    counts = defaultdict(int)
    for trade in rows:
        counts[of(trade)] += 1

    if not counts:
        return None

    top = max(counts, key = counts.get)
    return top, round(counts[top] / len(rows) * 100, 2)


def _pretty(label, value):
    return f"{int(value):02d}:00" if label == "השעה" else clean_label(value)


def _longest_day_run(totals, belongs):
    """The longest consecutive run of days that satisfy a condition."""
    best, current = [], []

    for day in sorted(totals):
        if belongs(totals[day]):
            if current and (day - current[-1]).days > 7:
                current = []
            current.append(day)
            if len(current) > len(best):
                best = list(current)
        else:
            current = []

    return best

# ------------------------- PERIODS END ------------------------- #
