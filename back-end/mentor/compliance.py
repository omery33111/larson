from collections import defaultdict
from zoneinfo import ZoneInfo

from analytics.evidence import describe_trade
from analytics.statistics import (MIN_TRADES_FOR_BREAKDOWN, REVENGE_WINDOW_MINUTES, clean_label,
                                  _duration_bucket, _is_loss, _split_tags)
from analytics.formatting import money, percent
from analytics.formatting import trades as trade_count



# ------------------------- THE PLAN CHECK START ------------------------- #
#
# The other half of a debrief, and the half that makes a one-trade session worth answering.
#
# **A deviation needs a sample; a rule needs a single event.** "Has your rate of sub-two-minute
# trades come down" is a statistic and takes dozens of trades to mean anything. "Was this trade
# held under two minutes" is a fact about one trade, and it is checkable the moment it lands.
#
# So the resume is turned into a short list of rules the trader's own history already argues
# for - the buckets that lose him money - and every new trade is checked against them. A
# session of one either obeyed them or did not, and either answer is worth saying out loud.
#
# Everything here is computed in Python. The model is handed the verdicts and asked to say
# them like a mentor; it never decides what a rule is and never counts anything itself.

# A rule has to rest on something. Below this the "leak" is an anecdote, and telling a trader
# to stop doing something on the strength of four trades is how a mentor loses credibility.
from .rules import DAY_KINDS, day_verdict


MIN_TRADES_FOR_RULE = MIN_TRADES_FOR_BREAKDOWN

# And it has to have cost real money, not a rounding error.
MIN_LOSS_FOR_RULE = 1.0

# The prompt carries the rules that matter, not every negative bucket in the history.
MAX_RULES = 6

# A market this much of his history is where he trades, not a choice he is making.
MAX_SHARE_FOR_INSTRUMENT_RULE = 0.5



def _bad_groups(groups):
    """Buckets that are significant, negative and actually cost money."""
    return [g for g in groups
            if g.get("is_significant")
            and g["expectancy"] < 0
            and g["net_pnl"] < -MIN_LOSS_FOR_RULE]


def _evidence(group, currency):
    return (f"{trade_count(group['trades'])} כאלה ברזומה, "
            f"{percent(group['win_rate'])} הצלחה, {money(group['net_pnl'], currency)}")



# ------------- THE RULES, DERIVED FROM THE RESUME:

