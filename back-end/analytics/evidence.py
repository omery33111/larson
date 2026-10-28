from collections import defaultdict

from .formatting import money
from .statistics import (_instrument_of, _is_loss, _is_win, _split_tags, after_red_day_slices,
                         biggest_size_slice, busy_day_slices, clean_label, clean_note,
                         rated_slices, revenge_slices, _safe_zone)



# ------------------------- EVIDENCE START ------------------------- #
#
# **A number without an instance is a report; a number with one is a mentor.**
#
# Every finding already carried its sample size - "12 trades" - and that is the honest half.
# What it could not do was point: it said "revenge trading costs you $1,840 across 12 trades"
# and could not say "here, this one: 25/08 17:36, MNQ, 87 seconds, -$255". The trader reads
# the first and nods; he reads the second and remembers the trade.
#
# **The line itself is not new, and that matters.** `mentor/compliance.py` has named the
# offending trade since milestone 5 - it just pointed at the file that had only been
# confirmed, never at the record. `describe_trade` moved here and compliance imports it, so
# there is one definition of what a trade looks like when it is named.
#
# **And the trades are selected by the same functions the numbers come from**, never by a
# second copy of the rule. A finding whose example contradicts its own count has lost the
# argument before the trader finishes the sentence, and two copies of a predicate is exactly
# how that happens. `statistics.py` exposes the slices; this file only ranks and formats them.


EXAMPLES_PER_FINDING = 3



def describe_trade(trade, tz, currency):
    """One trade, named the way a trader would recognise it in his own journal."""
    when = trade.executed_at.astimezone(tz)

    # The ticker comes out of the file too, and this sentence is quoted to the model.
    line = f"{when:%d/%m} {when:%H:%M} · {clean_label(trade.symbol)}"

    if trade.duration_seconds is not None:
        line += (f" · {int(trade.duration_seconds)} שניות"
                 if trade.duration_seconds < 120
                 else f" · {round(trade.duration_seconds / 60)} דקות")

    if trade.pnl is not None:
        line += f" · {money(trade.pnl, currency)}"

    # **The two numbers the realised P&L hides.** MFE is how far into profit the trade ran,
    # MAE how far underwater it went first; quoted on the trade itself so Larson can say
    # "this one was +$331 before you booked $144" instead of only the $144.
    #
    # A derived figure (the file gave prices, not money) is marked, so the model never quotes
    # an estimate with the certainty of a measured value.
    if getattr(trade, "mfe", None) is not None or getattr(trade, "mae", None) is not None:
        mark = " (מוערך)" if getattr(trade, "excursion_estimated", False) else ""
        if getattr(trade, "mfe", None) is not None:
            line += f" · שיא {money(trade.mfe, currency)}{mark}"
        if getattr(trade, "mae", None) is not None:
            line += f" · שפל {money(trade.mae, currency)}{mark}"

    # **His own words, on the trade they were written about.**
    #
    # `notes` sat in the database and in the data export and reached no prompt at all, which
    # made the most human field in the file the one Larson was blind to. It arrives here
    # rather than as a list of its own because a note is only worth anything **attached to
    # the trade it describes** - "I was tired, revenge after the morning loss" means nothing
    # floating in a block of its own, and everything beside 87 seconds and -$255.
    #
    # Cleaned on the way through, and that is not optional: this is unbounded free text out
    # of a spreadsheet, and the one field a downloaded template would most plausibly use to
    # smuggle something into the prompt.
    if trade.notes:
        note = clean_note(trade.notes)
        if note:
            line += f" — \"{note}\""

    return line



def attach_examples(findings, trades, currency = "USD", timezone_name = "Asia/Jerusalem",
                    worst_first = True):
    """
    Each finding gains `examples`: up to three of its own instances, named.

    `worst_first` is the only difference between the two shoulders. A leak is argued with the
    trades that cost the most, and a strength with the ones that paid - **the same selector,
    ranked from the other end.** Findings with nothing to point at are returned untouched
    rather than given an empty list, so the prompt never carries "examples: []" as if the
    absence meant something.
    """
    if not trades:
        return findings

    tz = _safe_zone(timezone_name, trades)
    ordered = sorted(trades, key = lambda t: t.executed_at)

    for finding in findings:
        picked = _instances(finding, ordered, tz)
        if not picked:
            continue

        # Money decides which three, time decides how they are read: a trader scanning three
        # lines expects them in the order they happened.
        picked.sort(key = lambda t: (t.pnl if t.pnl is not None else 0.0),
                    reverse = not worst_first)
        chosen = sorted(picked[:EXAMPLES_PER_FINDING], key = lambda t: t.executed_at)

        finding["examples"] = [describe_trade(t, tz, currency) for t in chosen]

        # **The count is stated next to the three, not implied by them.** Three lines out of
        # seventy-six read as "it happened three times" unless the sentence says otherwise,
        # and understating a habit is the one direction this feature must not fail in.
        finding["examples_of"] = len(picked)

    return findings



