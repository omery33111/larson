from collections import defaultdict
from zoneinfo import ZoneInfo

from analytics.formatting import money, ratio, trades as trade_count

from .compliance import build_rules, check_plan
from .interpret import matches, vocabulary
from .models import DismissedSuggestion, TraderRule
from .rules import clock, declared_rules



# ------------------------- LARSON ASKS ONE QUESTION ------------------------- #
#
# **The server asks it, in Larson's voice.** Python finds the condition, computes the
# figure and composes the card; the model never writes a row and never presses anything.
# That is not a detail - "the model has no tools" is the entire reason an injection in a
# trade file cannot reach anyone's data, and a feature that let it create rules would end
# that argument. The same shape as the receipt line, which the server has always written.
#
# **Two questions, and the second is the one worth having:**
#
#     "Should I hold you to this?"   - a losing pattern he just repeated
#     "Should we drop this one?"     - a rule he has outgrown, or one he never keeps
#
# Any analytics product can propose a rule. **Retiring one is what a mentor does**, and it
# is why `retire` outranks `add` when both apply: tidying what exists comes before adding
# more, and it is the rarer moment.
#
# **One card per debrief, never two.** A mentor who offers three rules is a form.
#
# **And a no is remembered for good** (`DismissedSuggestion`). The condition that produced a
# suggestion is usually still true next week, so without that the same card returns every
# debrief until he gives in or stops reading. That is the failure mode that kills features
# like this one, and it is cheap to avoid.


# ------------- WHEN A RULE HAS BEEN OUTGROWN, AND WHEN IT WAS NEVER REAL:
#
# Measured over his whole record rather than over one file - a single debrief judges a
# handful of trades, which is nowhere near enough to retire a commitment on.
GRADUATED_AFTER = 25
NEVER_KEPT_AFTER = 10

# **A fifth, which is the number the reasoning always used.**
#
# The argument for having a floor at all is that a rule kept *sometimes* is one he is
# working on, and offering to delete that is telling him to stop trying. The line I argued
# for out loud was a fifth; the line I wrote was a tenth, and nobody noticed until a real
# rule landed between them.
#
# His was broken on 74 of 83 - **89.2% against a 90% bar, missing by less than one trade** -
# while Larson's own text recommended dropping it. A threshold that disagrees with the
# answer beside it by a fraction of a trade is not protecting anything; it is just brittle,
# and it reads as the feature being broken.
BARELY_KEPT = 0.2

# A pattern has to have cost real money and have happened again just now.
MIN_WORTH_A_RULE = 150.0


# ------------- WHEN HE ASKS FOR ONE IN SO MANY WORDS:
#
# **A trader who types "suggest me a rule" and gets nothing has been told the feature does
# not exist.** The card was built to arrive at the one moment it is most likely to be
# accepted - under a debrief where he has just repeated the pattern - and that is still the
# right default. But asking for it *is* the moment, and the "did it happen again just now"
# test exists only to decide whether this is a moment. When he asks, that question is
# already answered.
#
# Deterministic, like `looks_specific` in the retrieval path: a phrase match in python, no
# model call to decide whether the model should be asked something.

# **Both halves have to be wide, and the first version was narrow in a way I had built.**
# The screen calls them "התנאים שלך"; the detector only knew "כלל". A trader who asked
# "על איזה אחד מהתנאים היית מציע לי לוותר" - in the product's own word - got nothing, and
# from the outside that is the feature being broken rather than the question being missed.
#
# Verb and noun are matched separately so neither list has to anticipate phrasings. The
# verbs cover asking for one and asking to be rid of one, because "which would you drop" is
# the same request as "suggest me one" as far as this is concerned: it wants the card.
_ASKING = (
    "תציע", "מציע", "הצע", "המלץ", "תמליץ", "ממליץ", "המלצה", "הצעה",
    "כדאי", "שווה", "לוותר", "להוריד", "למחוק", "לבטל", "להוסיף", "איזה", "איזו",
    "suggest", "recommend", "should i",
)