def build_rules(statistics, currency):
    """
    The trader's own history, restated as things not to do.

    Each rule carries the evidence that produced it, so the mentor can always answer "says
    who" with a number rather than an opinion.
    """
    breakdowns = statistics.get("breakdowns", {})
    behaviour = statistics.get("behaviour", {})

    rules = []

    # ------------- HOLD TIME:
    for group in _bad_groups(breakdowns.get("by_duration", [])):
        rules.append({
            "key": f"duration:{group['key']}",
            "rule": f"לא להיכנס לעסקאות שנסגרות בטווח {group['key']}",
            "why": _evidence(group, currency),
            "weight": abs(group["net_pnl"]),
            "kind": "duration",
            "value": group["key"],
        })

    # ------------- HOURS:
    for group in _bad_groups(breakdowns.get("by_hour", [])):
        rules.append({
            "key": f"hour:{group['key']}",
            "rule": f"לא לסחור בשעה {int(group['key']):02d}:00",
            "why": _evidence(group, currency),
            "weight": abs(group["net_pnl"]),
            "kind": "hour",
            "value": int(group["key"]),
        })

    # ------------- SETUPS:
    for group in _bad_groups(breakdowns.get("by_setup", [])):
        rules.append({
            "key": f"setup:{group['key']}",
            "rule": f"לא לקחת את הסטאפ {group['key']}",
            "why": _evidence(group, currency),
            "weight": abs(group["net_pnl"]),
            "kind": "setup",
            "value": str(group["key"]),
        })

    # ------------- INSTRUMENTS:
    # Only where he has somewhere else to go. "Stop trading NQ" to a trader who only trades
    # NQ is not a rule, it is a shrug - so a market that carries most of his history is left
    # alone even when it is the losing one.
    total = statistics.get("total_trades") or 0

    for group in _bad_groups(breakdowns.get("by_symbol", [])):
        if not total or group["trades"] > total * MAX_SHARE_FOR_INSTRUMENT_RULE:
            continue

        name = group.get("label") or group["key"]
        rules.append({
            "key": f"instrument:{group['key']}",
            "rule": f"לא לסחור ב-{name}",
            "why": _evidence(group, currency),
            "weight": abs(group["net_pnl"]),
            "kind": "instrument",
            "value": str(group["key"]),
        })

    # Direction is deliberately not a rule. Every trade is a long or a short, so the check
    # would fire on all of them by construction, and "never take longs" is not something a
    # trader can act on the way "not under two minutes" is. It stays a finding on the profile
    # page, where it belongs.

    # ------------- REVENGE:
    revenge = behaviour.get("revenge", {})
    if revenge.get("available") and revenge.get("is_worse") and revenge.get("count", 0) >= MIN_TRADES_FOR_RULE:
        rules.append({
            "key": "revenge",
            "rule": f"לא לפתוח עסקה תוך {REVENGE_WINDOW_MINUTES} דקות מסגירת הפסד",
            "why": f"{trade_count(revenge['count'])} כאלה ברזומה, תוחלת "
                   f"{money(revenge['expectancy'], currency)} מול "
                   f"{money(revenge['rest_expectancy'], currency)} בשאר",
            "weight": abs(revenge.get("total_pnl", 0.0)),
            "kind": "revenge",
            "value": REVENGE_WINDOW_MINUTES,
        })

    # ------------- SIZE:
    size = behaviour.get("size_discipline", {})
    if size.get("available") and size.get("biggest_size_expectancy", 0) < 0:
        rules.append({
            "key": "size",
            "rule": f"לא לעלות מעל {size['avg_size']} חוזים",
            "why": f"בגודל המקסימלי שלך ({size['max_size']} חוזים) התוחלת היא "
                   f"{money(size['biggest_size_expectancy'], currency)} לעסקה",
            "weight": abs(size["biggest_size_expectancy"]) * 10,
            "kind": "size",
            "value": size["avg_size"],
        })

    rules.sort(key = lambda r: -r["weight"])

    return rules[:MAX_RULES]



# ------------- THE CHECK, ONE TRADE AT A TIME:

def _breaks(rule, trade, tz, previous):
    """Whether this one trade broke this one rule. None when the rule cannot be judged."""
    kind = rule["kind"]

    if kind == "duration":
        bucket = _duration_bucket(trade)
        return None if bucket is None else bucket == rule["value"]

    if kind == "hour":
        return trade.executed_at.astimezone(tz).hour == rule["value"]

    if kind == "setup":
        tags = _split_tags(trade.setups)
        return None if not tags else rule["value"] in tags

    if kind == "instrument":
        found = trade.instrument or trade.symbol
        return None if not found else found == rule["value"]

    if kind == "revenge":
        if previous is None:
            return None

        opened = trade.opened_at or trade.executed_at
        gap = (opened - previous.executed_at).total_seconds() / 60

        return _is_loss(previous) and 0 <= gap <= rule["value"]

    if kind == "size":
        return None if not trade.quantity else trade.quantity > rule["value"]

    # ------------- AND THE KINDS A TRADER DECLARES FOR HIMSELF:
    #
    # **These judge the entry and not the exit, which is the opposite of the inferred hour
    # rule above - deliberately.** `by_hour` buckets a trade by when it closed, because that
    # is where its result lands. But a trader who says "I do not enter before ten" is talking
    # about the moment he clicked, and judging him on the close would mark a 09:50 entry that
    # ran until 10:30 as obedient.
    if kind in ("no_before", "no_after"):
        entry = (trade.opened_at or trade.executed_at).astimezone(tz)
        edge = entry.replace(hour = int(rule["value"]), minute = 0, second = 0, microsecond = 0)

        return entry < edge if kind == "no_before" else entry > edge

    if kind == "min_hold":
        if trade.duration_seconds is None:
            return None
        return trade.duration_seconds < rule["value"] * 60

    if kind == "max_size":
        return None if not trade.quantity else trade.quantity > rule["value"]

    if kind == "no_revenge_within":
        if previous is None:
            return None

        opened = trade.opened_at or trade.executed_at
        gap = (opened - previous.executed_at).total_seconds() / 60

        return _is_loss(previous) and 0 <= gap <= rule["value"]

    if kind == "only_setups":
        tags = _split_tags(trade.setups)
        # No tag means the trade cannot answer this rule, and silence is the honest verdict -
        # "you kept it" on a rule that was never tested is a compliment nobody earned.
        return None if not tags else not any(tag in rule["value"] for tag in tags)

    return None