# ------------- WHICH TRADES BELONG TO WHICH FINDING:
#
# Keyed by the finding's `key`. The group-based findings also carry `subject` - the hour, the
# setup, the ticker - because the group key is otherwise only inside the title prose, and
# parsing a sentence to find out which hour it meant is the kind of thing that works until
# somebody rewrites the sentence.
def _instances(finding, trades, tz):
    key = finding.get("key")
    subject = finding.get("subject")

    if key == "revenge":
        return list(revenge_slices(trades)[0])

    if key == "after_red_day":
        return list(after_red_day_slices(trades, tz)[0])

    if key == "overtrading":
        slices = busy_day_slices(trades, tz)
        return list(slices[0]) if slices else []

    if key == "mistake_tax":
        return [t for t in trades if t.mistakes]

    if key == "worst_mistake":
        return _tagged(trades, "mistakes", subject)

    if key in ("worst_setup", "best_setup"):
        return _tagged(trades, "setups", subject)

    if key in ("worst_hour", "best_hour"):
        return [t for t in trades if t.executed_at.astimezone(tz).hour == subject]

    if key == "best_symbol":
        return [t for t in trades if _instrument_of(t) == subject]

    if key == "best_direction":
        return [t for t in trades if t.direction == subject]

    if key == "size_discipline":
        sizes = [t.quantity for t in trades if t.quantity]
        return list(biggest_size_slice(trades)[1]) if sizes else []

    if key == "hold_time":
        # The leak is sitting in losers; the strength is letting winners run. Either way the
        # instance worth showing is the longest-held trade on the relevant side.
        side = [t for t in trades
                if t.duration_seconds and (_is_loss(t) if _holds_losers(finding) else _is_win(t))]
        return sorted(side, key = lambda t: -t.duration_seconds)[:EXAMPLES_PER_FINDING]

    if key == "self_awareness":
        return _miscalled(trades, finding)

    if key == "loss_streak":
        return _longest_streak(trades, _is_loss)

    if key == "worst_day":
        return _extreme_day(trades, tz, worst = True)

    if key == "green_days":
        return _extreme_day(trades, tz, worst = False)

    if key == "payoff":
        # One of each, because the finding is about the gap between them.
        wins = [t for t in trades if _is_win(t) and t.pnl is not None]
        losses = [t for t in trades if _is_loss(t) and t.pnl is not None]
        picked = []
        if wins:
            picked.append(max(wins, key = lambda t: t.pnl))
        if losses:
            picked.append(min(losses, key = lambda t: t.pnl))
        return picked

    return []


def _holds_losers(finding):
    """The two hold-time findings share a key and sit on opposite shoulders."""
    return "מחזיק מפסידות" in finding.get("title", "")


def _tagged(trades, field, subject):
    """Trades carrying one label out of a comma-separated cell, compared after cleaning.

    The subject arrived from `_group_stats`, which cleans; `_split_tags` cleans too. Matching
    raw against cleaned would silently find nothing on any label that needed cleaning.
    """
    if not subject:
        return []
    return [t for t in trades if subject in _split_tags(getattr(t, field))]


def _miscalled(trades, finding):
    """The rated trades that most contradicted their own rating."""
    rated = [t for t in trades if t.rating is not None and t.pnl is not None]
    if len(rated) < 2:
        return []

    high, low, _ = rated_slices(rated)

    # Uncalibrated: the ones he liked and lost on. Calibrated: the ones he liked and won on -
    # the proof that his read is worth something.
    if "לא מנבא" in finding.get("title", ""):
        return [t for t in high if _is_loss(t)]

    return [t for t in high if _is_win(t)]


def _longest_streak(trades, belongs):
    """The actual trades of the longest run, not a count of them."""
    best, current = [], []

    for trade in trades:
        if belongs(trade):
            current.append(trade)
            if len(current) > len(best):
                best = list(current)
        else:
            current = []

    return best


def _extreme_day(trades, tz, worst = True):
    """Every trade of the single best or worst day."""
    days = defaultdict(list)
    for trade in trades:
        days[trade.executed_at.astimezone(tz).date()].append(trade)

    if not days:
        return []

    totals = {day: sum(t.pnl for t in rows if t.pnl is not None) for day, rows in days.items()}
    chosen = min(totals, key = totals.get) if worst else max(totals, key = totals.get)

    return days[chosen]

# ------------------------- EVIDENCE END ------------------------- #