# **"תנאי" is in here because it is what the screen says**, and a product whose own
# vocabulary its detector does not recognise is a product that ignores you in your words.
_ABOUT_RULES = (
    "כלל", "כללים", "תנאי", "תנאים", "rule", "condition",
)

def asked_for_one(text):
    """Whether this message is a request for a rule rather than a question about trading."""
    if not text:
        return False

    lowered = text.lower()

    return (any(phrase in lowered for phrase in _ASKING)
            and any(word in lowered for word in _ABOUT_RULES))


def propose(user, recent, statistics, currency = "USD", timezone_name = "Asia/Jerusalem",
            asked = False):
    """
    The one card to put under this answer, or `None` - which is the usual answer.

    `recent` is what he just uploaded; `statistics` is the resume it landed on. `asked` is
    true when he said so in words, and it lifts the "did he just do it again" requirement:
    that test exists to decide whether this is a moment, and asking settles it.
    """
    declined = set(DismissedSuggestion.objects.filter(user = user)
                   .values_list("key", flat = True))

    return (_retire(user, currency, timezone_name, declined, statistics)
            or _add(user, recent, statistics, currency, timezone_name, declined, asked))



# ------------------------- "SHOULD WE DROP THIS ONE?" ------------------------- #

# **A rule that forbids something profitable is a bad rule however faithfully he keeps it.**
#
# Everything else here judges a rule by how often it is kept, and that misses the case that
# matters most: the trader wrote "only enter without IFVG" while IFVG is the tag on his best
# setup. Larson said so in words - the rule forbids exactly what he lives on - and the
# engine offered nothing, because compliance ratios cannot see money.
#
# **And the dangerous version is the one he keeps.** A rule he obeys perfectly while it
# blocks his most profitable setup would have earned the graduation card: "forty trades in a
# row, zero breaches, this is who you are now" - congratulating him for the thing costing
# him the most. That is the single worst sentence this feature could produce, and nothing
# before this could have stopped it.
#
# So this reason outranks both of the others: not how often, but whether it should exist.
COSTS_HIM_AT_LEAST = 300.0


def _structured_works_against_him(row, statistics):
    """
    A threshold that cuts off a part of his record that makes money.

    Each kind is asked the same question in its own units: **what does the rule stop him
    doing, and is that thing profitable?** The figure is his own, out of the breakdowns -
    nothing here is estimated.
    """
    kind, value = row.kind, row.number
    breakdowns = statistics.get("breakdowns", {})
    behaviour = statistics.get("behaviour", {})

    if value is None:
        return None

    # ------------- THE HOURS IT BANS:
    if kind in (TraderRule.NO_BEFORE, TraderRule.NO_AFTER):
        hours = [g for g in breakdowns.get("by_hour", []) if g.get("is_significant")]
        edge = int(value) // 60

        banned = [g for g in hours
                  if (int(g["key"]) < edge if kind == TraderRule.NO_BEFORE
                      else int(g["key"]) > edge)]

        earned = sum(g.get("net_pnl", 0) for g in banned)

        if earned >= COSTS_HIM_AT_LEAST:
            best = max(banned, key = lambda g: g.get("net_pnl", 0))
            return {"group": {"key": f"השעות ש{'לפני' if kind == TraderRule.NO_BEFORE else 'אחרי'} "
                                     f"{clock(value)}",
                              "net_pnl": earned,
                              "trades": sum(g.get("trades", 0) for g in banned)},
                    "shape": "forbids", "detail_extra": f"הטובה שבהן היא {int(best['key']):02d}:00"}

    # ------------- THE SIZE IT CAPS:
    if kind == TraderRule.MAX_SIZE:
        size = behaviour.get("size_discipline", {})

        # **Only the per-trade expectancy is published, not how many trades it covers** -
        # so this reports the expectancy and says so, rather than multiplying by a count
        # nobody measured. A figure invented to look bigger is the one thing this product
        # does not do.
        if (size.get("available") and size.get("max_size", 0) > value
                and size.get("biggest_size_expectancy", 0) > 0):
            return {"group": {"key": f"העסקאות הגדולות שלך (מעל {ratio(value)} חוזים)",
                              "net_pnl": size["biggest_size_expectancy"],
                              "trades": None},
                    "shape": "forbids", "per_trade": True}

    # ------------- THE RE-ENTRY IT BLOCKS:
    if kind == TraderRule.NO_REVENGE_WITHIN:
        revenge = behaviour.get("revenge", {})
        # **`is_worse` false means his re-entries after a loss do better than the rest** -
        # and that is true of this trader right now. A rule banning them is banning the
        # better half.
        if (revenge.get("available") and revenge.get("is_significant")
                and not revenge.get("is_worse")
                and revenge.get("total_pnl", 0) >= COSTS_HIM_AT_LEAST):
            return {"group": {"key": "הכניסות שלך אחרי הפסד",
                              "net_pnl": revenge["total_pnl"],
                              "trades": revenge.get("count", 0)},
                    "shape": "forbids"}

    return None


