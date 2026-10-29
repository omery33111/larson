import statistics as stats_lib
from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from trades.symbols import instrument_label

from .formatting import money, percent, ratio as ratio_text



# ------------------------- STATISTICS ENGINE START ------------------------- #
#
# One function computes everything, at request time, from the trades table. There is no
# pre-computed aggregate table and no invalidation mechanism - the numbers can never be
# stale because they are never stored.
#
# Everything below is deterministic. The model is never asked to compute a number; it is
# handed this JSON and asked to write about it.


# A finding needs a floor of trades before it means anything. These are the thresholds at
# which a breakdown stops being noise.
MIN_TRADES_FOR_BREAKDOWN = 5
MIN_TRADES_FOR_PROFILE = 20

# Two trades inside this window, after a loss, is the signature of a revenge trade.
REVENGE_WINDOW_MINUTES = 30

WIN = "win"
LOSS = "loss"
BREAKEVEN = "breakeven"


def _outcome(trade):
    """
    How a trade is counted.

    The stored outcome wins, because it came from the trader's own journal and reflects the
    breakeven range they configured there. Only a trade the pipeline could not classify falls
    back to the sign of its P&L.
    """
    recorded = getattr(trade, "outcome", None)

    if recorded in (WIN, LOSS, BREAKEVEN):
        return recorded

    if trade.pnl is None:
        return BREAKEVEN

    return WIN if trade.pnl > 0 else LOSS if trade.pnl < 0 else BREAKEVEN


def _is_win(trade):
    return _outcome(trade) == WIN


def _is_loss(trade):
    return _outcome(trade) == LOSS



def compute_statistics(trades, timezone_name = "Asia/Jerusalem"):
    """
    trades - an iterable of Trade rows, any order.
    Returns the full statistics document that feeds both the profile page and the prompt.
    """
    trades = [t for t in trades if t.pnl is not None]
    trades.sort(key = lambda t: t.executed_at)

    if not trades:
        return {"total_trades": 0, "has_enough_data": False}

    tz = _safe_zone(timezone_name, trades)

    # The scratch band this trader actually works with, used for days and for any trade the
    # source file did not label.
    flat_band = _flat_band(trades)

    currency = _currency(trades)

    core = _core_metrics(trades)
    daily = _daily_metrics(trades, tz, flat_band)
    streaks = _streaks(trades)
    behaviour = _behavioural_metrics(trades, tz)
    excursion = _excursion_metrics(trades)

    breakdowns = {
        "by_hour": _breakdown(trades, lambda t: t.executed_at.astimezone(tz).hour),
        "by_weekday": _breakdown(trades, lambda t: t.executed_at.astimezone(tz).weekday()),
        # Grouped by the chart, not by the contract month. Without this a trader who rolls
        # every quarter looks like someone who trades four unrelated instruments badly.
        "by_symbol": _breakdown(trades, _instrument_of, label = instrument_label),
        "by_direction": _breakdown(trades, lambda t: t.direction),
        "by_setup": _breakdown_multi(trades, lambda t: _split_tags(t.setups)),
        "by_tag": _breakdown_multi(trades, lambda t: _split_tags(t.tags)),
        "by_mistake": _breakdown_multi(trades, lambda t: _split_tags(t.mistakes)),
        "by_duration": _breakdown(trades, _duration_bucket),
    }

    score = compute_score(core, daily, behaviour, streaks, currency)

    return {
        "total_trades": len(trades),
        "has_enough_data": len(trades) >= MIN_TRADES_FOR_PROFILE,
        "min_trades_for_profile": MIN_TRADES_FOR_PROFILE,
        "timezone": str(tz),
        "currency": currency,
        "date_from": trades[0].executed_at,
        "date_to": trades[-1].executed_at,
        "accounts": sorted({clean_label(t.account_id) for t in trades if t.account_id}),
        "flat_band": round(flat_band, 2),
        "outcome_from_file": sum(1 for t in trades
                                 if getattr(t, "outcome", None) in (WIN, LOSS, BREAKEVEN)),
        "core": core,
        "daily": daily,
        "streaks": streaks,
        "behaviour": behaviour,
        "excursion": excursion,
        "breakdowns": breakdowns,
        "score": score,
    }



