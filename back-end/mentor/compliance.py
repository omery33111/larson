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
from .interpret import _tokens, matches, trade_text
from .models import TraderRule
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

    # ------------- HIS OWN TAGS:
    #
    # **`by_tag` existed in the statistics from the start and nothing ever read it.**
    # Found by reading a real thread: Larson named "שורט בפרימיום" - 19 trades, -$894.50,
    # profit factor 0.51 - as the one thing in the record worth a rule, and then had to say
    # *"write it yourself in My Rules"*, because the engine that makes buttons only ever
    # looked at `by_setup`. The trader asked for a rule roughly twenty times in that thread.
    # **He kept asking because asking was all there was.**
    #
    # The shape is the setup block's exactly, and it lands on the same free-text rule - the
    # terms are built here, in python, from a label that is already on his trades, so the
    # model is no closer to the write path than it was.
    #
    # **`by_mistake` is deliberately left out.** A mistake tag is written *after* the trade,
    # about the trade - "entered early", "chased it" - so a rule saying not to take trades
    # he will later call mistakes is circular: it cannot be obeyed at the moment of entry,
    # which is the one test a rule has to pass. Tags describe the setup he saw; mistakes
    # describe the regret.
    for group in _bad_groups(breakdowns.get("by_tag", [])):
        rules.append({
            "key": f"tag:{group['key']}",
            "rule": f"לא להיכנס כשזה {group['key']}",
            "why": _evidence(group, currency),
            "weight": abs(group["net_pnl"]),
            "kind": "tag",
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

def _re_entry(rule, trade, previous):
    """
    Whether this trade is a re-entry inside the window after a losing one.

    **Both the revenge rules run through here, and both need two things the record does not
    always carry.** Measured, each missing piece produced a wrong answer rather than silence:

    - **No outcome on the trade before it.** `_is_loss` answers False for a row with no P&L
      and no status, so the window simply never opened and the trade was credited as kept -
      praise for a rule nothing tested.
    - **No entry time on this one.** Falling back to the close made the gap the distance
      between two closes, and in an export with date-only stamps that distance is zero for
      every consecutive pair. **A journal without intraday times would have reported a
      revenge breach on every trade after a loss** - a wall of accusations, all invented.

    The rule is about the moment he clicked, exactly like the two hour rules, and the close
    cannot stand in for it in either direction.
    """
    if previous is None:
        return None

    if previous.pnl is None and not previous.outcome:
        return None

    if trade.opened_at is None:
        return None

    gap = (trade.opened_at - previous.executed_at).total_seconds() / 60

    return _is_loss(previous) and 0 <= gap <= rule["value"]


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
        return _re_entry(rule, trade, previous)

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
        stamp = (trade.opened_at or trade.executed_at).astimezone(tz)
        # Minutes from midnight, so 09:30 is a threshold a trader can actually set.
        edge = stamp.replace(hour = int(rule["value"]) // 60, minute = int(rule["value"]) % 60,
                             second = 0, microsecond = 0)

        before = stamp < edge

        if trade.opened_at:
            return before if kind == "no_before" else not before and stamp > edge

        # **No entry time, so the close is all there is - and it only answers one of the two
        # directions.** A trade is opened before it is closed, so a close before the cutoff
        # proves the entry was too, and a close inside the window proves the entry was not
        # after it. The other way round the close says nothing: an exit at 18:00 against
        # "not after 16:00" is equally consistent with a 15:00 entry he was entitled to take.
        #
        # Both halves used to guess, in opposite directions - one accusing and one praising.
        if kind == "no_before":
            return True if before else None

        return False if not stamp > edge else None

    if kind == "max_size":
        return None if not trade.quantity else trade.quantity > rule["value"]

    if kind == "no_revenge_within":
        return _re_entry(rule, trade, previous)

    # ------------- THE ONE HE WROTE IN HIS OWN WORDS:
    #
    # **Pure string work, and that is the point.** His sentence was turned into terms once,
    # when he saved it; nothing here asks a model anything, so two identical trades cannot be
    # judged differently and the offender can be named by date and time like any other.
    #
    # A requirement is satisfied by **any** of its spellings, because a trader tags "IFVG"
    # one day and "inverse fvg" the next and meant the same thing both times.
    if kind == "custom":
        haystack = trade_text(trade)

        # **A trade that recorded nothing cannot answer, and saying "you kept it" would be
        # the single most damaging thing this feature could do** - it would confirm a plan he
        # may not have followed at all. Unjudged is the honest verdict, and the same one the
        # inferred setup rule already gives.
        if not haystack:
            return None

        terms = rule["value"]

        # **Nothing left to look for means nothing was tested.** Falling through would reach
        # the `return False` at the bottom - "kept" - on every single trade, which is the
        # exact false comfort the trimming upstream exists to remove.
        if not terms.get("require") and not terms.get("forbid"):
            return None

        # Tokenised once per trade rather than once per term - a short term is matched as a
        # whole word, because `tl` inside `settled` is the kind of false positive that tells
        # him he kept a rule he broke.
        tokens = _tokens(haystack)

        for spellings in terms.get("require", []):
            if not any(matches(term, haystack, tokens) for term in spellings):
                return True

        for term in terms.get("forbid", []):
            if matches(term, haystack, tokens):
                return True

        return False

    return None


def _already_his(rule, declared):
    """
    Whether a rule the record argues for is one he has already committed to himself.

    **Two ceilings on the same thing is not a stricter plan, it is a plan with no answer** -
    and the debrief reported both: the inferred one as a discovery he might not know about,
    the declared one as a commitment he made. The same trade appearing twice under two
    tones reads as the mentor not having noticed what it said a paragraph earlier.

    His own always wins. A rule he chose is the stronger statement, and the inference that
    agrees with it has nothing left to add.
    """
    kinds = {row["kind"]: row for row in declared}

    if rule["kind"] == "size" and TraderRule.MAX_SIZE in kinds:
        return True

    if rule["kind"] == "revenge" and TraderRule.NO_REVENGE_WITHIN in kinds:
        return True

    # An inferred hour that his own cut-off already bans: saying "do not trade at 09:00" to
    # somebody who has written "not before 10:00" is telling him his own rule.
    if rule["kind"] == "hour":
        hour = int(rule["value"]) * 60

        before = kinds.get(TraderRule.NO_BEFORE)
        after = kinds.get(TraderRule.NO_AFTER)

        if before and hour < before["value"]:
            return True
        if after and hour > after["value"]:
            return True

    # A setup his own free-text rule already forbids, or requires something else instead of.
    if rule["kind"] == "setup":
        setup = str(rule["value"]).lower()

        for row in declared:
            if row["kind"] != TraderRule.CUSTOM:
                continue

            terms = row["value"] if isinstance(row["value"], dict) else {}

            if any(matches(term, setup) for term in terms.get("forbid", [])):
                return True

    return False


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
    # **His own first, and an inference that merely agrees with one is dropped.** Reporting
    # both put the same trade in front of him twice under two different tones - a discovery
    # he might not know about, and a commitment he made - which reads as the mentor not
    # having noticed what it said a paragraph earlier.
    rules = list(declared) + [rule for rule in build_rules(baseline_statistics, currency)
                              if not _already_his(rule, declared)]

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

    unjudged = []

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

            if not judged and rule.get("declared"):
                unjudged.append({"rule": rule["rule"], "why": rule["why"]})

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
            # **Silence per trade, but not silence forever.**
            #
            # "Kept" here would be a rule that was never tested, so it cannot go in that
            # bucket - that part was always right. What was wrong is that it went nowhere:
            # a rule he wrote, sitting in his panel, that the debrief **never mentions
            # again in either direction.** From where he sits that is indistinguishable
            # from the mentor not noticing it, and the one thing this feature cannot look
            # like is broken software.
            #
            # His own rules only. An inferred one he never set is not his to wonder about,
            # and naming every bucket the record could not answer would bury the verdict.
            if rule.get("declared"):
                unjudged.append({"rule": rule["rule"], "why": rule["why"]})

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
        # **The third state, and it is the one that stops this reading as a bug.** A rule
        # whose words appear in nothing he records, or a session that carried none of what
        # it asks about, can be neither broken nor kept - and saying nothing about it in
        # every debrief forever looks exactly like the mentor having missed it.
        "unjudged": unjudged,
    }

# ------------------------- THE PLAN CHECK END ------------------------- #