# **A margin, because "never broken" and "never tested" are not the same thing.**
#
# A trader who always takes exactly three contracts under a "maximum three" rule has never
# broken it - and he is sitting precisely on it, which is a rule he respects to the
# contract rather than one that does nothing. Calling that vacuous would be insulting and
# wrong. What is vacuous is a threshold he never comes near: a cap of ninety-nine from
# somebody whose largest position is three.
NEVER_NEAR = 0.75

# For the two clock rules the same idea is an hour rather than a ratio - 09:00 against a
# 10:00 cut-off is near it; 14:00 is not.
NEVER_NEAR_MINUTES = 60


def _zone(name):
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Asia/Jerusalem")


def _watching_nothing(row, vocabulary_now):
    """
    A rule whose tag has disappeared from his record since it was written.

    **It worked, and then it silently stopped.** He renames a tag, or drops a setup from his
    journal, and a rule that had been checking something real quietly begins checking
    nothing - still reported, still confident, matching no trade ever again. Nothing on any
    screen would say so, and "kept" would look exactly the same as "could not be judged".

    The evidence is already stored: `known_labels` is the vocabulary the sentence was read
    against. A term that was one of his labels then and matches none of them now is a tag
    that went away - which is a different thing from a term that never matched anything,
    and the two must not be confused. The second is a rule about something the engine
    cannot see, and he was already warned about that when he saved it.
    """
    terms = row.terms if isinstance(row.terms, dict) else {}

    wanted = [t for group in terms.get("require", []) for t in group]
    wanted += list(terms.get("forbid", []))

    if not wanted or not row.known_labels or not vocabulary_now:
        return None

    was = [label.lower() for label in row.known_labels]
    now = [label.lower() for label in vocabulary_now]

    for term in wanted:
        existed = any(matches(term, label) for label in was)
        exists = any(matches(term, label) for label in now)

        if existed and not exists:
            return term

    return None


def _never_tested(row, rows, tz):
    """
    A rule his record never comes near - **the graduation card's evil twin.**

    "Do not exceed 99 contracts" from a trader who never takes more than three is judged on
    every trade, broken by none, and therefore earns the warmest thing this feature says:
    *forty in a row, zero breaches, this is who you are now*. **It congratulated him for a
    rule that cannot be broken**, which is worse than saying nothing: it teaches him the
    praise is automatic, and the next time it is earned he will not believe it.

    A habit is a threshold he comes close to and respects. A threshold nothing approaches
    is not discipline, it is a no-op.
    """
    kind, value = row.kind, row.number

    if kind == TraderRule.CUSTOM or value is None:
        return None

    if kind == TraderRule.MAX_SIZE:
        biggest = max((t.quantity for t in rows if t.quantity), default = 0)
        if biggest and biggest < value * NEVER_NEAR:
            return f"הגודל הגדול ביותר שלך הוא {ratio(biggest)} חוזים"

    if kind in (TraderRule.NO_BEFORE, TraderRule.NO_AFTER):
        entries = [(t.opened_at or t.executed_at).astimezone(tz) for t in rows]
        if not entries:
            return None
        minutes = [e.hour * 60 + e.minute for e in entries]

        if kind == TraderRule.NO_BEFORE and min(minutes) >= value + NEVER_NEAR_MINUTES:
            return f"הכניסה המוקדמת ביותר שלך היא {clock(min(minutes))}"
        if kind == TraderRule.NO_AFTER and max(minutes) <= value - NEVER_NEAR_MINUTES:
            return f"הכניסה המאוחרת ביותר שלך היא {clock(max(minutes))}"

    if kind == TraderRule.MAX_TRADES_PER_DAY:
        per_day = defaultdict(int)
        for trade in rows:
            per_day[trade.executed_at.astimezone(tz).date()] += 1
        busiest = max(per_day.values(), default = 0)
        if busiest and busiest < value * NEVER_NEAR:
            return f"היום העמוס ביותר שלך היה {trade_count(busiest)}"

    if kind == TraderRule.MAX_DAILY_LOSS:
        per_day = defaultdict(float)
        for trade in rows:
            if trade.pnl:
                per_day[trade.executed_at.astimezone(tz).date()] += trade.pnl
        worst = min(per_day.values(), default = 0)
        if worst > -abs(value) * NEVER_NEAR:
            return f"היום הגרוע ביותר שלך היה {money(worst)}"

    return None