# ------------- CORE METRICS:
def _core_metrics(trades):
    pnls = [t.pnl for t in trades]

    # Classified by the recorded outcome. A scratch stays a scratch even though its P&L is
    # a few dollars either side of zero, which is exactly what the journal meant by "BE".
    wins = [t.pnl for t in trades if _outcome(t) == WIN]
    losses = [t.pnl for t in trades if _outcome(t) == LOSS]
    breakeven = [t.pnl for t in trades if _outcome(t) == BREAKEVEN]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    # Breakeven trades still move money - a scratch at -2.50 costs 2.50 - so they stay in
    # net_pnl and expectancy. They are only excluded from the win/loss counts.

    avg_win = _mean(wins)
    avg_loss = abs(_mean(losses))

    # Decided trades only. Counting breakeven trades as losses would understate a trader
    # who scratches often, which is the opposite of what scratching means.
    decided = len(wins) + len(losses)
    win_rate = (len(wins) / decided * 100) if decided else 0.0

    r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]

    return {
        "net_pnl": round(sum(pnls), 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),

        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),

        "win_rate": round(win_rate, 2),
        # Profit factor is undefined without a loss; None is honest, 999 is not.
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,

        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "win_loss_ratio": round(avg_win / avg_loss, 2) if avg_loss else None,

        # What one trade is worth on average - the number that actually compounds.
        "expectancy": round(sum(pnls) / len(pnls), 2),

        "largest_win": round(max(pnls), 2),
        "largest_loss": round(min(pnls), 2),

        "max_drawdown": round(_max_drawdown(pnls), 2),
        "avg_r": round(_mean(r_multiples), 2) if r_multiples else None,
        "r_coverage": len(r_multiples),
    }


def _max_drawdown(pnls):
    """Largest peak-to-trough drop of the cumulative P&L curve."""
    equity = 0.0
    peak = 0.0
    drawdown = 0.0

    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)

    return abs(drawdown)



# ------------- DAILY METRICS:
def _daily_metrics(trades, tz, flat_band = 0.0):
    days = defaultdict(list)
    for t in trades:
        days[t.executed_at.astimezone(tz).date()].append(t.pnl)

    day_pnls = {day: sum(pnls) for day, pnls in days.items()}
    values = list(day_pnls.values())

    # A day that ends within the trader's own scratch band did not really go either way.
    # Requiring an exact zero would make flat days practically impossible and push every
    # near-nothing day into the red column.
    green = [v for v in values if v > flat_band]
    red = [v for v in values if v < -flat_band]
    flat = [v for v in values if abs(v) <= flat_band]

    decided_days = len(green) + len(red)

    trades_per_day = [len(pnls) for pnls in days.values()]

    return {
        "trading_days": len(days),
        "green_days": len(green),
        "red_days": len(red),
        "flat_days": len(flat),
        "green_day_rate": round(len(green) / decided_days * 100, 2) if decided_days else 0.0,
        "avg_green_day": round(_mean(green), 2),
        "avg_red_day": round(abs(_mean(red)), 2),
        "best_day": round(max(values), 2),
        "worst_day": round(min(values), 2),
        "avg_trades_per_day": round(_mean(trades_per_day), 2),
        "max_trades_in_a_day": max(trades_per_day),
        # Standard deviation of daily results - the raw material of the consistency score.
        "daily_stdev": round(stats_lib.pstdev(values), 2) if len(values) > 1 else 0.0,
    }



# ------------- STREAKS:
def _streaks(trades):
    best_win = best_loss = current = 0
    current_kind = None

    for t in trades:
        outcome = _outcome(t)

        if outcome == WIN:
            kind = "win"
        elif outcome == LOSS:
            kind = "loss"
        else:
            # A scratch neither extends nor breaks a streak.
            continue

        if kind == current_kind:
            current += 1
        else:
            current_kind, current = kind, 1

        if kind == "win":
            best_win = max(best_win, current)
        else:
            best_loss = max(best_loss, current)

    return {
        "longest_win_streak": best_win,
        "longest_loss_streak": best_loss,
        "current_streak": current,
        "current_streak_kind": current_kind or "none",
    }



