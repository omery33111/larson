import json
import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone as dj_timezone

from analytics.evidence import describe_trade
from analytics.statistics import _instrument_of, _safe_zone, clean_label

from trades.models import Trade

from .context import MODEL


log = logging.getLogger(__name__)



# ------------------------- RETRIEVAL START ------------------------- #
#
# **"What happened on the 18th?" used to have no answer, and the reason was the whole design:
# the prompt carries aggregates, never rows.** This file is how a specific trade reaches the
# conversation - and the shape of it is the entire security argument, so it is written down
# here rather than left to be inferred.
#
# **The model does not query. It returns parameters, and python queries.**
#
# The tempting version is a tool - `get_trades(filters)` - and that is exactly the surface a
# prompt injection wants: the filter lives inside the tool, the model composes the call, so
# anything that can talk to the model can compose it too. Instead this is the same shape as
# `trades/llm_mapping.py`, which has been in the product since milestone 7 for the same
# reason: **the model answers one narrow question, returns names, and python validates them
# against what already exists before anything is read.**
#
# Three invariants hold it. Each has a test, and each of those tests has been watched to fail.
#
#   1. **`user` is not a parameter anywhere in the chain.** `fetch` takes a user object, which
#      the view takes from `request.user`. There is no key in the intent schema that names a
#      user, an id, or an account belonging to anyone - **so there is no value the model can
#      emit that changes whose rows are read.** The filter is a literal at the call site.
#
#   2. **Every field the model may name is an enum in python.** Nothing it returns is ever
#      passed to `.filter()` as a field name, and there is no `**kwargs` into the ORM. An
#      invented field, an unknown outcome or a symbol the trader has never traded is dropped
#      on the floor - the worst case is the same answer he would have got without this file.
#
#   3. **Rows are serialised by an explicit list.** A sensitive column added to `Trade` next
#      year does not start flowing into a prompt because it exists. This is the invariant that
#      guards `account_id`, and it is the reason the list is written out rather than derived.
#
# **And one constraint that is performance before it is safety:** the retrieved rows go into
# the *message*, never into the system block. The system block is the cached prefix - four
# thousand tokens of persona and resume that are byte-identical between turns - and injecting
# anything per-question above the cache marker turns every read into a write, silently. That
# rule is already written in CLAUDE.md; this is the first feature with a reason to break it.


# What the model is allowed to say, and nothing else is read.
OUTCOMES = {"win", "loss", "breakeven"}
ORDERS = {"worst", "best", "newest", "longest", "shortest"}

MAX_ROWS = 15

# Cheap and shallow on purpose: it answers "which rows", not "what do they mean".
EFFORT = "low"
MAX_TOKENS = 600


SYSTEM = """אתה ממפה שאלה של סוחר לפרמטרים של שליפה. אתה לא עונה על השאלה ולא מנתח דבר.

החזר JSON יחיד, בלי טקסט לפניו ואחריו, עם המפתחות האלה בלבד — וכל אחד מהם אופציונלי:

{
  "from":    "YYYY-MM-DD",   // תחילת הטווח, אם השאלה מתייחסת לתקופה
  "to":      "YYYY-MM-DD",   // סוף הטווח
  "symbol":  "<מתוך הרשימה שתקבל בלבד>",
  "outcome": "win" | "loss" | "breakeven",
  "order":   "worst" | "best" | "newest" | "longest" | "shortest",
  "limit":   <מספר שלם>
}

כללים:
- מפתח שאינך בטוח בו — **השמט אותו**. אין ניחושים.
- "התאריך של היום" שתקבל הוא ההווה. "השבוע שעבר" ו"החודש" נגזרים ממנו.
- `symbol` חייב להיות אחד מהערכים ברשימה שתקבל, מילה במילה. אם הסוחר הזכיר נכס שאינו ברשימה — השמט.
- אם השאלה אינה מתייחסת לעסקאות מסוימות אלא היא כללית — החזר `{}`.
- אל תמציא מפתחות. מפתח שאינו ברשימה למעלה יידחה בכל מקרה."""


# The deterministic gate in front of the model call. Most questions are general - "what is my
# biggest leak" - and they must not pay a second call, nor the second of silence before the
# first token, which is the thing the whole product feels like.
SPECIFIC_HINTS = (
    "תראה לי", "תן לי", "הראה", "איזו", "איזה", "מתי", "באיזה", "הגרוע", "הגרועות",
    "הטוב", "הטובות", "הכי גדול", "הכי גרוע", "הכי טוב", "הפסד הגדול", "הרווח הגדול",
    "דוגמ", "ספציפ", "בתאריך", "ביום", "השבוע", "החודש", "אתמול", "היום ש",
    "show me", "which trade", "worst", "best", "example",
)

