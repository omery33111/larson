import json
import logging
import re

from django.conf import settings

from analytics.statistics import _split_tags, clean_label
from chat.context import MODEL



# ------------------------- HIS SENTENCE, INTERPRETED ONCE ------------------------- #
#
# **The whole design is in when this runs: at save time, never at check time.**
#
# The obvious way to check "only enter when delta is high and there is an IFVG" is to hand
# the model the rule and the trade and ask whether it was kept. That is the version to avoid,
# for three separate reasons and any one of them is enough: it costs a call per trade per
# rule, it can answer differently on two identical trades, and it makes compliance an opinion
# in a product whose iron law is that every number is computed in python.
#
# So the sentence is interpreted **once**, into terms stored on the row, and every check
# after that is python comparing strings. Same pattern as `llm_mapping.py`, and for the same
# reason: **the model maps, python judges.** Bought once per rule rather than once per trade,
# identical on every run, and able to name the offending trade by date and time.
#
# **What it cannot do, stated plainly, because the screen has to say it too:** a term can
# only be found in text the trade actually carries. Entry time is a column on every row, so
# an hour rule is always judgeable. "Delta was high" is a column nowhere. If he never tagged
# it, the trade cannot answer - and `coverage()` is how he finds that out when he saves the
# rule, rather than after a month of debriefs that quietly judged nothing.


MAX_REQUIREMENTS = 4
MAX_SPELLINGS = 4
MAX_FORBIDDEN = 4
MAX_TERM_LENGTH = 40

MAX_RULE_LENGTH = 200

log = logging.getLogger(__name__)


BRIEF = """אתה מתרגם כלל מסחר שסוחר כתב לעצמך למונחים שניתן לחפש בטקסט של עסקה.

הטקסט של עסקה הוא התגיות, הסטאפים, הטעויות וההערות שהסוחר עצמו רשם עליה — ותו לא.
אין לך גישה למחיר, לנפח, לאינדיקטורים או לכל נתון שוק. תרגם אך ורק למילים שסביר
שסוחר יקליד בתגית או בהערה.

החזר JSON בלבד, בדיוק בצורה הזו:

{"require": [["ifvg", "inverse fvg"], ["delta"]], "forbid": ["news"]}

"require" — רשימה של דרישות. **כל דרישה חייבת להתקיים; בתוך דרישה מספיק מונח אחד.**
"forbid"  — מונחים שנוכחותם שוברת את הכלל.

**זה ההבדל שחייב לצאת נכון:**
- "רק כשיש IFVG **או** CISD" → דרישה אחת עם שניהם:  {"require": [["ifvg", "cisd"]]}
- "רק כשיש IFVG **וגם** דלתא" → שתי דרישות נפרדות:  {"require": [["ifvg"], ["delta"]]}

בתוך דרישה אחת תן גם את האיותים הסבירים של אותו מושג — אנגלית, עברית, קיצור ומילה
מלאה — עד 4 בסך הכל.

כללים קשיחים:
- מונח הוא מילה או צירוף קצר, באותיות קטנות, בלי סימני פיסוק ובלי מירכאות.
- אל תמציא מושגים שלא נאמרו. "רק כשיש IFVG" הוא דרישה אחת, לא שלוש.
- תנאי על מחיר, על אחוזים או על כל דבר שאינו מילה שסוחר מקליד — דלג עליו.
- אם אין בכלל מונח שאפשר לחפש בטקסט, החזר {"require": [], "forbid": []}.

**`התגיות_שהסוחר_משתמש_בהן` היא רשימת התגיות שהוא באמת כתב על העסקאות שלו.** אם אחת מהן
מתארת את מה שהכלל מבקש — **תן אותה בדיוק כפי שהיא כתובה שם**, והוסף אותה לאיותים. היא
הניחוש היחיד שבטוח קיים ברשומה שלו. כשהרשימה ריקה, תן את האיותים הסבירים מהידע שלך."""


# **A trader's distinct tag vocabulary is small and this ceiling only has to be above it.**
# 60 was a guess, and a ceiling that hides the one label the rule is about defeats the entire
# mechanism - the labels are short, so 400 of them is still a small payload.
MAX_VOCABULARY = 400