# ------------- BEHAVIOURAL METRICS:
# These are the numbers a trader cannot see by scrolling their own journal, because each
# one is a comparison between two slices of their history rather than a column in it.
def _behavioural_metrics(trades, tz):
    return {
        "revenge": _revenge_trading(trades),
        "after_red_day": _after_red_day(trades, tz),
        "overtrading": _overtrading(trades, tz),
        "hold_time": _hold_time_asymmetry(trades),
        "mistake_tax": _mistake_tax(trades),
        "self_awareness": _self_awareness(trades),
        "size_discipline": _size_discipline(trades),
    }


# ------------- EXCURSION (MFE / MAE):
#
# **What the realised P&L cannot say: not whether the trade won, but how much was on the
# table and how much heat it took.** MFE is the best unrealised profit the trade reached,
# MAE the worst unrealised loss - both in money, both folded to a fixed sign at parse time
# (MFE non-negative, MAE non-positive).
#
# The number that pays for the whole block is the capture rate: on his winners, how much of
# the peak profit he actually kept. A trader who reaches +$300 on nearly every trade and
# books a tenth of it does not have a win-rate problem, he has an exit problem - and no
# metric built on realised P&L can see it, because the money he left behind was never
# realised. Everything here is computed in python; the model only quotes it.
def _excursion_metrics(trades):
    mfe_trades = [t for t in trades if t.mfe is not None]
    mae_trades = [t for t in trades if t.mae is not None]

    if not mfe_trades and not mae_trades:
        return {"available": False}

    # Of the peak profit reached on winners, how much was booked. Aggregated over the pool
    # rather than averaged per trade, so one tiny-MFE winner cannot swing the ratio.
    winners = [t for t in mfe_trades if _is_win(t) and t.mfe and t.mfe > 0 and t.pnl is not None]
    captured_from = sum(t.mfe for t in winners)
    capture_rate = (sum(t.pnl for t in winners) / captured_from * 100) if captured_from else None

    # How far underwater a winning trade went before it came good - the heat he sat through.
    winner_heat = [abs(t.mae) for t in trades if _is_win(t) and t.mae is not None]

    # Money that was on the table and walked away, per trade that reached a peak.
    give_back = [t.mfe - t.pnl for t in mfe_trades if t.pnl is not None and t.mfe is not None]

    return {
        "available": True,
        "mfe_coverage": len(mfe_trades),
        "mae_coverage": len(mae_trades),
        "avg_mfe": round(_mean([t.mfe for t in mfe_trades]), 2) if mfe_trades else None,
        "avg_mae": round(_mean([t.mae for t in mae_trades]), 2) if mae_trades else None,
        # Percent of the peak kept on winners. Low means tight targets would raise the win
        # rate; near 100 means he exits at the high and the edge is elsewhere.
        "capture_rate_on_winners": round(capture_rate, 2) if capture_rate is not None else None,
        "winners_measured": len(winners),
        "avg_heat_on_winners": round(_mean(winner_heat), 2) if winner_heat else None,
        "avg_left_on_table": round(_mean(give_back), 2) if give_back else None,
        # How many of the contributing rows were derived from the price path rather than read
        # as money. Lets the model temper its certainty when the block leans on estimates.
        "estimated_rows": sum(1 for t in mfe_trades if getattr(t, "excursion_estimated", False)),
    }


# ------------- WHICH TRADES, AS OPPOSED TO HOW MANY:
#
# **Each behavioural metric is a comparison between two slices, and the slices are now named
# functions rather than locals.** The reason is `evidence.py`: a finding that says "revenge
# trading cost you $1,840 across 12 trades" is now shown with three of those twelve, by name.
#
# **If the examples were selected by a second copy of the rule, the two could disagree** -
# and a mentor whose example contradicts its own number has lost the argument before the
# trader finishes reading. One definition, both callers, no drift possible. This is the same
# rule the IRON block is defined once for.


