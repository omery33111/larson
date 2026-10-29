from collections import defaultdict

from .statistics import MIN_TRADES_FOR_BREAKDOWN, _is_loss, _is_win, _safe_zone, _split_tags



# ------------------------- CROSS-TABULATION START ------------------------- #
#
# **The one-dimensional breakdowns cannot answer "does long *from premium* work".**
#
# The trader asked exactly that - whether true-day-open premium/discount matters crossed with
# his direction - and Larson had to refuse: he has `by_tag` and he has direction, but "long
# that entered at premium" is a cell that does not exist as a number, and cutting it himself
# from the two one-dimensional slices would be the guess the iron rule forbids. **He was right
# to refuse, and that is the bug**: the raw trades carry both fields, so the cross is a thing
# Python can compute. A mentor who says "I can't cross-reference" about data he is holding is
# not the god of trading he is meant to be.
#
# So this computes it - deterministically, in Python, handed to the model finished, the same
# iron rule everything else lives under. **The model never crosses anything; it quotes a cell.**
#
# **Only the crosses that answer a real question, and only the significant cells.** Direction
# against setup, tag and hour - "does long/short from X matter" is the archetype. A full N-way
# cross-tab would explode combinatorially and bury the prompt in buckets of two trades; this
# stays bounded by the same significance floor the breakdowns use, and by a cap per cross.
#
# **A combination that is missing is a combination with too few trades, not one that cannot be
# computed** - and that distinction is the whole point. The persona says so, so Larson reports
# the cells that cleared the floor and names the floor for the ones that did not, instead of
# refusing the question wholesale.


# At most this many cells per cross, heaviest by money first - the rest are long-tail noise
# and would only cost prompt tokens on the cached prefix.
MAX_CELLS_PER_CROSS = 8

# Stored as "long"/"short"; spoken as the trader speaks them. `unknown` is dropped - a trade
# with no direction cannot sharpen a direction cross.
_DIRECTION = {"long": "לונג", "short": "שורט"}


def _directions(trade):
    label = _DIRECTION.get(trade.direction)
    return [label] if label else []


def _setups(trade):
    return _split_tags(trade.setups)


def _tags(trade):
    return _split_tags(trade.tags)


def _cross(trades, first, second):
    """Every (a, b) cell that clears the significance floor, heaviest by money first.

    A trade contributes to each cell its own values make - a trade tagged with two setups
    lands in both, exactly as it does in the one-dimensional breakdowns, so the cross cannot
    disagree with the slice it refines.
    """
    cells = defaultdict(list)

    for trade in trades:
        for a in first(trade):
            for b in second(trade):
                if a and b:
                    cells[(a, b)].append(trade)

    out = []

    for (a, b), rows in cells.items():
        pnls = [t.pnl for t in rows if t.pnl is not None]

        if len(rows) < MIN_TRADES_FOR_BREAKDOWN or not pnls:
            continue

        wins = sum(1 for t in rows if _is_win(t))
        # Breakeven is money but not an outcome, so it stays out of the win-rate denominator -
        # the same convention the whole product classifies by.
        decided = wins + sum(1 for t in rows if _is_loss(t))

        cell = {
            "a": a,
            "b": b,
            "trades": len(rows),
            "net_pnl": round(sum(pnls), 2),
            "expectancy": round(sum(pnls) / len(pnls), 2),
            "win_rate": round(wins / decided * 100, 1) if decided else None,
        }

        # Entry quality for the combined bucket, when the price path is in the file - so
        # "was my entry optimal on long-from-premium" has heat and peak numbers, not a guess.
        maes = [t.mae for t in rows if getattr(t, "mae", None) is not None]
        mfes = [t.mfe for t in rows if getattr(t, "mfe", None) is not None]
        if maes:
            cell["avg_mae"] = round(sum(maes) / len(maes), 2)
        if mfes:
            cell["avg_mfe"] = round(sum(mfes) / len(mfes), 2)

        out.append(cell)

    out.sort(key = lambda cell: -abs(cell["net_pnl"]))

    return out[:MAX_CELLS_PER_CROSS]


def cross_breakdowns(trades, timezone_name = "Asia/Jerusalem"):
    """
    The two-dimensional cells the resume never carried. Empty when nothing clears the floor,
    so a thin record adds nothing to the prompt.
    """
    tz = _safe_zone(timezone_name, trades)

    def hours(trade):
        return [f"{trade.executed_at.astimezone(tz).hour:02d}:00"]

    pairs = (
        ("כיוון_מול_סטאפ", _directions, _setups, "כיוון", "סטאפ"),
        ("כיוון_מול_תגית", _directions, _tags, "כיוון", "תגית"),
        ("כיוון_מול_שעה", _directions, hours, "כיוון", "שעה"),
    )

    result = {}

    for name, first, second, a_label, b_label in pairs:
        cells = _cross(trades, first, second)

        if cells:
            result[name] = [_public_cell(cell, a_label, b_label) for cell in cells]

    return result


def _public_cell(cell, a_label, b_label):
    """A cell as the model sees it - the internal a/b keys renamed, entry quality kept."""
    out = {a_label: cell["a"], b_label: cell["b"], "עסקאות": cell["trades"],
           "net_pnl": cell["net_pnl"], "expectancy": cell["expectancy"],
           "win_rate": cell["win_rate"]}

    for field in ("avg_mae", "avg_mfe"):
        if field in cell:
            out[field] = cell[field]

    return out

# ------------------------- CROSS-TABULATION END ------------------------- #
