import re



# ------------------------- SYMBOL NORMALIZATION START ------------------------- #
#
# MNQM6 and MNQU6 are the same chart. So are NQ, MNQ and the nano contract - one is a
# quarter the size of the next, but the price action, the session, the setups and the hours
# are identical. Splitting them apart scatters a trader's history across buckets that are
# too small to be significant, and hides the very edge the statistics exist to find.
#
# Two steps, in order:
#   1. Drop the contract month and year, so MNQU6 becomes MNQ.
#   2. Fold the size variants onto the family root, so MNQ becomes NQ.
#
# The raw symbol is still stored on every trade. Only the analysis groups by the family.


# Futures month codes: Jan through Dec, in order.
MONTH_CODES = "FGHJKMNQUVXZ"

# Every family we can name, with the label a trader would recognise. The root is what the
# whole family collapses onto.
INSTRUMENT_FAMILIES = {
    # ------------- EQUITY INDEX:
    "ES":  "S&P 500",
    "NQ":  "נאסד\"ק 100",
    "YM":  "דאו ג'ונס",
    "RTY": "ראסל 2000",

    # ------------- ENERGY:
    "CL":  "נפט גולמי",
    "NG":  "גז טבעי",
    "RB":  "בנזין",
    "HO":  "סולר",

    # ------------- METALS:
    "GC":  "זהב",
    "SI":  "כסף",
    "HG":  "נחושת",
    "PL":  "פלטינה",

    # ------------- RATES:
    "ZB":  "אג\"ח 30 שנה",
    "ZN":  "אג\"ח 10 שנים",
    "ZF":  "אג\"ח 5 שנים",
    "ZT":  "אג\"ח שנתיים",

    # ------------- CRYPTO:
    "BTC": "ביטקוין",
    "ETH": "את'ריום",

    # ------------- FX:
    "6E":  "יורו",
    "6B":  "לירה שטרלינג",
    "6J":  "ין יפני",
    "6A":  "דולר אוסטרלי",
    "6C":  "דולר קנדי",
    "6S":  "פרנק שוויצרי",

    # ------------- AGRICULTURE:
    "ZC":  "תירס",
    "ZS":  "פולי סויה",
    "ZW":  "חיטה",
}

# Size variants whose name does not simply prefix the root. The generic micro/nano rule
# below handles MNQ, MES, MCL and friends; these are the ones that break the pattern.
EXPLICIT_ALIASES = {
    "M2K": "RTY",   # micro Russell is not "MRTY"
    "MBT": "BTC",   # micro Bitcoin
    "MET": "ETH",   # micro Ether
    "QM":  "CL",    # e-mini crude
    "QG":  "NG",    # e-mini natural gas
    "QO":  "GC",    # e-mini gold
    "QC":  "HG",    # e-mini copper
    "SIL": "SI",    # micro silver
    "MGC": "GC",
    "MCL": "CL",
    "MNG": "NG",
}

# A size prefix only counts when what is left is a family we know. That guard is what stops
# NG (natural gas) being read as a nano contract of a nonexistent "G".
SIZE_PREFIXES = ["M", "N"]


def strip_contract_code(symbol):
    """
    MNQU6 -> MNQ. Removes the month letter and year digits a futures ticker carries.

    Handles the shapes exports actually use: MNQU6, MNQZ25, /ESH25, "ES 12-25", ESH5.
    """
    text = (symbol or "").strip().upper()
    if not text:
        return ""

    # Some platforms prefix futures with a slash.
    text = text.lstrip("/")

    # "ES 12-25" and "ES DEC 25" carry the expiry after a separator.
    text = re.split(r"[\s_]", text)[0]

    # Root + month letter + one or two year digits, at the end of the ticker.
    match = re.match(rf"^([A-Z0-9]{{1,4}}?)([{MONTH_CODES}])(\d{{1,2}})$", text)
    if match:
        root = match.group(1)
        # A root of one character is almost certainly a misread - "M6" is not a contract.
        if len(root) >= 2:
            return root

    return text


def family_root(symbol):
    """MNQ -> NQ. Folds a size variant onto the family it belongs to."""
    text = (symbol or "").strip().upper()
    if not text:
        return ""

    if text in EXPLICIT_ALIASES:
        return EXPLICIT_ALIASES[text]

    if text in INSTRUMENT_FAMILIES:
        return text

    # Micro and nano variants: the prefix only counts if the remainder is a family we know.
    for prefix in SIZE_PREFIXES:
        if text.startswith(prefix):
            remainder = text[len(prefix):]
            if remainder in INSTRUMENT_FAMILIES:
                return remainder
            if remainder in EXPLICIT_ALIASES:
                return EXPLICIT_ALIASES[remainder]

    return text


def normalize_symbol(symbol):
    """
    The full pipeline: raw ticker in, family root out.

    Anything we do not recognise - a stock, an FX pair, an unknown ticker - is returned as
    it came, uppercased. Guessing at an unknown symbol would merge two instruments that have
    nothing to do with each other, which is far worse than leaving them apart.
    """
    return family_root(strip_contract_code(symbol))


def instrument_label(instrument):
    """A recognisable name for the chart, or the ticker itself when we have no name."""
    return INSTRUMENT_FAMILIES.get(instrument, instrument)

# ------------------------- SYMBOL NORMALIZATION END ------------------------- #