def revenge_slices(trades):
    """(revenge, normal) - a trade opened soon after closing a loser, and everything else."""
    revenge, normal = [], []

    for previous, current in zip(trades, trades[1:]):
        opened = current.opened_at or current.executed_at
        gap = (opened - previous.executed_at).total_seconds() / 60

        if _is_loss(previous) and 0 <= gap <= REVENGE_WINDOW_MINUTES:
            revenge.append(current)
        else:
            normal.append(current)

    return revenge, normal


def _revenge_trading(trades):
    """A trade opened soon after closing a loser, compared with everything else."""
    revenge, normal = revenge_slices(trades)

    return _comparison("עסקאות נקמה", revenge, normal,
                       f"עסקה שנפתחה תוך {REVENGE_WINDOW_MINUTES} דקות מסגירת הפסד")


def after_red_day_slices(trades, tz):
    """(after a losing day, after a winning day)."""
    days = defaultdict(list)
    for t in trades:
        days[t.executed_at.astimezone(tz).date()].append(t)

    ordered = sorted(days.items())
    after_red, after_green = [], []

    for (_, previous_trades), (_, next_trades) in zip(ordered, ordered[1:]):
        if sum(t.pnl for t in previous_trades) < 0:
            after_red.extend(next_trades)
        else:
            after_green.extend(next_trades)

    return after_red, after_green


def _after_red_day(trades, tz):
    """Whether a losing day changes how the next day is traded."""
    after_red, after_green = after_red_day_slices(trades, tz)

    result = _comparison("מסחר אחרי יום אדום", after_red, after_green,
                         "העסקאות ביום שאחרי יום הפסד, מול יום שאחרי יום רווח")

    # Position size is the tell here: bigger size after a red day is chasing.
    result["avg_size_after_red"] = round(_mean([t.quantity for t in after_red if t.quantity]), 2)
    result["avg_size_after_green"] = round(_mean([t.quantity for t in after_green if t.quantity]), 2)

    return result


def busy_day_slices(trades, tz):
    """(busy-day trades, the rest, threshold, median) - or None when there is nothing."""
    days = defaultdict(list)
    for t in trades:
        days[t.executed_at.astimezone(tz).date()].append(t)

    counts = [len(v) for v in days.values()]
    if not counts:
        return None

    median = stats_lib.median(counts)
    threshold = max(median + 1, 2)

    busy, calm = [], []
    for day_trades in days.values():
        (busy if len(day_trades) > threshold else calm).extend(day_trades)

    return busy, calm, threshold, median


def _overtrading(trades, tz):
    """Compares days with an unusually high trade count against the rest."""
    slices = busy_day_slices(trades, tz)
    if not slices:
        return {"available": False}

    busy, calm, threshold, median = slices

    result = _comparison("ימים עמוסים", busy, calm,
                         f"ימים עם יותר מ-{int(threshold)} עסקאות, מול שאר הימים")
    result["threshold"] = int(threshold)
    result["median_trades_per_day"] = median

    return result


def _hold_time_asymmetry(trades):
    """Cutting winners early while sitting in losers is the classic asymmetry."""
    wins = [t.duration_seconds for t in trades if _is_win(t) and t.duration_seconds]
    losses = [t.duration_seconds for t in trades if _is_loss(t) and t.duration_seconds]

    if not wins or not losses:
        return {"available": False}

    avg_win = _mean(wins)
    avg_loss = _mean(losses)

    return {
        "available": True,
        "avg_win_minutes": round(avg_win / 60, 1),
        "avg_loss_minutes": round(avg_loss / 60, 1),
        "ratio": round(avg_win / avg_loss, 2) if avg_loss else None,
        # Holding losers longer than winners is the direction that costs money.
        "holds_losers_longer": avg_loss > avg_win,
    }


def _mistake_tax(trades):
    """What the trades the trader themselves flagged as mistakes actually cost."""
    flagged = [t for t in trades if t.mistakes]
    clean = [t for t in trades if not t.mistakes]

    if not flagged:
        return {"available": False, "coverage": 0}

    result = _comparison("עסקאות עם טעות מתועדת", flagged, clean,
                         "עסקאות שסימנת בעצמך כטעות, מול השאר")
    result["coverage"] = len(flagged)
    result["total_cost"] = round(sum(t.pnl for t in flagged), 2)

    return result


