
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