def vocabulary(user):
    """
    **The words this trader actually tags with**, which is a far better input than the
    model's general knowledge of what a term might be called.

    It expanded `CISD` into `change in state of delivery` on its own, from what it knows
    about the term - and that happened to be right. **But it is a one-shot guess**: a trader
    who tags `שינוי במצב האספקה`, or `delivery shift`, gets a miss, and nothing says so until
    a month of debriefs has quietly judged nothing.

    Handing it his own labels replaces the guess with the answer. Same move as
    `_own_instruments` in `chat/retrieval.py`, and for the same reason: **a vocabulary drawn
    from his own rows is the only one guaranteed to exist in them.**

    Not a security boundary here - these are his own labels going back into his own prompt -
    but it is bounded and cleaned anyway, because this is free text out of a spreadsheet and
    it is about to be written into a prompt.
    """
    from trades.models import Trade

    seen = []

    rows = Trade.objects.filter(user = user).values_list("setups", "tags", "mistakes")

    for columns in rows.iterator():
        for raw in columns:
            for token in _split_tags(raw or ""):
                token = clean_label(token, MAX_TERM_LENGTH)
                if token and token not in seen:
                    seen.append(token)
                    if len(seen) >= MAX_VOCABULARY:
                        return seen

    return seen


def interpret(sentence, billed_to = None, known_labels = ()):
    """
    His sentence to searchable terms, or `None` when nothing in it can be searched for.

    `None` is a real answer and the caller must refuse the rule on it: "keep risk sensible"
    carries no term a trade could ever carry, and saving it would produce a rule that is
    kept by every trade forever.
    """
    sentence = clean_label(sentence, MAX_RULE_LENGTH)

    if not sentence:
        return None

    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key = settings.ANTHROPIC_API_KEY)

        response = client.messages.create(
            model = MODEL,
            max_tokens = 1000,
            # Naming terms in a sentence is not a reasoning problem, and this runs while he
            # watches the save spinner.
            output_config = {"effort": "low"},
            system = BRIEF,
            messages = [{"role": "user", "content": json.dumps({
                "הכלל": sentence,
                # **His own labels, so the terms come back as strings that exist in his
                # record rather than as plausible guesses about what they might be called.**
                "התגיות_שהסוחר_משתמש_בהן": list(known_labels)[:MAX_VOCABULARY],
            }, ensure_ascii = False)}])

    except Exception:
        # The caller turns this into "we could not read the rule, try plainer wording" - a
        # saved rule with no terms would be a rule that never fires and never says so.
        log.exception("Rule interpretation call failed")
        return None

    # Every call to the model is on the meter, including this one, and it is recorded before
    # the refusal check: a refusal was still generated and still billed.
    if billed_to is not None and getattr(response, "usage", None):
        from usage import budget
        budget.record(billed_to, "rule_interpret", response.usage)

    # A refusal arrives as a 200 with no answer in it, and reading `content` first is how
    # that becomes an unrelated crash two lines later.
    if response.stop_reason == "refusal":
        return None

    return _validate(_json_from(response), known_labels)


def _json_from(response):
    """The object out of the reply, whatever else the reply wrapped it in."""
    text = ""

    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            text += block.text

    match = re.search(r"\{.*\}", text, re.S)

    if not match:
        return {}

    try:
        return json.loads(match.group(0))
    except (ValueError, TypeError):
        return {}


def _validate(body, known_labels = ()):
    """
    Nothing the model returned survives this that was not asked for.

    Same contract as `_validate` in `llm_mapping.py`: an unexpected key is dropped rather
    than carried, because a dict that keeps it hands the next reader a parameter that looks
    supported. The caps are not politeness - they are what stops a confused reply from
    turning into a rule that matches every trade or none.
    """
    if not isinstance(body, dict):
        return None

    # **A short term is only trusted when it came from his own labels.** `TL` out of his
    # vocabulary is his abbreviation and is exact; `TL` invented by the model is two letters
    # that appear inside ordinary words, and nobody could have guessed a personal shorthand
    # anyway. Dropping it is the difference between a rule that is quiet and one that is wrong.
    labels = [label.lower() for label in known_labels]

    require = []

    for group in _as_list(body.get("require"))[:MAX_REQUIREMENTS]:
        # A bare string is a requirement with one spelling, and the model does write it that
        # way sometimes. Accepting it is not looseness: the meaning is unambiguous.
        spellings = _terms([group] if isinstance(group, str) else _as_list(group),
                           labels)[:MAX_SPELLINGS]

        if spellings:
            require.append(spellings)

    forbid = _terms(_as_list(body.get("forbid")), labels)[:MAX_FORBIDDEN]

    # **A rule with neither side is not a strict rule, it is a rule that cannot be broken.**
    if not require and not forbid:
        return None

    return {"require": require, "forbid": forbid}


def _as_list(value):
    return value if isinstance(value, list) else []


def _terms(values, labels = ()):
    """One line, lowercase, bounded - the same shape every label in this product is held to."""
    out = []

    for value in values:
        if not isinstance(value, str):
            continue

        term = clean_label(value, MAX_TERM_LENGTH).lower().strip(" \"'.,:;-")

        # One character matches almost everything, which reads as a rule that is always kept.
        if len(term) < 2 or term in out:
            continue

        # A short term he does not actually use is a guess that will fire on ordinary words.
        if len(term) < SHORT_TERM and not any(term in label.split() or term == label
                                              for label in labels):
            continue

        out.append(term)

    return out