def _works_against_him(row, statistics, currency):
    """
    Whether this rule points him at the wrong half of his own record.

    **Two shapes, and they are the same mistake from opposite ends.** A rule that forbids
    something profitable blocks money he is making; a rule that requires something
    unprofitable pushes him into money he is losing. The first was obvious from his
    screenshot - "only without IFVG" while IFVG is +$939 - and the second was sitting in the
    same panel unnoticed: "only on 1m IFVG", a tag worth -$114 to him.

    Returns the bucket and which way round it is, or `None` when the rule is doing its job.
    """
    # ------------- THE STRUCTURED KINDS:
    #
    # **The same question, asked of a number instead of a tag.** "Do not enter before
    # 10:00" is costing him exactly as much as "never with IFVG" if his mornings are where
    # he makes money - and until now only the free-text rules were checked, so the two
    # halves of the panel were held to different standards.
    if row.kind != TraderRule.CUSTOM:
        return _structured_works_against_him(row, statistics)

    terms = row.terms if isinstance(row.terms, dict) else {}

    forbidden = list(terms.get("forbid", []))
    required = [term for group in terms.get("require", []) for term in group]

    if not forbidden and not required:
        return None

    buckets = (statistics.get("breakdowns", {}).get("by_setup", [])
               + statistics.get("breakdowns", {}).get("by_tag", []))

    found = None

    for group in buckets:
        if not group.get("is_significant"):
            continue

        label = str(group.get("key", "")).lower()
        pnl = group.get("net_pnl", 0)

        # **Forbidding something that makes him money.**
        if pnl >= COSTS_HIM_AT_LEAST and any(matches(t, label) for t in forbidden):
            if found is None or pnl > abs(found["group"].get("net_pnl", 0)):
                found = {"group": group, "shape": "forbids"}

        # **Requiring something that loses him money.** Every trade he takes under this rule
        # is in that bucket by definition, so the rule is not failing to protect him - it is
        # aiming him at it.
        if pnl <= -COSTS_HIM_AT_LEAST and any(matches(t, label) for t in required):
            if found is None or abs(pnl) > abs(found["group"].get("net_pnl", 0)):
                found = {"group": group, "shape": "requires"}

    return found