def rated_slices(rated):
    """(above the median rating, at or below it, the median)."""
    median = stats_lib.median([t.rating for t in rated])
    return ([t for t in rated if t.rating > median],
            [t for t in rated if t.rating <= median],
            median)


def _self_awareness(trades):
    """Does the trader's own rating actually predict the outcome?"""
    rated = [t for t in trades if t.rating is not None]
    if len(rated) < MIN_TRADES_FOR_BREAKDOWN:
        return {"available": False}

    high, low, median = rated_slices(rated)

    if not high or not low:
        return {"available": False}

    high_expectancy = _mean([t.pnl for t in high])
    low_expectancy = _mean([t.pnl for t in low])

    return {
        "available": True,
        "rated_trades": len(rated),
        "median_rating": median,
        "high_rated_expectancy": round(high_expectancy, 2),
        "low_rated_expectancy": round(low_expectancy, 2),
        # If the trades the trader liked did better, their read on themselves is calibrated.
        "is_calibrated": high_expectancy > low_expectancy,
        "gap": round(high_expectancy - low_expectancy, 2),
    }


def biggest_size_slice(trades):
    """(the largest quantity traded, every trade that carried it)."""
    biggest = max(t.quantity for t in trades if t.quantity)
    return biggest, [t for t in trades if t.quantity == biggest]


def _size_discipline(trades):
    """How much position size varies - a proxy for whether risk is fixed or emotional."""
    sizes = [t.quantity for t in trades if t.quantity]
    if len(sizes) < MIN_TRADES_FOR_BREAKDOWN:
        return {"available": False}

    mean_size = _mean(sizes)
    if not mean_size:
        return {"available": False}

    variation = stats_lib.pstdev(sizes) / mean_size

    biggest, biggest_trades = biggest_size_slice(trades)

    return {
        "available": True,
        "avg_size": round(mean_size, 2),
        "max_size": biggest,
        # Coefficient of variation. Under ~0.25 reads as a fixed-risk trader.
        "size_variation": round(variation, 2),
        "is_consistent": variation < 0.25,
        "biggest_size_expectancy": round(_mean([t.pnl for t in biggest_trades]), 2),
    }


def _comparison(name, subset, rest, description):
    """Shared shape for 'this slice versus the rest' findings."""
    subset_pnls = [t.pnl for t in subset]
    rest_pnls = [t.pnl for t in rest]
    subset_wins = sum(1 for t in subset if _is_win(t))
    rest_wins = sum(1 for t in rest if _is_win(t))

    if not subset_pnls or not rest_pnls:
        return {"available": False, "name": name, "description": description, "count": len(subset_pnls)}

    subset_expectancy = _mean(subset_pnls)
    rest_expectancy = _mean(rest_pnls)

    return {
        "available": True,
        "name": name,
        "description": description,
        "count": len(subset_pnls),
        "rest_count": len(rest_pnls),
        "expectancy": round(subset_expectancy, 2),
        "rest_expectancy": round(rest_expectancy, 2),
        "total_pnl": round(sum(subset_pnls), 2),
        "win_rate": round(subset_wins / len(subset_pnls) * 100, 2),
        "rest_win_rate": round(rest_wins / len(rest_pnls) * 100, 2),
        "gap": round(subset_expectancy - rest_expectancy, 2),
        "is_worse": subset_expectancy < rest_expectancy,
        "is_significant": len(subset_pnls) >= MIN_TRADES_FOR_BREAKDOWN,
    }



# ------------- BREAKDOWNS:
def _instrument_of(trade):
    """Falls back to the raw ticker for rows ingested before instruments were derived."""
    return getattr(trade, "instrument", None) or trade.symbol


def _breakdown(trades, key_function, label = None):
    groups = defaultdict(list)
    for t in trades:
        key = key_function(t)
        if key is not None and key != "":
            groups[key].append(t)

    return [_group_stats(key, group, label)
            for key, group in sorted(groups.items(), key = lambda kv: str(kv[0]))]