# **Below this, a term is matched as a whole token and never as a substring.**
#
# `TL` is a real abbreviation a trader uses for "true liquidity", and as a substring it is
# also inside `settle`, `little` and `bottle`. A rule that fires on the word "settled" in a
# note is not a strict rule, it is a broken one - **and it fails in the direction that costs
# most, telling him he kept a rule he did not.** Long terms stay substrings, because that is
# what lets a saved `cisd` find his `cisd-sweep`.
SHORT_TERM = 4


def _tokens(text):
    return set(re.split(r"[^0-9a-z֐-׿]+", text))


def matches(term, haystack, tokens = None):
    """Whether one term is present, by the rule its length earns."""
    if len(term) >= SHORT_TERM:
        return term in haystack

    return term in (tokens if tokens is not None else _tokens(haystack))


def unknown_terms(terms, known_labels):
    """
    The terms that match nothing he has ever written - **where every silent miss lives.**

    A term drawn from his own labels cannot be wrong about what exists. A term the model
    produced from its general knowledge might be: it expanded `CISD` into `change in state
    of delivery`, which was right, and would just as confidently produce a phrasing he never
    uses. **The difference is invisible in the rule and visible here**, so the screen can show
    it instead of letting it fail quietly a month later.
    """
    if not isinstance(terms, dict):
        return []

    wanted = []
    for group in terms.get("require", []):
        wanted += list(group)
    wanted += list(terms.get("forbid", []))

    labels = [label.lower() for label in known_labels]

    # Substring in both directions: a saved `cisd` is found inside his `cisd-sweep`, and his
    # bare `cisd` is found inside a saved `cisd entry`. Either way the term is real.
    return [term for term in wanted
            if not any(term in label or label in term for label in labels)]


def read_back(terms):
    """
    What it will look for, in a line he can check at a glance.

    **The raw `terms` deliberately never reaches the screen** - showing him our structure
    would have him editing our paraphrase instead of his plan. But he does need to be able
    to tell whether "IFVG **or** CISD" was read as one condition or two, because that
    inversion is the difference between a rule almost every trade keeps and one almost
    every trade breaks, **and nothing else on the screen would reveal it.**

    So: one short read-only line, in his own vocabulary, and no way to edit it. If it is
    wrong, the fix is to reword the sentence - which is the thing that should be edited.
    """
    if not isinstance(terms, dict):
        return ""

    parts = [" או ".join(group) for group in terms.get("require", []) if group]

    line = " וגם ".join(parts)

    forbidden = terms.get("forbid", [])
    if forbidden:
        line += (" וגם " if line else "") + "בלי " + " ובלי ".join(forbidden)

    return line


# ------------------------- CAN HIS TRADES EVEN ANSWER IT ------------------------- #

def trade_text(trade):
    """
    Everything the trader himself wrote on one trade, as one lowercase haystack.

    **These four fields and no others.** Price, size and timestamps are numbers the engine
    already judges with proper rules; searching them as text would make "10" match a rule
    about the 10:00 hour and a rule about 10 contracts at once.
    """
    parts = [trade.setups, trade.tags, trade.mistakes, trade.notes]

    return " ".join(part for part in parts if part).lower()


def coverage(trades, terms = None):
    """
    Three numbers, and the third one is the one that matters.

    `answerable` - trades carrying any text at all. Without it a rule reports "kept" across
    a year of trades that said nothing, and he believes a plan he never followed is one he did.

    **`matched` - trades where any term of this rule actually appears**, and it is here
    because of a failure the first version had. A rule about something the engine cannot
    see - the news calendar, the VIX, the spread - produces terms that are nowhere in the
    record. Every trade that *does* carry tags then fails the requirement, so the debrief
    reports a wall of breaches for a rule he may have kept perfectly. **Telling him he broke
    a rule he kept is worse than saying nothing at all**, and `matched == 0` is how that is
    caught at save time rather than discovered a month later.
    """
    rows = list(trades)
    texts = [trade_text(trade) for trade in rows]

    answerable = sum(1 for text in texts if text)

    wanted = []
    if isinstance(terms, dict):
        for group in terms.get("require", []):
            wanted += list(group)
        wanted += list(terms.get("forbid", []))

    # **The same matcher the verdict uses.** A coverage number computed by a second copy of
    # the rule is a number that can disagree with the thing it is describing - the exact
    # failure `statistics.py` exposing its slices was meant to end.
    matched = sum(1 for text in texts
                  if text and any(matches(term, text) for term in wanted)) if wanted else 0

    return {"answerable": answerable, "total": len(rows), "matched": matched}

# ------------------------- END ------------------------- #
