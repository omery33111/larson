
# ------------------------- NUMBER FORMATTING START ------------------------- #
#
# Every number the user reads passes through here.
#
# A bare "10.35" in a sentence is unreadable: it could be dollars, a percentage, points or
# a ratio, and the reader has to guess. Guessing wrong about your own P&L is worse than not
# being told at all, so no number is rendered without its unit attached.


CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "ILS": "₪",
    "JPY": "¥",
}


def money(value, currency = "USD"):
    """`$1,234.50`, `-$85`. The sign sits outside the symbol, the way a statement reads."""
    if value is None:
        return "—"

    symbol = CURRENCY_SYMBOLS.get((currency or "USD").upper())
    amount = abs(float(value))

    # Whole amounts lose the decimals; anything else keeps two.
    text = f"{amount:,.0f}" if amount == int(amount) else f"{amount:,.2f}"
    sign = "-" if value < 0 else ""

    if symbol:
        return f"{sign}{symbol}{text}"

    return f"{sign}{text} {(currency or '').upper()}".strip()


def percent(value, decimals = 2):
    if value is None:
        return "—"
    return f"{round(float(value), decimals):g}%"


def ratio(value, decimals = 2):
    """A pure ratio - profit factor, win/loss, recovery factor. Carries no unit by nature."""
    if value is None:
        return "—"
    return f"{round(float(value), decimals):g}"


def points(value, decimals = 2):
    if value is None:
        return "—"
    return f"{round(float(value), decimals):g} נק'"


def trades(count):
    """Hebrew needs the singular for one."""
    if count is None:
        return "—"
    return "עסקה אחת" if count == 1 else f"{count} עסקאות"


def days(count):
    if count is None:
        return "—"
    return "יום אחד" if count == 1 else f"{count} ימים"


def minutes(value, decimals = 1):
    if value is None:
        return "—"
    return f"{round(float(value), decimals):g} דק'"

# ------------------------- NUMBER FORMATTING END ------------------------- #



# ------------------------- QUOTING A TRADER'S OWN WORD ------------------------- #

def quoted(value):
    """
    A tag or a rule of his, placed inside a Hebrew sentence without the sentence falling
    apart around it.

    **Measured on the live site, in a refusal he sent back.** The server wrote

        התנאי הזה סותר כלל ... "להיכנס רק בלי fvg, ifvg ולא cisd". שניהם מדברים על "ifvg" ...

    and what rendered read `ולא "ifvg" שניהם מדברים על "cisd"` - the two terms swapped
    places. **A sentence that names the wrong tag is worse than no sentence**, and he read
    it as the software being confused rather than as his rule being refused.

    The cause is the bidirectional algorithm, not the text: quotes, commas and the full
    stop around a latin run are neutral characters, so they take their direction from
    whichever side wins, and a latin run at the end of an RTL clause drags them with it.

    **U+2068 and U+2069 are the characters the standard provides for exactly this** - the
    run inside is laid out on its own and cannot reorder anything around it. They are
    invisible, they need no markup, and they therefore work the same in the browser, in an
    email body and in a plain-text log, which is more than a `<span dir>` can say.
    """
    return f"⁨\"{value}\"⁩"


# ------------------------- QUOTING END ------------------------- #