MONTHS = ("ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט",
          "ספטמבר", "אוקטובר", "נובמבר", "דצמבר")



def looks_specific(text):
    """Whether a question is worth a mapping call at all.

    **Deliberately generous in one direction and cheap in the other:** a false positive costs
    a fraction of a cent and nobody notices, a false negative costs the feature. What it
    protects is the common case - a general question paying neither the call nor the pause.
    """
    if not text:
        return False

    lowered = text.lower()

    if any(hint in lowered for hint in SPECIFIC_HINTS):
        return True

    if any(month in text for month in MONTHS):
        return True

    # A bare number in a question is usually a date or a count: "18/8", "the 5 worst".
    return any(character.isdigit() for character in text)



def block_for(user, text, billed_to = None):
    """The prompt block for a specific question, or "" when there is nothing to add.

    Returns a string because that is all the caller is allowed to do with it: append it to
    the trader's own turn. Nothing here reaches the system block.
    """
    if not looks_specific(text):
        return ""

    symbols = _own_instruments(user)
    if not symbols:
        return ""

    intent = _extract(text, symbols, billed_to)
    if not intent:
        return ""

    rows = _fetch(user, intent)
    if not rows:
        return _nothing_found(intent)

    return _render(rows, intent)



def attach(messages, block):
    """Append the block to the trader's own turn, and nowhere else.

    **The last turn is new content by definition** - it is the question just asked - so adding
    to it cannot cost a cache read. The same text in the system block would change the cached
    prefix on every question and turn every read into a write, with nothing anywhere saying so.
    """
    if not block or not messages:
        return messages

    last = messages[-1]
    if last.get("role") != "user":
        return messages

    content = last.get("content")

    if isinstance(content, str):
        last["content"] = content + block
    elif isinstance(content, list) and content and isinstance(content[-1], dict):
        content[-1]["text"] = content[-1].get("text", "") + block

    return messages



# ------------- WHAT THE TRADER HIMSELF HAS TRADED:
def _own_instruments(user):
    """The symbols the model is allowed to name - **drawn from this trader's own rows.**

    This is invariant 2 in its most useful form: the vocabulary offered to the model is a
    closed set that already belongs to the person asking, so a ticker it invents has nowhere
    to land even before validation rejects it.
    """
    values = (Trade.objects.filter(user = user)
                           .values_list("instrument", "symbol")
                           .distinct()[:200])

    out = set()
    for instrument, symbol in values:
        for value in (instrument, symbol):
            cleaned = clean_label(value or "")
            if cleaned:
                out.add(cleaned)

    return sorted(out)



# ------------- THE MAPPING CALL:
def _extract(text, symbols, billed_to):
    """One narrow question to the model. Returns {} for every kind of failure."""
    if not settings.ANTHROPIC_API_KEY:
        return {}

    try:
        import anthropic
    except ImportError:
        return {}

    payload = {
        "השאלה": text[:1000],
        "התאריך_של_היום": dj_timezone.now().date().isoformat(),
        "הנכסים_שהסוחר_סחר": symbols,
    }

    try:
        client = anthropic.Anthropic(api_key = settings.ANTHROPIC_API_KEY)

        message = client.messages.create(
            model = MODEL,
            max_tokens = MAX_TOKENS,
            output_config = {"effort": EFFORT},
            system = SYSTEM,
            messages = [{"role": "user",
                         "content": json.dumps(payload, ensure_ascii = False, default = str)}],
        )
    except Exception:
        # A failed mapping is the same thing as a general question: the answer is still given,
        # just without rows attached. This line is the only way to tell them apart afterwards.
        log.exception("Retrieval mapping call failed")
        return {}

    # Every call to the model is on the meter, including this one. A ledger with a hole in it
    # stops being a ledger - the same rule the column mapper follows.
    if billed_to is not None and getattr(message, "usage", None):
        from usage import budget
        budget.record(billed_to, "retrieval", message.usage)

    if message.stop_reason == "refusal":
        return {}

    body = "".join(block.text for block in message.content if block.type == "text").strip()

    return _validate(body, symbols)