def _retire(user, currency, timezone_name, declined, statistics = None):
    """
    A rule he has kept so consistently it is no longer a rule, or one he never keeps.

    **Both are real mentor moments and neither is a reproach.** Forty clean trades in a row
    is a habit, not a restriction, and saying so out loud is one of the few times software
    gets to tell somebody they have changed. A rule broken every single time is not
    discipline failing - it is a plan that does not fit him, and pretending otherwise
    teaches him to ignore the whole section.
    """
    from trades.models import Trade

    rows = list(Trade.objects.filter(user = user))

    if not rows:
        return None

    declared = declared_rules(user, currency)

    if not declared:
        return None

    # Judged over everything he has, with no inferred rules in the way - this is a question
    # about his own commitments only.
    statistics = statistics or {}
    current_vocabulary = vocabulary(user)

    plan = check_plan({}, [], rows, currency, timezone_name, declared = declared)

    # The sentence a rule was translated into is the only handle a judged entry carries, so
    # the map is built with the same translator the checker used - not with a second copy
    # of the wording, which is how the two would drift apart.
    from .rules import _translate

    by_sentence = {}

    for row in TraderRule.objects.filter(user = user, is_active = True):
        translated = _translate(row, currency)
        if translated:
            by_sentence[translated["rule"]] = row

    for entry in plan["kept"] + plan["broken"]:
        if not entry.get("declared"):
            continue

        row = by_sentence.get(entry["rule"])

        if row is None:
            continue

        # **Keyed on the reason and not only on the rule**, which it was.
        #
        # "No, I keep breaking it and I am still working on it" is a different answer from
        # "no, I know it blocks my best setup and I want it anyway". A dismissal of the
        # first silenced the second forever, so the strongest reason this engine has could
        # never reach a trader who had already said no to a weaker one. A no should close
        # the question it was asked, not every future question about the same rule.
        def asked_before(reason):
            return f"retire:{row.id}:{reason}" in declined

        judged = entry.get("checked", 0)
        broke = entry.get("broke", 0)
        name = entry["rule"]

        # **Before the ratios, because this is a reason to drop a rule and they are only
        # symptoms.** Kept or broken, a rule that forbids what he makes money on should go.
        costly = _works_against_him(row, statistics, currency)

        if costly and not asked_before("costly"):
            group = costly["group"]
            verb = "אוסר עליך את" if costly["shape"] == "forbids" else "מחייב אותך דווקא את"

            figure = money(group["net_pnl"], currency)
            scale = (f"{figure} לעסקה" if costly.get("per_trade")
                     else f"{figure} על פני {trade_count(group['trades'])}")

            return {
                "action": "retire",
                "key": f"retire:{row.id}:costly",
                "rule_id": row.id,
                "title": f'"{name}" {verb} {group["key"]}.',
                "detail": f"{group['key']} — {scale} אצלך."
                          + (chr(10) + costly["detail_extra"] + "."
                             if costly.get("detail_extra") else "")
                          + chr(10) +
                          "הכלל הזה עובד נגדך — בין אם אתה שומר עליו ובין אם לא.",
                "accept": "להוריד",
                "decline": "להשאיר",
            }

        # **Before the graduation card, which is the thing it exists to stop.** A rule
        # nothing approaches would otherwise collect the warmest sentence in the product.
        # **It worked and then stopped, which is invisible without the comparison.** A term
        # that was one of his labels when the rule was written and matches none of them now
        # is a tag that went away - not a term that never matched, which he was warned
        # about at save time and is a different problem.
        gone = _watching_nothing(row, current_vocabulary)

        if gone and not asked_before("gone"):
            return {
                "action": "retire",
                "key": f"retire:{row.id}:gone",
                "rule_id": row.id,
                "title": f'"{name}" מחפש את "{gone}", ואתה כבר לא מתייג ככה.',
                "detail": "הכלל הזה עבד פעם ועכשיו הוא לא בודק כלום."
                          + chr(10) +
                          "אפשר לדייק אותו לתגית שאתה משתמש בה היום, או להוריד.",
                "accept": "להוריד",
                "decline": "להשאיר",
            }

        vacuous = _never_tested(row, rows, _zone(timezone_name))

        if vacuous and not asked_before("vacuous"):
            return {
                "action": "retire",
                "key": f"retire:{row.id}:vacuous",
                "rule_id": row.id,
                "title": f'"{name}" לא נבדק אף פעם באמת.',
                "detail": f"{vacuous} — הכלל הזה לא יכול להישבר, ולכן הוא גם לא אומר לך כלום."
                          + chr(10) +
                          "כלל שימושי הוא כזה שאתה מתקרב אליו.",
                "accept": "להוריד",
                "decline": "להשאיר",
            }

        if broke == 0 and judged >= GRADUATED_AFTER and not asked_before("graduated"):
            return {
                "action": "retire",
                "key": f"retire:{row.id}:graduated",
                "rule_id": row.id,
                "title": f'שמרת על "{name}" {trade_count(judged)} ברצף, אפס חריגות.',
                "detail": "זה כבר לא כלל — זה אתה. אפשר להוריד אותו ולפנות מקום למשהו שעוד נבדק.",
                "accept": "להוריד",
                "decline": "להשאיר",
            }

        # Strictly fewer than a fifth kept: at exactly a fifth he is still working on it.
        if (judged >= NEVER_KEPT_AFTER and (judged - broke) < judged * BARELY_KEPT
                and not asked_before("wish")):
            return {
                "action": "retire",
                "key": f"retire:{row.id}:wish",
                "rule_id": row.id,
                "title": f'"{name}" נשבר ב-{broke} מתוך {trade_count(judged)} שנבדקו.',
                # **The first version told him to lower the rule to something he already
                # meets, and he was right that it is wrong at the root: a rule is set in
                # order to be worked towards.** "Change it to what you already do" turns a
                # commitment into a description and removes the only reason to have one.
                #
                # What is actually true here is not about his discipline at all - it is
                # about the debrief. A verdict that never varies carries no information, so
                # the rule has stopped reporting anything whether or not he is improving.
                # **And that leaves two honest doors, which is exactly the two buttons:**
                # still working on it, or it does not fit him. Keeping it is a real answer
                # and the wording has to let it be one.
                # The break is deliberate: the first line is the fact, the second is the
                # choice, and running them together makes the choice read as part of the
                # explanation rather than as the thing he is being asked.
                "detail": "כלל שהתשובה עליו קבועה כבר לא אומר לך כלום בתחקיר."
                          + chr(10) +
                          "אם אתה עדיין עובד עליו — להשאיר; אם הוא לא מתאים לך — להוריד.",
                "accept": "להוריד",
                "decline": "להשאיר",
            }

    return None