def _breakdown_multi(trades, keys_function):
    """For comma-separated columns, where one trade belongs to several buckets."""
    groups = defaultdict(list)
    for t in trades:
        for key in keys_function(t):
            groups[key].append(t)

    ordered = sorted(groups.items(), key = lambda kv: -len(kv[1]))
    return [_group_stats(key, group) for key, group in ordered]


def _group_stats(key, group, label = None):
    pnls = [t.pnl for t in group]
    wins = [t.pnl for t in group if _is_win(t)]
    losses = [t.pnl for t in group if _is_loss(t)]
    decided = len(wins) + len(losses)

    stats = {
        # Cleaned here rather than at each caller, because this is the one place every
        # breakdown passes through - hours and weekdays included, which are numbers and are
        # left alone.
        "key": clean_label(key) if isinstance(key, str) else key,
        # A recognisable name for the chart when we have one, the ticker itself otherwise.
        "label": label(key) if label else None,
        "trades": len(group),
        "net_pnl": round(sum(pnls), 2),
        "expectancy": round(sum(pnls) / len(pnls), 2),
        "win_rate": round(len(wins) / decided * 100, 2) if decided else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) else None,
        # Below the floor a breakdown is an anecdote, and the UI greys it out.
        "is_significant": len(group) >= MIN_TRADES_FOR_BREAKDOWN,
    }

    # **Entry quality, when the file carried the price path.** MAE is the heat a bucket took on
    # average before it worked, MFE how far it ran - so "was my entry optimal on this setup" is
    # a number here and not a guess. Added only when MFE/MAE exist, so a journal without them
    # grows the bucket by nothing.
    maes = [t.mae for t in group if getattr(t, "mae", None) is not None]
    mfes = [t.mfe for t in group if getattr(t, "mfe", None) is not None]
    if maes:
        stats["avg_mae"] = round(sum(maes) / len(maes), 2)
    if mfes:
        stats["avg_mfe"] = round(sum(mfes) / len(mfes), 2)

    return stats


# A label is meant to be a few words a trader typed into a column: "breakout", "fomo",
# "revenge entry". **Nothing about the file guarantees that**, and whatever is in that cell
# becomes a key in the statistics document, which is handed to the model inside the system
# prompt and printed on the screen.
#
# Both of those break on a long one, and one of them breaks badly: a cell holding several
# lines of prose arrives in the system block verbatim, newlines and headings intact, which is
# a place for instructions rather than data. Proved against the real prompt builder with a
# setup column carrying a blank line and then a heading that ordered the model to ignore
# its instructions - it landed whole, at the highest authority the request has.
#
# **The fix is what a label already is**: one line, no runs of whitespace, and short. Nothing
# a real journal writes is touched by this; the uploaded file is stored untouched either way,
# so nothing is lost that a re-ingestion could not recover.
MAX_LABEL_LENGTH = 80

# **A note is the same contract with more room, and the room is the whole difference.**
#
# `notes` is the trader's own sentence about a trade - "I was tired, this was revenge after
# the morning loss" - and it is the single most human field in the file. Cut to 80 characters
# it stops being a sentence, which is why it needs its own ceiling rather than the label one.
#
# What it does **not** get is its own cleaning rule. One line and no runs of whitespace is
# what stops a cell from forging a heading inside the prompt, and that is as necessary for a
# paragraph as for a tag - more so, because a note is the field a downloaded journal template
# would most plausibly hide something in. The ceiling changes; the collapsing does not.
MAX_NOTE_LENGTH = 300


def clean_label(value, limit = MAX_LABEL_LENGTH):
    """One line, collapsed, and bounded. Returns "" for anything that had no content."""
    text = " ".join(str(value).split())

    if len(text) > limit:
        text = text[:limit].rstrip() + "…"

    return text


def clean_note(value):
    """The trader's own sentence, made safe to put in a prompt without being made useless."""
    return clean_label(value, limit = MAX_NOTE_LENGTH)


def _split_tags(value):
    if not value:
        return []
    return [label for label in (clean_label(part) for part in str(value).split(",")) if label]