def _validate(body, symbols):
    """
    The guard the whole route rests on.

    **Nothing the model said is trusted and nothing it invented survives.** Keys outside the
    schema are dropped rather than ignored, which matters: a dict that still carries them
    would hand the next reader of this code a parameter that looks supported.
    """
    try:
        start = body.index("{")
        proposed = json.loads(body[start:body.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {}

    if not isinstance(proposed, dict):
        return {}

    intent = {}

    for key in ("from", "to"):
        parsed = _date(proposed.get(key))
        if parsed:
            intent[key] = parsed

    # A range the wrong way round is a typo, not a request for nothing.
    if intent.get("from") and intent.get("to") and intent["from"] > intent["to"]:
        intent["from"], intent["to"] = intent["to"], intent["from"]

    symbol = clean_label(proposed.get("symbol") or "")
    if symbol in set(symbols):
        intent["symbol"] = symbol

    outcome = proposed.get("outcome")
    if isinstance(outcome, str) and outcome in OUTCOMES:
        intent["outcome"] = outcome

    order = proposed.get("order")
    if isinstance(order, str) and order in ORDERS:
        intent["order"] = order

    limit = proposed.get("limit")
    if isinstance(limit, int) and limit > 0:
        intent["limit"] = min(limit, MAX_ROWS)

    return intent


def _date(value):
    """A date, or nothing. No formats beyond the one the schema asked for."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None



# ------------- THE QUERY, WHICH PYTHON OWNS:
def _fetch(user, intent):
    """
    The rows.

    **`user` is the first argument and it is not in the intent.** The model cannot name it,
    reach it, or change it; the view passes `request.user` and nothing else is accepted. Every
    field below is a literal in this file - there is no path from the model's output to a
    field name, and no dictionary is expanded into the filter.
    """
    rows = Trade.objects.filter(user = user)

    if intent.get("from"):
        rows = rows.filter(executed_at__date__gte = intent["from"])

    if intent.get("to"):
        rows = rows.filter(executed_at__date__lte = intent["to"])

    if intent.get("symbol"):
        # The symbol may be either the raw ticker or the folded family, because both are
        # offered to the model and a trader says whichever he thinks in.
        from django.db.models import Q
        rows = rows.filter(Q(symbol = intent["symbol"]) | Q(instrument = intent["symbol"]))

    if intent.get("outcome"):
        rows = rows.filter(outcome = intent["outcome"])

    order = intent.get("order")
    ordering = {
        "worst": "pnl",
        "best": "-pnl",
        "newest": "-executed_at",
        "longest": "-duration_seconds",
        "shortest": "duration_seconds",
    }.get(order, "executed_at")

    limit = intent.get("limit") or MAX_ROWS

    return list(rows.order_by(ordering)[:min(limit, MAX_ROWS)])



# ------------- WHAT THE MODEL RECEIVES:
#
# An explicit list and not a serializer over the model, which is invariant 3. `describe_trade`
# already decides what a named trade looks like everywhere else in the product, so the block
# cannot drift from the examples attached to a finding.
def _render(rows, intent):
    currency = rows[0].currency or "USD"
    tz = _safe_zone(rows[0].source_timezone or "Asia/Jerusalem", rows)

    lines = [describe_trade(trade, tz, currency) for trade in rows]

    return ("\n\n---\n\n"
            "**עסקאות ספציפיות שנשלפו עבור השאלה הזו, מהרשומה של הסוחר עצמו.**\n"
            f"{_describe_intent(intent)}\n\n"
            + "\n".join(f"- {line}" for line in lines)
            + "\n\n**השתמש בהן בשמן ובתאריכן.** אם הן לא עונות על השאלה — תגיד זאת, "
              "ואל תסיק מהן יותר ממה שכתוב בהן.")


def _nothing_found(intent):
    """An empty result is an answer, and a better one than a guess.

    Without this the model receives no block at all and answers from the aggregates - which
    reads to the trader as being told about his averages when he asked about a Tuesday.
    """
    return ("\n\n---\n\n"
            f"**חיפוש בעסקאות של הסוחר לא מצא שורות מתאימות.** {_describe_intent(intent)}\n"
            "אמור לו במפורש שלא נמצאו עסקאות בטווח או בתנאים שביקש, ואל תענה מהממוצעים "
            "כאילו היו תשובה לשאלה הספציפית.")


def _describe_intent(intent):
    """What was actually searched for, so a wrong reading of the question is visible."""
    parts = []

    if intent.get("from") or intent.get("to"):
        start = intent.get("from").isoformat() if intent.get("from") else "ההתחלה"
        end = intent.get("to").isoformat() if intent.get("to") else "היום"
        parts.append(f"טווח: {start} עד {end}")

    if intent.get("symbol"):
        parts.append(f"נכס: {intent['symbol']}")

    if intent.get("outcome"):
        parts.append({"win": "רווחיות בלבד", "loss": "מפסידות בלבד",
                      "breakeven": "באיזון בלבד"}[intent["outcome"]])

    if intent.get("order"):
        parts.append({"worst": "הגרועות ראשונות", "best": "הטובות ראשונות",
                      "newest": "האחרונות ראשונות", "longest": "הארוכות ראשונות",
                      "shortest": "הקצרות ראשונות"}[intent["order"]])

    return ("מה שחופש: " + " · ".join(parts)) if parts else "חיפוש כללי בעסקאות האחרונות."

# ------------------------- RETRIEVAL END ------------------------- #
