import json

from django.conf import settings



# ------------------------- THE MAPPING FALLBACK START ------------------------- #
#
# What to do with a file whose headers the dictionary has never seen.
#
# Three rules hold this in place, and each of them is the reason it is safe to let a model
# near the ingestion engine at all:
#
# 1. **The dictionary goes first, always.** This runs only when the deterministic mapping
#    cannot produce the required fields. Every known vendor still costs nothing and stays
#    reproducible, and `COLUMN_SYNONYMS` remains the thing to extend.
#
# 2. **The model maps; it never parses.** It answers one question - which column is which -
#    and returns names. Every value in the file is still read by the same deterministic code
#    that reads a TradeReport export. The model never sees a number it could round, reformat
#    or invent.
#
# 3. **Its answer is checked against the file.** A field it does not recognise, or a column
#    name that is not actually in the file, is dropped. A hallucinated header therefore
#    cannot reach the parser - the worst case is that the file is rejected with the same
#    explanation it would have got without this route.

MODEL = "claude-opus-5"

# One column-naming question. There is nothing to reason deeply about here, and the answer is
# checked against the file either way.
EFFORT = "low"

MAX_TOKENS = 2000

# Enough values to settle what a column actually holds - "Result" is P&L in one journal and
# win/loss in another - and few enough that the prompt stays small.
SAMPLE_ROWS = 8


# What each canonical field means, in the terms a trading export would use. This is the whole
# specification the model is given; it never sees our parsing rules.
FIELDS = {
    "closed_date": "the date the trade was closed (required)",
    "closed_time": "the time of day the trade was closed, when it is in its own column",
    "opened_date": "the date the trade was opened",
    "opened_time": "the time of day the trade was opened",
    "symbol": "the ticker or instrument traded, e.g. MNQU6, AAPL, EURUSD (required)",
    "direction": "long/short, buy/sell, or the side of the trade",
    "quantity": "size: contracts, shares, lots",
    "entry_price": "the price the trade was entered at",
    "exit_price": "the price the trade was exited at",
    "pnl": "the money result of the trade, profit or loss (required unless entry and exit "
           "prices are both present)",
    "points": "the result in points or ticks rather than money",
    "fees": "commission or fees charged on the trade",
    "r_multiple": "the result expressed in R (multiples of the risk taken)",
    "stop_loss": "the stop loss price",
    "take_profit": "the take profit or target price",
    "orders_count": "how many orders or fills made up the trade",
    "duration": "how long the trade was held, as a duration",
    "setups": "the strategy or setup name the trader tagged the trade with",
    "tags": "free tags on the trade",
    "mistakes": "mistakes the trader recorded on the trade",
    "notes": "the trader's written notes",
    "rating": "the trader's own score for the trade",
    "screenshot_url": "a link to a chart image",
    "status": "the outcome as a word: win/loss/breakeven, green/red, profit/loss",
    "account_id": "the account number or name the trade belongs to",
    "currency": "the currency of the money columns",
}


SYSTEM = """You map the columns of a trading journal export onto a fixed set of field names.

You are given the file's column headers and a few sample values from each. Return which
header holds which field.

Rules:
- Answer with JSON only: an object of {"field_name": "exact column header"}. No prose.
- Use only the field names you were given, and only column headers that appear in the input,
  copied exactly as they were written.
- Map a field only when the sample values actually support it. A header alone is not enough:
  a column called "Result" holding 137 and -132 is `pnl`, and the same header holding "Win"
  and "Loss" is `status`.
- Leave out anything you are not confident about. A missing field is recoverable; a wrong one
  silently corrupts the trader's record.
- One header maps to at most one field."""



def map_with_model(headers, sample, known, billed_to = None):
    """
    Returns {field: header} for the fields the dictionary could not find.

    `known` is what the deterministic pass already resolved, so the model is not asked to
    re-decide anything that is settled. Returns {} whenever it cannot help - a missing key,
    a failed call or an unusable answer are all the same thing here, and all of them simply
    leave the file to be rejected with the ordinary explanation.
    """
    if not settings.ANTHROPIC_API_KEY:
        return {}

    wanted = {field: description for field, description in FIELDS.items() if field not in known}

    if not wanted:
        return {}

    try:
        import anthropic
    except ImportError:
        return {}

    payload = {
        "fields_to_find": wanted,
        "already_identified": {field: str(column) for field, column in known.items()},
        "columns": {
            str(header): [_readable(value) for value in values[:SAMPLE_ROWS]]
            for header, values in sample.items()
            # A column the dictionary already claimed is not on offer.
            if str(header) not in {str(c) for c in known.values()}
        },
    }

    try:
        client = anthropic.Anthropic(api_key = settings.ANTHROPIC_API_KEY)

        message = client.messages.create(
            model = MODEL,
            max_tokens = MAX_TOKENS,
            output_config = {"effort": EFFORT},
            system = SYSTEM,
            messages = [{"role": "user", "content": json.dumps(payload, ensure_ascii = False,
                                                               default = str)}],
        )
    except Exception:
        return {}

    # Small and rare, but it is a call to the model - and a ledger with a hole in it stops
    # being a ledger. This is also the only model call the product makes that is NOT behind
    # the chat's own gate, so without this it would be the way around the budget entirely.
    if billed_to is not None and getattr(message, "usage", None):
        from usage import budget
        budget.record(billed_to, "mapping", message.usage)

    if message.stop_reason == "refusal":
        return {}

    text = "".join(block.text for block in message.content if block.type == "text").strip()

    return _validate(text, headers, known)


def _readable(value):
    """Sample values go over as text; the model is choosing a column, not reading a number."""
    text = str(value)
    return text[:60]


def _validate(text, headers, known):
    """
    Keeps only what the file can actually support.

    This is the guard that makes the whole route safe: a field name we do not have, a column
    that is not in the file, or a column already taken is dropped on the floor. Nothing the
    model says reaches the parser without existing first.
    """
    try:
        start = text.index("{")
        proposed = json.loads(text[start:text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {}

    if not isinstance(proposed, dict):
        return {}

    by_name = {str(header): header for header in headers}
    taken = {str(column) for column in known.values()}

    resolved = {}

    for field, column in proposed.items():
        if field not in FIELDS or field in known:
            continue

        name = str(column)

        if name not in by_name or name in taken:
            continue

        resolved[field] = by_name[name]
        taken.add(name)

    return resolved

# ------------------------- THE MAPPING FALLBACK END ------------------------- #