def _duration_bucket(trade):
    seconds = trade.duration_seconds
    if seconds is None:
        return None
    if seconds < 120:
        return "עד 2 דקות"
    if seconds < 600:
        return "2-10 דקות"
    if seconds < 1800:
        return "10-30 דקות"
    if seconds < 3600:
        return "30-60 דקות"
    return "מעל שעה"



# ------------------------- THE SCORE START ------------------------- #
#
# A single 0-100 number, built from five pillars that are scored separately and then
# weighted. Every pillar is visible on its own, because a single number that cannot be
# taken apart is not feedback - it is a verdict.

SCORE_WEIGHTS = {
    "profitability": 0.25,
    "risk": 0.20,
    "consistency": 0.20,
    "discipline": 0.20,
    "execution": 0.15,
}

PILLAR_LABELS = {
    "profitability": "רווחיות",
    "risk": "ניהול סיכון",
    "consistency": "עקביות",
    "discipline": "משמעת",
    "execution": "איכות ביצוע",
}


def compute_score(core, daily, behaviour, streaks, currency = "USD"):
    pillars = {
        "profitability": _score_profitability(core),
        "risk": _score_risk(core, daily, currency),
        "consistency": _score_consistency(core, daily),
        "discipline": _score_discipline(behaviour, streaks),
        "execution": _score_execution(core, behaviour),
    }

    total = sum(pillars[name]["value"] * weight for name, weight in SCORE_WEIGHTS.items())

    return {
        "total": round(total),
        "grade": _grade(total),
        "pillars": [
            {
                "key": name,
                "label": PILLAR_LABELS[name],
                "value": round(pillars[name]["value"]),
                "weight": round(SCORE_WEIGHTS[name] * 100),
                "detail": pillars[name]["detail"],
            }
            for name in SCORE_WEIGHTS
        ],
    }


def _score_profitability(core):
    """Anchored on profit factor: 1.0 is breakeven, 2.0 is a genuinely strong edge."""
    pf = core["profit_factor"]

    if pf is None:
        value = 100.0 if core["net_pnl"] > 0 else 50.0
    else:
        value = _scale(pf, low = 0.75, high = 2.0)

    return {"value": value, "detail": f"פקטור רווח {ratio_text(pf)}"}


def _score_risk(core, daily, currency = "USD"):
    """
    Recovery factor - net profit divided by the deepest drawdown that produced it.

    Gross profit is deliberately not the reference here. A trader with a high payoff ratio
    accumulates a large gross profit even while netting almost nothing, which would hide a
    drawdown that actually swallowed the entire result. Recovery factor is the industry
    measure precisely because it compares the drawdown to what was kept, not to what was won.
    """
    drawdown = core["max_drawdown"]

    if drawdown <= 0:
        # No drawdown at all - either a very short history or a genuinely clean run.
        return {"value": 100.0 if core["net_pnl"] > 0 else 50.0,
                "detail": "לא נרשם דראודאון"}

    recovery_factor = core["net_pnl"] / drawdown

    # Below 1 the drawdown was deeper than everything kept; 3 and up is a robust edge.
    value = _scale(recovery_factor, low = 0.0, high = 3.0)

    # A day far outside the normal losing day means there is no daily stop in place.
    if daily["avg_red_day"] and abs(daily["worst_day"]) > daily["avg_red_day"] * 3:
        value = min(value, 60.0)

    return {
        "value": value,
        "detail": f"יחס התאוששות {ratio_text(recovery_factor)} — "
                  f"רווח נקי {money(core['net_pnl'], currency)} מול דראודאון של "
                  f"{money(drawdown, currency)}",
    }


def _score_consistency(core, daily):
    """Are results spread across many days, or carried by a handful of outliers?"""
    if daily["trading_days"] < 3:
        return {"value": 50.0, "detail": "אין מספיק ימי מסחר"}

    green_component = _scale(daily["green_day_rate"], low = 30.0, high = 65.0)

    # How much of the whole result rests on the single best day.
    reference = max(abs(core["net_pnl"]), core["gross_profit"], 1)
    concentration = abs(daily["best_day"]) / reference
    concentration_component = _scale(1 - concentration, low = 0.3, high = 0.9)

    value = green_component * 0.6 + concentration_component * 0.4

    return {"value": value, "detail": f"{percent(daily['green_day_rate'])} ימים ירוקים"}