def check_plan(baseline_statistics, baseline, recent, currency = "USD",
               timezone_name = "Asia/Jerusalem", declared = ()):
    """
    Did the new trades obey the rules - the ones the resume argues for, and the ones he set?

    Works at any size, and that is the whole point: a trader who closed his session on one
    trade still gets told whether that trade was the thing he keeps being told to stop doing.

    `declared` arrives already in this shape from `rules.py`, carrying `declared: True`.
    **They are judged by the same loop and reported in the same lists**, because the trade
    that broke one is named the same way either way - what changes is only that the answer to
    "says who" is him.
    """
    rules = list(declared) + build_rules(baseline_statistics, currency)

    if not recent:
        return {"available": False, "reason": "אין עסקאות חדשות לבדוק."}

    if not rules:
        return {"available": False,
                "reason": "אין ברזומה דפוס מפסיד מובהק שאפשר לבדוק מולו, ולא קבעת כללים "
                          "לעצמך — אין כרגע כלל שהוא מפר או עומד בו."}

    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")

    # The predecessor of the first new trade lives in the baseline, so a revenge entry that
    # follows a loss from the previous session is still caught.
    history = sorted(list(baseline) + list(recent), key = lambda t: t.executed_at)
    before = {}
    for previous, current in zip(history, history[1:]):
        before[id(current)] = previous

    kept, broken = [], []

    # Grouped once, for the rules that are about a day rather than a trade.
    by_day = defaultdict(list)
    for trade in recent:
        by_day[trade.executed_at.astimezone(tz).date()].append(trade)

    for rule in rules:
        offenders, judged = [], 0

        # ------------- A DAY CANNOT BE JUDGED ONE TRADE AT A TIME:
        #
        # "No more than four trades a day" and "stop at a $500 loss" are answered by the
        # day's rows together, and no single trade in that day can answer either. They get
        # their own pass, and the trade named is **the one that crossed the line** rather
        # than the worst one - because that is the trade that should not have been taken.
        if rule["kind"] in DAY_KINDS:
            for day, day_rows in sorted(by_day.items()):
                broke, offender = day_verdict(rule, day_rows)

                if broke is None:
                    continue

                judged += 1
                if broke and offender is not None:
                    offenders.append(offender)

            entry = {"rule": rule["rule"], "why": rule["why"], "checked": judged}
            if rule.get("declared"):
                entry["declared"] = True

            if judged:
                if offenders:
                    entry["broke"] = len(offenders)
                    entry["examples"] = [describe_trade(t, tz, currency) for t in offenders[:3]]
                    broken.append(entry)
                else:
                    kept.append(entry)

            continue

        for trade in sorted(recent, key = lambda t: t.executed_at):
            verdict = _breaks(rule, trade, tz, before.get(id(trade)))

            if verdict is None:
                continue

            judged += 1
            if verdict:
                offenders.append(trade)

        if not judged:
            # The trade carried nothing to judge this rule by - no duration, no setup tag.
            # Silence is the honest answer; a "kept" here would be a rule that was never
            # actually tested.
            continue

        entry = {
            "rule": rule["rule"],
            "why": rule["why"],
            "checked": judged,
        }

        # The mentor has to be able to tell a commitment from an inference without being told.
        if rule.get("declared"):
            entry["declared"] = True

        if offenders:
            entry["broke"] = len(offenders)
            entry["examples"] = [describe_trade(t, tz, currency) for t in offenders[:3]]
            broken.append(entry)
        else:
            kept.append(entry)

    return {
        "available": True,
        "checked": len(recent),
        # Ordered so the most expensive rule is first on both sides - `weight` itself never
        # leaves, exactly like `impact` and `magnitude`.
        "broken": broken,
        "kept": kept,
    }

# ------------------------- THE PLAN CHECK END ------------------------- #