def standings(user, currency = "USD", timezone_name = "Asia/Jerusalem"):
    """
    How each of his rules is actually doing, for the model to answer from.

    **Without this the words and the button disagree, and the user reads that as broken.**
    He asked which condition he would give up if he had to; Larson picked one and no button
    appeared, because the engine's bar for "this is dead weight" is 90% broken and that rule
    sits at 77%. Both were right - 23% kept is somebody working on a rule rather than
    ignoring one, and offering to delete it would be telling him to stop trying.

    What was missing is that the model had no idea. Given the figures it can answer the
    forced choice honestly *and* say why there is nothing to press, which is a better
    answer than either half alone.
    """
    from trades.models import Trade

    rows = list(Trade.objects.filter(user = user))
    declared = declared_rules(user, currency)

    if not rows or not declared:
        return []

    plan = check_plan({}, [], rows, currency, timezone_name, declared = declared)

    out = []

    for entry in plan["kept"] + plan["broken"]:
        if not entry.get("declared"):
            continue

        judged = entry.get("checked", 0)
        broke = entry.get("broke", 0)

        out.append({
            "הכלל": entry["rule"],
            "נבדק_על": judged,
            "נשבר": broke,
            "נשמר": judged - broke,
        })

    return out


# ------------------------- "SHOULD I HOLD YOU TO THIS?" ------------------------- #

def _add(user, recent, statistics, currency, timezone_name, declined, asked = False):
    """
    A losing pattern with money behind it **that he just did again.**

    The "just did again" is what makes it a moment rather than a report. The same finding
    sitting in a panel he has to open is a finding nobody acts on; arriving underneath the
    debrief where he has only now repeated it, carrying what it would have cost, is the one
    time the answer might be yes.
    """
    if not recent and not asked:
        return None

    inferred = [rule for rule in build_rules(statistics, currency)
                if rule.get("weight", 0) >= MIN_WORTH_A_RULE]

    if not inferred:
        return None

    already = {row.kind for row in TraderRule.objects.filter(user = user, is_active = True)}

    # Heaviest first: the one worth the single question he gets is the expensive one.
    for rule in sorted(inferred, key = lambda r: -r.get("weight", 0)):
        offer = _as_declarable(rule, statistics, timezone_name)

        if not offer or offer["kind"] in already:
            continue

        key = f"add:{rule['key']}"

        if key in declined:
            continue

        # It has to have happened in what he just uploaded, or this is a report and not a
        # moment. `check_plan` already knows how to ask that question of these exact rules.
        # **Unless he asked**, in which case the moment is the asking.
        if not asked:
            plan = check_plan(statistics, [], recent, currency, timezone_name)

            if not any(e["rule"] == rule["rule"] for e in plan["broken"]):
                continue

        return {
            "action": "add",
            "key": key,
            "title": offer["title"],
            "detail": rule["why"] + ("" if asked else " — וזה קרה שוב עכשיו."),
            "rule_kind": offer["kind"],
            "rule_number": offer.get("number"),
            "rule_text": offer.get("text"),
            "rule_terms": offer.get("terms"),
            "accept": "להוסיף ככלל",
            "decline": "לא",
        }

    return None


