from analytics.formatting import trades as trade_count

from .compliance import build_rules, check_plan
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

# **A ratio and not "zero kept", which is what it was.** The trader wrote "only enter on a
# gamble" - a rule he obviously wants gone - and it was kept on the two trades he had
# actually tagged `gamble` out of hundreds. Two out of two hundred is a wish by any reading,
# and demanding a perfect zero meant the one rule most worth retiring was the one the engine
# could not see.
BARELY_KEPT = 0.1

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

    return (_retire(user, currency, timezone_name, declined)
            or _add(user, recent, statistics, currency, timezone_name, declined, asked))



# ------------------------- "SHOULD WE DROP THIS ONE?" ------------------------- #

def _retire(user, currency, timezone_name, declined):
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

        key = f"retire:{row.id}"

        if key in declined:
            continue

        judged = entry.get("checked", 0)
        broke = entry.get("broke", 0)
        name = entry["rule"]

        if broke == 0 and judged >= GRADUATED_AFTER:
            return {
                "action": "retire",
                "key": key,
                "rule_id": row.id,
                "title": f'שמרת על "{name}" {trade_count(judged)} ברצף, אפס חריגות.',
                "detail": "זה כבר לא כלל — זה אתה. אפשר להוריד אותו ולפנות מקום למשהו שעוד נבדק.",
                "accept": "להוריד",
                "decline": "להשאיר",
            }

        if judged >= NEVER_KEPT_AFTER and broke >= judged * (1 - BARELY_KEPT):
            return {
                "action": "retire",
                "key": key,
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
                "detail": "כלל שהתשובה עליו קבועה כבר לא אומר לך כלום בתחקיר. "
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