def _score_discipline(behaviour, streaks):
    """Built from the behavioural leaks, each of which subtracts from a clean slate."""
    value = 100.0
    notes = []

    revenge = behaviour["revenge"]
    if revenge.get("available") and revenge.get("is_significant") and revenge["is_worse"]:
        value -= 25
        notes.append("עסקאות נקמה")

    mistakes = behaviour["mistake_tax"]
    if mistakes.get("available") and mistakes.get("is_significant") and mistakes["is_worse"]:
        value -= 20
        notes.append("טעויות מתועדות")

    overtrading = behaviour["overtrading"]
    if overtrading.get("available") and overtrading.get("is_significant") and overtrading["is_worse"]:
        value -= 20
        notes.append("ימים עמוסים")

    size = behaviour["size_discipline"]
    if size.get("available") and not size["is_consistent"]:
        value -= 15
        notes.append("גודל פוזיציה משתנה")

    after_red = behaviour["after_red_day"]
    if after_red.get("available") and after_red.get("is_significant") and after_red["is_worse"]:
        value -= 10
        notes.append("מסחר אחרי יום אדום")

    if streaks["longest_loss_streak"] >= 6:
        # A long losing run without stopping is a missing circuit breaker.
        value -= 10
        notes.append(f"רצף {streaks['longest_loss_streak']} הפסדים")

    return {
        "value": max(value, 0.0),
        "detail": "נמצאו: " + "; ".join(notes) if notes else "לא נמצאו דליפות משמעת",
    }


def _score_execution(core, behaviour):
    """Trade craft: the size of a win against the size of a loss, and how each is held."""
    ratio = core["win_loss_ratio"]
    value = _scale(ratio, low = 0.7, high = 3.0) if ratio else 50.0

    hold = behaviour["hold_time"]
    if hold.get("available") and hold["holds_losers_longer"]:
        # Sitting in losers longer than winners is the most expensive habit in trading.
        value -= 20

    return {
        "value": max(min(value, 100.0), 0.0),
        "detail": f"יחס רווח/הפסד ממוצע {ratio_text(ratio)} לטובתך",
    }


def _scale(value, low, high):
    """Maps a raw metric onto 0-100 with a linear ramp between two anchors."""
    if value is None:
        return 50.0
    if high == low:
        return 50.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100))


def _grade(total):
    if total >= 85:
        return "מצוין"
    if total >= 70:
        return "טוב"
    if total >= 55:
        return "סביר"
    if total >= 40:
        return "טעון שיפור"
    return "בעייתי"

# ------------------------- THE SCORE END ------------------------- #



# ------------- HELPERS:
def _currency(trades):
    """The currency the amounts are in. Files rarely say, so USD is the fallback."""
    found = {getattr(t, "currency", None) for t in trades}
    found.discard(None)
    found.discard("")

    # Mixed currencies cannot be summed honestly; the most common one is used and the
    # numbers stay comparable within it.
    return sorted(found)[0] if len(found) == 1 else (sorted(found)[0] if found else "USD")


def _flat_band(trades):
    """
    The scratch band, anchored on this trader's own median trade size.

    Mirrors the band the ingestion engine uses, so a day and a trade are judged on the same
    scale. Traders who record their own breakeven range in their journal never reach this -
    their recorded outcome is used instead.
    """
    sizes = sorted(abs(t.pnl) for t in trades if t.pnl is not None)

    if not sizes:
        return 0.0

    middle = len(sizes) // 2
    median = sizes[middle] if len(sizes) % 2 else (sizes[middle - 1] + sizes[middle]) / 2

    return median * 0.30


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0


def _safe_zone(timezone_name, trades):
    for candidate in [timezone_name] + [t.source_timezone for t in trades if t.source_timezone]:
        try:
            return ZoneInfo(candidate)
        except Exception:
            continue
    return ZoneInfo("UTC")

# ------------------------- STATISTICS ENGINE END ------------------------- #