def _as_declarable(rule, statistics, timezone_name):
    """
    The inferred rule as something he could actually commit to - or `None`.

    **Not every finding maps onto a rule, and forcing one is how the feature starts lying.**
    "You lose at 09:00" is not "do not enter before 10:00" unless the losing hours sit at
    one end of his day; if 08:00 is fine and 09:00 is not, a cut-off would ban a stretch the
    record says nothing against. Where the shape does not fit, there is no card.
    """
    kind = rule["kind"]

    if kind == "size":
        # **A ceiling nothing exceeds is not a rule.** A trader who always takes one
        # contract has `avg_size == max_size`, and the inferred finding still fires because
        # his "biggest" slice is simply all of his trades. Offering him a cap at his own
        # only size produces a commitment that can never be broken and never says anything.
        size = statistics.get("behaviour", {}).get("size_discipline", {})

        if size.get("max_size", 0) <= float(rule["value"]):
            return None

        return {"kind": TraderRule.MAX_SIZE,
                "number": float(rule["value"]),
                "title": f"החוזים הגדולים שלך מפסידים — לקבוע תקרה של {rule['value']}?"}

    if kind == "revenge":
        return {"kind": TraderRule.NO_REVENGE_WITHIN,
                "number": float(rule["value"]),
                "title": f"כניסה תוך {rule['value']} דקות מהפסד — להפוך את זה לכלל?"}

    if kind == "setup":
        setup = str(rule["value"]).lower()
        return {"kind": TraderRule.CUSTOM,
                "text": f"לא לקחת את הסטאפ {rule['value']}",
                "terms": {"require": [], "forbid": [setup]},
                "title": f"הסטאפ {rule['value']} מדמם — להפוך את זה לכלל?"}

    if kind == "hour":
        edge = _clean_edge(rule["value"], statistics)
        if not edge:
            return None

        side, hour = edge
        word = "לפני" if side == TraderRule.NO_BEFORE else "אחרי"

        return {"kind": side,
                "number": float(hour * 60),
                "title": f"כל ההפסדים שלך {word} {clock(hour * 60)} — לקבוע את זה ככלל?"}

    # `duration` and `instrument` have no kind he can declare, so they stay findings.
    return None


def _clean_edge(bad_hour, statistics):
    """
    Whether the losing hours sit at one end of his trading day, so a cut-off is honest.

    **This is the check that stops the card from proposing a rule the evidence does not
    support.** A single bad hour in the middle of a good day is a finding; it is not a
    reason to ban everything before it.
    """
    hours = [group for group in statistics.get("breakdowns", {}).get("by_hour", [])
             if group.get("is_significant")]

    if len(hours) < 3:
        return None

    losing = sorted(int(g["key"]) for g in hours if g.get("net_pnl", 0) < 0)
    winning = sorted(int(g["key"]) for g in hours if g.get("net_pnl", 0) >= 0)

    if not losing or not winning or int(bad_hour) not in losing:
        return None

    # Every losing hour earlier than every winning one: a morning he should not be trading.
    if max(losing) < min(winning):
        return TraderRule.NO_BEFORE, min(winning)

    # And the mirror of it, an afternoon he should be done before.
    if min(losing) > max(winning):
        return TraderRule.NO_AFTER, max(winning)

    return None

# ------------------------- END ------------------------- #
