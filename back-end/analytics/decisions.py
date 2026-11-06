"""
Fold copy-traded executions back into the single decision that produced them.

**A copy trader places one trade and a copier mirrors it across several accounts at the same
instant.** The export then carries that one decision as N rows - same instrument, same
direction, the same entry minute - one per account, each with its own (near-identical) P&L.
Those rows are real per-account money and must stay rows for the per-account cut (`by_account`).
But every metric that counts *how often he acts* - trades per day, pace, overtrading, revenge,
streaks - reads N where the truth is one, and tells him he takes "12 trades a day" when he took
three and a copier did the rest. That number is not just wrong, it is the kind of wrong that
makes the mentor sound broken on the first session.

So the engines that count decisions run on `collapse(trades)`, and only `by_account` (and the
account list) stays on the raw rows. The split is the whole point: **money is per account,
cadence is per decision.**

**Two guarantees hold this safe:**
  - **Identity for a single-account trader** - the overwhelming majority. Every group is one
    account, nothing collapses, `collapse(rows) is rows'` content unchanged. So nothing an
    existing user sees moves, and every existing test (all single-account, or multi-account on
    distinct days) is untouched.
  - **The money never changes.** A decision's P&L is the sum of its copies, so the total over
    decisions equals the total over rows to the cent - `net`, the daily sums, the drawdown all
    land exactly where they did. Only the *counts* fall.

The collapse key is tight on purpose - same instrument, same direction, same entry minute, and
every row on a *distinct* account - because that is the signature of a mirror and nothing else
is. When accounts repeat inside a group it is not a clean copy set, so the rows pass through
uncollapsed: under-collapsing is a count that is slightly high, over-collapsing is money that
vanishes, and only one of those is acceptable.
"""

from collections import defaultdict
from types import SimpleNamespace


# Every attribute the analytics engines read off a trade. A merged decision is a plain
# namespace carrying these from its first copy, because the engines only ever touch a trade by
# attribute (the whole test suite drives them with SimpleNamespace rows), so a namespace is a
# trade as far as they are concerned - and this list is what keeps a new field from silently
# going missing on a decision.
_FIELDS = (
    "executed_at", "opened_at", "symbol", "instrument", "account_id", "source_timezone",
    "currency", "direction", "quantity", "entry_price", "exit_price", "pnl", "points", "fees",
    "r_multiple", "stop_loss", "take_profit", "mfe", "mae", "excursion_estimated",
    "highest_price", "lowest_price", "was_documented", "duration_seconds", "orders_count",
    "setups", "tags", "mistakes", "notes", "rating", "screenshot_url", "outcome",
)


def _instrument(trade):
    # The family, falling back to the raw ticker - the same rule the breakdowns group by, so a
    # rolled contract (MNQU6 / MNQZ6) still reads as one instrument for the copy key.
    return getattr(trade, "instrument", None) or trade.symbol


def _entry_minute(trade):
    """The decision moment, truncated to the minute. Mirrors fire together; a minute bucket
    catches them without fusing two genuine entries that merely share an hour."""
    when = trade.opened_at or trade.executed_at
    return when.replace(second = 0, microsecond = 0) if when else None


def _merge(group):
    """One decision from its copies. Money sums; everything descriptive comes from the first
    copy, which they share by construction (same decision)."""
    base = group[0]
    merged = SimpleNamespace(**{field: getattr(base, field, None) for field in _FIELDS})

    # The money of the decision is the money of all its copies together - this is what keeps the
    # total identical to the row-level total.
    merged.pnl = sum(t.pnl for t in group)

    # Size is his *per-account* sizing choice, not the copy count, so the representative is one
    # account's size (they are equal for a clean mirror; max covers an uneven fill) - never the
    # sum, which would read a 1-contract decision copied four ways as a 4-contract position.
    sizes = [t.quantity for t in group if t.quantity is not None]
    merged.quantity = max(sizes) if sizes else base.quantity

    # Heat folds the same way the money does, so capture/heat stay in the decision's own unit.
    mfes = [t.mfe for t in group if t.mfe is not None]
    maes = [t.mae for t in group if t.mae is not None]
    merged.mfe = sum(mfes) if mfes else None
    merged.mae = sum(maes) if maes else None

    # The recorded outcome is the trader's own call and the copies share it, so it carries over
    # untouched (via _FIELDS) - a decision is counted the way he counted it, not re-derived.
    merged.copies = len(group)
    return merged


def collapse(trades):
    """
    Rows -> decisions. Copy groups fold into one; everything else passes through unchanged.

    Idempotent and order-preserving by `executed_at`. For a single-account record it returns the
    same trades, so callers can apply it unconditionally at their entry.
    """
    groups = defaultdict(list)
    for t in trades:
        groups[(_instrument(t), t.direction, _entry_minute(t))].append(t)

    out = []
    for group in groups.values():
        accounts = {t.account_id for t in group}
        # The mirror signature: more than one row, one per distinct account, every account named.
        is_copy_set = len(group) > 1 and len(accounts) == len(group) and None not in accounts
        if is_copy_set:
            out.append(_merge(group))
        else:
            out.extend(group)

    out.sort(key = lambda t: t.executed_at)
    return out
