import hashlib
import io
import re
import zipfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from .llm_mapping import map_with_model
from .statements import read_html_tables
from .symbols import normalize_symbol



# ------------------------- INGESTION ENGINE START ------------------------- #
#
# One file in, normalized trades out.
#
# The engine never edits the uploaded file and never converts it to another spreadsheet.
# It reads the table, maps whatever the columns happen to be called onto the canonical
# schema, and returns plain dicts. The original file stays on disk untouched.


SUPPORTED_EXTENSIONS = [".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls", ".html", ".htm"]


# ------------- TIMEZONE:
# Journal exports carry a bare wall clock with no offset. That clock is the trader's own
# local time, so it is localized here and stored as true UTC - anything else silently
# breaks session analysis, because the instruments are traded on US hours while the clock
# in the file is not. ZoneInfo resolves DST per date, so summer and winter trades both land
# on the right instant. The zone is kept per trade so files from different setups can
# coexist, and re-ingesting from the saved originals is what fixes a wrong guess.
DEFAULT_SOURCE_TIMEZONE = "Asia/Jerusalem"


# ------------- COLUMN SYNONYMS:
# The mapper is deterministic, not an LLM. It recognises a column by its header, in Hebrew
# or English, so one parser already covers many journals and broker reports rather than a
# single vendor. Unknown headers are simply ignored - the LLM mapping route (milestone 7)
# is what will handle files this dictionary cannot read.
#
# Provenance of the entries below:
#   TradeReport  - taken from a real export (Hebrew headers), verified end to end.
#   TradeZella   - "Status" carries green / red / breakeven; "Open Date", "Net P&L",
#                  "Entry Model", "Emotions", "Entry Logic Explanation", "Notes For Coaches",
#                  "Profit Target", "Stop Loss" appear in its CSV export.
#   Tradervue    - "Symbol", "Quantity", "Price", "Date", "Time", "Side", "Commission",
#                  "TransFee", "ECNFee", "Option" (documented generic format).
#   TradesViz    - date, time, symbol, asset_type, price, currency, quantity, commiss,
#                  tags, notes, stop_loss, profit_target (documented custom format).
#   Tradovate    - timestamp, account, symbol, side, quantity, price, costs, bought/sold
#                  price and timestamp pairs.
#
# TradeZella and Edgewonk let the user choose which columns to export and do not publish the
# full roster, so their entries are the names actually seen in the wild rather than a
# complete list. Adding a missing header is a one-line change here - never new logic.
COLUMN_SYNONYMS = {
    "account_id": ["חשבון", "מספר חשבון", "account", "account id", "account number", "accountid",
                   "login", "account name", "acct", "account #"],

    "closed_date": ["תאריך סגירה", "תאריך", "close date", "closed date", "closed", "exit date",
                    "date", "trade date", "sell date", "date closed", "sold timestamp",
                    "soldtimestamp", "close timestamp", "exit timestamp", "timestamp"],

    "opened_date": ["תאריך פתיחה", "open date", "opened date", "opened", "entry date", "buy date",
                    "date opened", "bought timestamp", "boughttimestamp", "open timestamp",
                    "entry timestamp"],

    "closed_time": ["שעת סגירה", "close time", "exit time", "closed time", "sell time", "time"],

    "opened_time": ["שעת פתיחה", "open time", "entry time", "opened time", "buy time"],

    "symbol": ["נכס", "סימבול", "מכשיר", "symbol", "instrument", "ticker", "asset", "pair",
               "market", "contract", "security", "product", "item"],

    "direction": ["סוג", "כיוון", "פוזיציה", "direction", "side", "type", "position",
                  "long/short", "buy/sell", "trade type", "position type", "l/s", "b/s"],

    "quantity": ["כמות", "גודל", "quantity", "qty", "size", "volume", "lots", "contracts",
                 "shares", "position size", "net qty", "filled qty", "units"],

    "entry_price": ["מחיר כניסה", "מחיר פתיחה", "entry price", "entry", "open price", "price in",
                    "avg entry", "average entry", "buy price", "entry avg price", "open"],

    "exit_price": ["מחיר יציאה", "מחיר סגירה", "exit price", "exit", "close price", "price out",
                   "avg exit", "average exit", "sell price", "exit avg price", "close"],

    "pnl": ["תוצאה", "רווח הפסד", "רווח/הפסד", "רווח", "pnl", "p&l", "p/l", "net p&l", "net pnl",
            "netpnl", "net p/l", "profit", "net profit", "realized pnl", "realized p&l",
            "gross p&l", "gross pnl", "profit/loss", "profit loss", "net return", "return",
            "net", "result", "$ p&l", "dollar p&l"],

    "points": ["נקודות", "points", "pips", "ticks", "point p&l", "pip p&l"],

    # Broker exports routinely split the cost across several columns. All of them are found
    # and summed, because a single "fees" column is the exception rather than the rule.
    "fees": ["עמלות", "עמלה", "fees", "fee", "commission", "commissions", "commiss", "cost",
             "costs", "transfee", "trans fee", "ecnfee", "ecn fee", "exchange fee", "nfa fee",
             "total fees", "brokerage", "swap", "taxes", "tax"],

    "r_multiple": ["r", "r multiple", "r-multiple", "rmultiple", "rr", "r:r", "realized r",
                   "risk reward", "risk reward ratio", "יחס סיכון סיכוי"],

    "stop_loss": ["סטופ לוס", "סטופ", "stop loss", "stoploss", "stop_loss", "stop", "sl", "s/l",
                  "initial stop", "stop price"],

    "take_profit": ["טייק פרופיט", "טייק", "take profit", "takeprofit", "profit target",
                    "profit_target", "target", "tp", "t/p", "target price"],

    # ------------- EXCURSION:
    # How far the trade ran in favour and against while open. The money versions (MFE/MAE)
    # are the valuable pair; the price versions are the raw high/low the instrument touched.
    #
    # Named every way the major journals write them. MFE: TradeZella/TraderSync "Max Favorable
    # Excursion", Tradervue "Run-up", Edgewonk "MFE", generic "max run up / max profit / max
    # potential profit". MAE: the adverse twin - Tradervue "Drawdown", "Run-down", "Max Adverse
    # Excursion", "max heat", "max loss". A header holding a win/loss word rather than a number
    # is settled off to `status` by value, so "max loss" claiming a figure is safe.
    "mfe": ["רווח מקסימלי", "רווח מרבי", "תנועה מיטיבה מקסימלית", "mfe",
            "max favorable excursion", "max favourable excursion",
            "maximum favorable excursion", "maximum favourable excursion",
            "favorable excursion", "favourable excursion", "run up", "runup", "run-up",
            "max run up", "max runup", "maximum run up", "max profit", "maximum profit",
            "peak profit", "highest profit", "max open profit", "max unrealized profit",
            "max unrealised profit", "max potential profit", "potential profit",
            "best case", "max gain", "maximum gain"],

    "mae": ["הפסד מקסימלי", "הפסד מרבי", "תנועה שלילית מקסימלית", "mae",
            "max adverse excursion", "maximum adverse excursion", "adverse excursion",
            "run down", "rundown", "run-down", "max run down", "max rundown",
            "drawdown", "max drawdown", "maximum drawdown", "trade drawdown",
            "max heat", "heat", "max loss", "maximum loss", "max open loss",
            "max unrealized loss", "max unrealised loss", "max potential loss",
            "worst case", "max pain"],

    "highest_price": ["מחיר גבוה ביותר", "מחיר שיא", "highest price", "high price",
                      "highest", "trade high", "session high", "max price", "price high",
                      "high of trade", "peak price"],

    "lowest_price": ["מחיר נמוך ביותר", "מחיר שפל", "lowest price", "low price",
                     "lowest", "trade low", "session low", "min price", "price low",
                     "low of trade", "trough price"],

    # TradeReport's yes/no "was this trade journaled" flag. Hebrew "כן"/"לא" or English.
    "was_documented": ["תועד", "documented", "is documented", "journaled", "journalled",
                       "logged", "reviewed", "has notes", "written up"],

    "orders_count": ["פקודות", "orders", "executions", "fills", "num orders", "no of trades"],

    "duration": ["סה\"כ זמן", 'סה"כ זמן', "זמן", "duration", "time in trade", "hold time",
                 "holding time", "trade duration", "time held"],

    "setups": ["סטאפים", "סטאפ", "אסטרטגיה", "setup", "setups", "strategy", "playbook", "model",
               "entry model", "system", "trade type setup"],

    "tags": ["תגיות", "tags", "tag", "labels", "label", "confluences", "custom tags"],

    # TradeZella files a trade's emotional state under "Emotions"; those values (Fomo, Greed,
    # Revenge) are the same material the mistakes column carries elsewhere, and they feed the
    # same analysis, so they land in the same field.
    "mistakes": ["טעויות", "טעות", "mistakes", "mistake", "errors", "error", "emotions",
                 "emotion", "what went wrong"],

    "notes": ["סיכום ומסקנות", "הערות", "סיכום", "מסקנות", "notes", "note", "comment", "comments",
              "journal", "summary", "review", "description", "entry logic explanation",
              "how did the trade play out", "notes for coaches", "lessons", "takeaway"],

    "rating": ["דירוג", "ציון", "rating", "grade", "score", "trade grade", "quality"],

    "screenshot_url": ["צילומי מסך", "צילום מסך", "screenshot", "screenshots", "image", "chart",
                       "chart url", "image url", "attachment"],

    "status": ["סטטוס", "status", "outcome", "win/loss", "trade status", "w/l", "trade outcome",
               "won/lost"],

    # TradesViz exports this; most journals do not. Without it every amount would have to be
    # labelled "$" on faith, which is wrong for anyone trading a non-dollar account.
    "currency": ["מטבע", "currency", "ccy", "quote currency", "account currency"],
}

DEFAULT_CURRENCY = "USD"

# Fields whose value is a number. Used to settle headers that two fields both claim - a
# "Result" column holding "win" is a status, one holding "-142.5" is a P&L.
NUMERIC_FIELDS = ["pnl", "points", "fees", "r_multiple", "quantity", "entry_price", "exit_price",
                  "stop_loss", "take_profit", "orders_count", "rating",
                  "mfe", "mae", "highest_price", "lowest_price"]


# ------------- FIELD REQUIREMENTS:
# Deliberately soft. A trade is accepted with a date, a symbol, and some way to know how it
# ended. Everything else deepens the analysis but never blocks a file - most traders do not
# keep a journal as detailed as a dedicated tool exports.
REQUIRED_FIELDS = ["closed_date", "symbol"]

# Optional fields, each mapped to the analysis it unlocks. Shown on the confirmation screen
# so the user sees what depth this particular file supports.
#
# "check" runs against the parsed trades, not against the header row. A journal can export a
# column and leave it empty on every trade - promising an analysis on the strength of a
# header alone would be a lie the statistics engine cannot honour.
ENRICHMENT_FIELDS = {
    "direction": {
        "label": "פילוח לונג מול שורט",
        "columns": ["direction"],
        "check": lambda t: t["direction"] != "unknown",
    },
    "quantity": {
        "label": "ניתוח גודל פוזיציה וסיכון",
        "columns": ["quantity"],
        "check": lambda t: t["quantity"] is not None,
    },
    "opened_at": {
        "label": "פילוח לפי שעת כניסה",
        "columns": ["opened_time"],
        "check": lambda t: t["opened_at"] is not None,
    },
    "duration": {
        "label": "משך החזקה",
        "columns": ["duration", "closed_time", "opened_time"],
        "check": lambda t: t["duration_seconds"] is not None,
    },
    "stop_loss": {
        "label": "חישוב R לכל עסקה",
        "columns": ["stop_loss", "r_multiple"],
        "check": lambda t: t["stop_loss"] is not None or t["r_multiple"] is not None,
    },
    "take_profit": {
        "label": "יחס סיכון־סיכוי",
        "columns": ["take_profit"],
        "check": lambda t: t["take_profit"] is not None,
    },
    "fees": {
        "label": "תוחלת נטו אחרי עמלות",
        "columns": ["fees"],
        "check": lambda t: t["fees"] is not None,
    },
    "setups": {
        "label": "תוחלת לכל סטאפ",
        "columns": ["setups"],
        "check": lambda t: bool(t["setups"]),
    },
    "tags": {
        "label": "זיהוי תנאים חוזרים",
        "columns": ["tags"],
        "check": lambda t: bool(t["tags"]),
    },
    "mistakes": {
        "label": "מנוע הסטייה וזיהוי דליפות",
        "columns": ["mistakes"],
        "check": lambda t: bool(t["mistakes"]),
    },
    "notes": {
        "label": "הבנת ההקשר מאחורי העסקה",
        "columns": ["notes"],
        "check": lambda t: bool(t["notes"]),
    },
    "rating": {
        "label": "השוואת הערכה עצמית לתוצאה בפועל",
        "columns": ["rating"],
        "check": lambda t: t["rating"] is not None,
    },
    "excursion": {
        "label": "רווח/הפסד מקסימלי (MFE/MAE) ואיכות יציאה",
        "columns": ["mfe", "mae"],
        "check": lambda t: t["mfe"] is not None or t["mae"] is not None,
    },
    "price_range": {
        "label": "טווח המחיר בעסקה — גבוה ונמוך ביותר",
        "columns": ["highest_price", "lowest_price"],
        "check": lambda t: t["highest_price"] is not None or t["lowest_price"] is not None,
    },
}


def assess_enrichment(trades, mapping):
    """
    Splits the optional fields into what this file can actually support.

    found   - real values exist, with the coverage so partial data is visible.
    empty   - the column is in the file but never filled. This is the useful one: it tells
              the trader exactly which journal field to start filling to unlock an analysis.
    missing - the export does not contain the column at all.
    """
    found, empty, missing = [], [], []

    for key, field in ENRICHMENT_FIELDS.items():
        coverage = sum(1 for t in trades if field["check"](t))

        if coverage > 0:
            found.append({"key": key, "label": field["label"],
                          "coverage": coverage, "total": len(trades)})
        elif any(column in mapping for column in field["columns"]):
            empty.append({"key": key, "label": field["label"]})
        else:
            missing.append({"key": key, "label": field["label"]})

    return found, empty, missing


LONG_WORDS = ["לונג", "long", "buy", "b", "קנייה", "קניה"]
SHORT_WORDS = ["שורט", "short", "sell", "s", "מכירה"]


# ------------- OUTCOME (win / loss / breakeven):
# A journal that records the outcome itself is authoritative. The trader configured their
# own breakeven range in that tool, and a trade they scratched at -2.50 is a scratch even
# though the arithmetic says "loss". Recomputing it from P&L alone turns dozens of scratches
# into losses and quietly wrecks the win rate.
#
# TradeZella exports this column as "Status" with the values green / red / breakeven, and
# has its own breakeven-range setting; TradeReport (Hebrew) uses רווח / הפסד / BE.
WIN_WORDS = ["win", "won", "winner", "wins", "profit", "profitable", "green", "w", "רווח", "מנצחת", "זכייה"]
LOSS_WORDS = ["loss", "lose", "lost", "loser", "losses", "red", "l", "הפסד", "מפסידה", "הפסדית"]
BREAKEVEN_WORDS = ["be", "b/e", "breakeven", "break even", "break-even", "scratch", "flat",
                   "neutral", "even", "ברייק איבן", "בריק איבן", "איזון", "ללא שינוי"]

WIN = "win"
LOSS = "loss"
BREAKEVEN = "breakeven"

# When no outcome column exists, a scratch has to be inferred from size. An exact zero is
# far too strict - a trade closed a couple of ticks either side of entry is a scratch to the
# trader, not a loss. The band is derived from the trader's own typical trade size, so it
# scales with whatever they risk instead of being a hardcoded dollar figure.
BREAKEVEN_RISK_FRACTION = 0.30



# ------------- HOW BIG THE FILE REALLY IS:
# **An xlsx is a zip, and the upload limit measures the zip.** Twenty megabytes of highly
# compressible XML unpacks to gigabytes, and the reader unpacks all of it into memory before
# anything else looks at it - so a file well inside the limit can take the server down. It
# costs one person one upload.
#
# The zip's own directory says how large each entry will be before any of it is read, which is
# the cheap moment to say no.
#
# The ceiling is deliberately generous: a real twenty-megabyte export of a hundred thousand
# trades unpacks to a few hundred megabytes of verbose XML, and refusing that would be
# refusing a customer. What it stops is the shape that has no honest version - a thousand to
# one and upwards.
MAX_UNCOMPRESSED_MB = 400


def _refuse_a_bomb(file_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            declared = sum(entry.file_size for entry in archive.infolist())
    except zipfile.BadZipFile:
        # Not a zip at all - an .xls, or something broken. The reader below will say so in
        # its own words; this check has nothing to add.
        return

    if declared > MAX_UNCOMPRESSED_MB * 1024 * 1024:
        raise ValueError(
            f"הקובץ נפתח לגודל חריג ({declared // (1024 * 1024)}MB) ולכן לא נקרא. "
            "אם זה ייצוא אמיתי, נסה לייצא אותו כ-CSV.")


# ------------- READING THE FILE:
def read_table(file_bytes, filename):
    """Turns an uploaded file into a DataFrame. Raises ValueError with a message for the user."""
    name = (filename or "").lower()

    if name.endswith((".xlsx", ".xlsm", ".xls")):
        # Before the reader, not inside its try: this refusal has its own sentence, and
        # wrapping it would replace that with "the file may be corrupt".
        _refuse_a_bomb(file_bytes)

        try:
            return pd.read_excel(io.BytesIO(file_bytes))
        except ImportError:
            # `.xls` is the old binary format and pandas needs `xlrd` for it. Said plainly
            # rather than as "the file may be corrupt", which sends somebody to re-export a
            # file that was fine.
            raise ValueError("קובץ xls ישן אינו נתמך בשרת הזה. שמור אותו כ-xlsx או כ-CSV ונסה שוב.")
        except Exception:
            raise ValueError("לא הצלחנו לקרוא את קובץ האקסל. ודא שהוא לא פגום ושהעסקאות נמצאות בגיליון הראשון.")

    if name.endswith((".html", ".htm")):
        tables = read_html_tables(file_bytes)

        if not tables:
            raise ValueError("לא מצאנו אף טבלה בקובץ ה-HTML. ודא שזה דוח עסקאות ולא עמוד שנשמר חלקית.")

        return _statement_frame(tables)

    if name.endswith((".csv", ".tsv", ".txt")):
        # Journals and brokers disagree on separator and encoding, so a few combinations
        # are tried before giving up.
        for encoding in ["utf-8-sig", "utf-8", "cp1255", "latin-1"]:
            for sep in [None, ",", ";", "\t"]:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding = encoding, sep = sep, engine = "python")
                    if df.shape[1] > 1:
                        return df
                except Exception:
                    continue
        raise ValueError("לא הצלחנו לקרוא את קובץ ה-CSV. נסה לייצא אותו מחדש כ-CSV או כאקסל.")

    raise ValueError("סוג הקובץ אינו נתמך. אפשר להעלות CSV, TSV, אקסל (xlsx/xls) או דוח HTML של MT4/MT5.")




# ------------- MAPPING THE COLUMNS:
def normalize_header(header):
    """
    Reduces a header to its comparable core.

    Exports decorate headers freely - "Net P&L (USD)", "Qty.", "Entry Price $" - and every
    one of those is the same column. Stripping the decoration is what lets one dictionary
    entry cover many vendors instead of needing a row per spelling.
    """
    text = str(header).strip().lower()

    # A trailing unit or currency note carries no meaning for identification.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)

    text = text.replace("_", " ").replace("-", " ").replace(".", " ")
    text = re.sub(r"[$€£₪#:*]", " ", text)

    # MT4 writes its stop and target columns as "S / L" and "T / P". Closing the gaps makes
    # them the same string as the synonyms already in the dictionary - and it is applied to
    # both sides, so "win / loss" and "win/loss" stay one header either way.
    text = re.sub(r"\s*/\s*", "/", text)

    return re.sub(r"\s+", " ", text).strip()


def map_columns(df, sample = None):
    """
    Maps the file's actual headers onto canonical field names.

    Two passes. The first takes exact matches, which is where a known vendor lands. The
    second offers the leftovers to a whole-word containment match, so a header nobody wrote
    down - "Total Net P&L For Trade" - still finds its field. Candidates are scored and
    assigned greedily so the tightest match wins the column rather than the first field that
    happens to be iterated.
    """
    mapping = {}
    used = set()

    headers = {}
    for column in df.columns:
        headers.setdefault(normalize_header(column), column)

    # ------------- PASS 1: exact header match.
    for field, synonyms in COLUMN_SYNONYMS.items():
        for synonym in synonyms:
            key = normalize_header(synonym)
            if key in headers and headers[key] not in used:
                mapping[field] = headers[key]
                used.add(headers[key])
                break

    # ------------- PASS 2: whole-word containment, scored.
    candidates = []
    for field, synonyms in COLUMN_SYNONYMS.items():
        if field in mapping:
            continue
        for synonym in synonyms:
            key = normalize_header(synonym)
            # Only multi-word synonyms may match as a fragment. A single word is far too
            # greedy: "type" swallows "Asset Type" and turns an instrument class into a
            # trade direction, and "net" would claim any column with the word in it.
            if len(key.split()) < 2:
                continue
            for normalized, column in headers.items():
                if column in used:
                    continue
                if _contains_words(normalized, key):
                    # Longer synonyms and tighter headers win.
                    score = len(key) / max(len(normalized), 1)
                    candidates.append((score, len(key), field, column))

    for _, _, field, column in sorted(candidates, key = lambda c: (-c[0], -c[1])):
        if field in mapping or column in used:
            continue
        mapping[field] = column
        used.add(column)

    if sample is not None:
        mapping = _settle_by_value(mapping, sample)

    return mapping


def _find_fee_columns(df, mapping):
    """Every column that reads as a cost, so a three-column fee breakdown is not lost."""
    claimed = {column for field, column in mapping.items() if field != "fees"}
    fee_names = [normalize_header(name) for name in COLUMN_SYNONYMS["fees"]]

    columns = []
    for column in df.columns:
        if column in claimed:
            continue
        normalized = normalize_header(column)
        if any(_contains_words(normalized, name) for name in fee_names if len(name) >= 3):
            columns.append(column)

    return columns


def _sum_fees(row, fee_columns):
    """Fees are stored as a positive cost regardless of the sign the export used."""
    total = None

    for column in fee_columns:
        value = parse_number(row[column]) if column in row else None
        if value is not None:
            total = (total or 0.0) + abs(value)

    return total


def _contains_words(haystack, needle):
    """True when every word of the needle appears in order, on word boundaries."""
    pattern = r"\b" + r"\s+".join(re.escape(word) for word in needle.split()) + r"\b"
    return re.search(pattern, haystack) is not None


def _settle_by_value(mapping, sample):
    """Resolves fields the headers alone cannot separate, by looking at the data."""
    return _settle_timestamps(_settle_outcome(mapping, sample), sample)


def _settle_outcome(mapping, sample):
    """
    "Result" is the live case: TradeReport uses it for the P&L, other journals use it for
    win/loss. A numeric field holding outcome words is really the status column, and taking
    the header at its word would drop every row for having no result.
    """
    pnl_column = mapping.get("pnl")

    if pnl_column is None or "status" in mapping:
        return mapping

    values = [v for v in sample.get(pnl_column, []) if v is not None][:20]
    if not values:
        return mapping

    numeric = sum(1 for v in values if parse_number(v) is not None)
    outcomes = sum(1 for v in values if parse_outcome(v) is not None)

    if outcomes > numeric:
        mapping.pop("pnl")
        mapping["status"] = pnl_column

    return mapping


# A cell that carries a date as well as a clock: "2026.08.18 11:02:41", "18/08/2026 11:02".
FULL_TIMESTAMP = re.compile(r"\d{1,4}[./-]\d{1,2}[./-]\d{1,4}")


def _settle_timestamps(mapping, sample):
    """
    A "Time" column holding a whole timestamp is the date column.

    MT4 and MT5 label the two instants of a trade "Open Time" and "Close Time" and never
    write a date anywhere else. Read as a time-of-day column, the file appears to have no
    date at all and is rejected - over a field it is in fact carrying, in that same cell.
    """
    for time_field, date_field in (("closed_time", "closed_date"), ("opened_time", "opened_date")):
        column = mapping.get(time_field)

        if column is None or date_field in mapping:
            continue

        values = [str(value) for value in sample.get(column, []) if value is not None][:20]

        if values and sum(1 for v in values if FULL_TIMESTAMP.search(v)) > len(values) / 2:
            # One column is one thing. Leaving it under both names would have the date read
            # twice out of the same cell.
            mapping[date_field] = column
            mapping.pop(time_field)

    return mapping



# ------------- STATEMENTS (MT4 / MT5):
# An HTML statement is not a spreadsheet: the trade table sits somewhere inside a page of
# account details and summaries, its header is a row like any other, and the platform ends
# the block with totals before starting the next section.
#
# So the header is *found* rather than assumed, and the block is cut where it actually ends.
# Everything after that is the ordinary engine - the column dictionary, the LLM fallback,
# the timezone handling and the dedup all apply unchanged.

# Every header the dictionary knows, as a set, so a row can be tested as a possible header
# in one pass instead of being run through the whole mapper.
HEADER_HINTS = {normalized
                for synonyms in COLUMN_SYNONYMS.values()
                for normalized in (normalize_header(s) for s in synonyms)
                if len(normalized) >= 2}

# A header row has to look like one. Three known column names is enough to tell the trade
# table apart from an account-details row, and low enough that a sparse statement still
# qualifies.
MIN_HEADER_HITS = 3


def _open_close_headers(cells):
    """
    Makes duplicate headers unique - and, where there are exactly two, meaningful.

    A statement writes the open and the close side of a trade under the same word: MT5 has
    two "Time" columns and two "Price" columns, MT4 repeats "Price". They are always laid out
    open first, close second, so naming them that way is not a guess about the platform - it
    is the layout of the table. And once they are named "Open Price" and "Close Time", the
    dictionary that reads every other export already knows what they are. That is the whole
    point: no statement-specific mapping logic exists anywhere.
    """
    # An unnamed column still has to be addressable, and two of them must not collide.
    names = [str(cell).strip() or f"column_{index + 1}" for index, cell in enumerate(cells)]

    counts = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1

    seen = {}
    resolved = []

    for name in names:
        seen[name] = seen.get(name, 0) + 1

        if counts[name] == 1:
            resolved.append(name)
        elif counts[name] == 2:
            resolved.append(("Open " if seen[name] == 1 else "Close ") + name)
        else:
            # Three or more of the same word is not an open/close pair; it just has to stop
            # colliding, the way a spreadsheet reader would already have made it.
            resolved.append(name if seen[name] == 1 else f"{name}.{seen[name] - 1}")

    return resolved


SCORE_ROWS = 10


def _block(table, header_index, width):
    """
    The rows that belong to this header, and no further.

    A statement does not end its trade table - it closes the section with a totals line and
    starts the next one under a header of its own. MT5 lists Positions, then Orders, then
    Deals, and deals are the individual fills: reading past the boundary would count every
    trade a second time.

    The boundary is a shape, not a keyword, so it holds in any language the platform is
    running in: a totals line, a blank line and a section title are all short rows.
    """
    rows = []

    for row in table[header_index + 1:]:
        cells = [str(cell).strip() for cell in row]
        filled = sum(1 for cell in cells if cell)

        if len(cells) != width or filled * 2 < width:
            break

        rows.append(cells)

    return rows


def _header_score(names, rows):
    """
    (how many fields the mapping supplies, whether the required three are all there).

    Scored with the values under the header, not the header alone - a statement's "Time"
    column only reveals itself as the date column by what is in it, and a candidate judged
    without that would be ranked on a mapping the real pass then disagrees with.
    """
    sample = {name: [row[index] for row in rows] for index, name in enumerate(names)}

    mapping = map_columns(pd.DataFrame(columns = names), sample)

    return len(mapping), not _missing_required(mapping), mapping


def _statement_frame(tables):
    """
    Picks the trade table out of a statement and returns it as a DataFrame.

    Ties are broken towards the earliest candidate, so a statement that describes the same
    trades twice is read from the first description of them.
    """
    best = None

    for table in tables:
        for index, row in enumerate(table):
            hits = sum(1 for cell in row if normalize_header(cell) in HEADER_HINTS)

            if hits < MIN_HEADER_HITS:
                continue

            names = _open_close_headers(row)
            rows = _block(table, index, len(names))

            if not rows:
                continue

            count, complete, mapping = _header_score(names, rows[:SCORE_ROWS])

            rank = (complete, count)

            if best is None or rank > best[0]:
                best = (rank, rows, names, mapping)

    if best is None:
        # No header the dictionary recognises - a statement in a language it does not cover.
        # The largest grid in the document is handed over anyway, because the LLM mapping
        # route downstream reads headers this dictionary cannot, and it needs a table to read.
        best = _widest_block(tables)

    if best is None:
        raise ValueError(
            "לא מצאנו טבלת עסקאות בקובץ ה-HTML. אם זה דוח של MT4 או MT5, שמור אותו מהפלטפורמה "
            "כ-Statement מלא (Save as Report / Detailed Report) והעלה שוב.")

    _, rows, names, mapping = best

    return pd.DataFrame(_data_rows(rows, names, mapping), columns = names)


# Below this, a run of same-width rows is a layout accident rather than a table.
MIN_FALLBACK_ROWS = 3
MIN_FALLBACK_COLUMNS = 4


def _widest_block(tables):
    """The largest rectangular run in the document, taking the row above it as the header."""
    best = None

    for table in tables:
        for index, row in enumerate(table):
            width = len(row)

            if width < MIN_FALLBACK_COLUMNS:
                continue

            rows = _block(table, index, width)

            if len(rows) < MIN_FALLBACK_ROWS:
                continue

            size = len(rows) * width

            if best is None or size > best[0][1]:
                best = ((False, size), rows, _open_close_headers(row), {})

    return best


def _data_rows(rows, names, mapping):
    """
    Drops what survived the shape test but is still not a trade.

    A statement that pads its totals line out to the full width of the table passes the
    boundary check; a totals line has no date in it, and that is what settles it.
    """
    column = mapping.get("closed_date") or mapping.get("opened_date")

    if column not in names:
        return rows

    index = names.index(column)

    kept = []

    for row in rows:
        if parse_datetime(row[index] or None) is None:
            if kept:
                break
            continue

        kept.append(row)

    return kept or rows


# ------------- VALUE PARSING:
def parse_number(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    # Handles "$1,234.50", "(85.00)" for negatives, and stray currency symbols.
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^\d.\-]", "", text.replace(",", ""))

    if text in ("", "-", "."):
        return None

    try:
        number = float(text)
    except ValueError:
        return None

    return -number if negative else number


def parse_datetime(date_value, time_value = None, source_timezone = DEFAULT_SOURCE_TIMEZONE):
    """Combines a date cell and an optional time cell into one UTC datetime."""
    if date_value is None or (isinstance(date_value, float) and pd.isna(date_value)):
        return None

    if isinstance(date_value, datetime):
        parsed = date_value
    else:
        text = str(date_value).strip()
        if not text:
            return None
        # dayfirst - the export uses 18.8.2026, and European/Israeli exports generally do.
        # A year-first stamp ("2026.08.18", what MT4 and MT5 write) is not ambiguous in the
        # first place, and asking for dayfirst on one only produces a warning.
        dayfirst = not re.match(r"\d{4}[./-]", text)
        parsed = pd.to_datetime(text, dayfirst = dayfirst, errors = "coerce")
        if parsed is pd.NaT or pd.isna(parsed):
            return None
        parsed = parsed.to_pydatetime()

    if time_value is not None and not (isinstance(time_value, float) and pd.isna(time_value)):
        time_text = str(time_value).strip()
        match = re.match(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", time_text)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            second = int(match.group(3)) if match.group(3) else 0
            parsed = parsed.replace(hour = hour, minute = minute, second = second)

    # The wall clock in the file belongs to source_timezone; it becomes a real instant here.
    try:
        local = parsed.replace(tzinfo = ZoneInfo(source_timezone))
    except Exception:
        local = parsed.replace(tzinfo = timezone.utc)

    return local.astimezone(timezone.utc)


def parse_direction(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "unknown"

    text = str(value).strip().lower()

    for word in LONG_WORDS:
        if text == word or word in text.split():
            return "long"
    for word in SHORT_WORDS:
        if text == word or word in text.split():
            return "short"

    if any(word in text for word in LONG_WORDS):
        return "long"
    if any(word in text for word in SHORT_WORDS):
        return "short"

    return "unknown"


TRUE_WORDS = ["כן", "true", "yes", "y", "1", "v", "✓", "✔", "x", "done", "בוצע"]
FALSE_WORDS = ["לא", "false", "no", "n", "0", "", "-", "pending", "ממתין"]


def parse_bool(value):
    """A yes/no cell to a real boolean, or None when the file did not say.

    Journals write this flag as כן/לא, Yes/No, true/false, a tick, or a 1/0, so all of them
    are read; anything unrecognised returns None rather than guessing a direction.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in TRUE_WORDS:
        return True
    if text in FALSE_WORDS:
        return False
    return None


def parse_outcome(value):
    """Reads an outcome cell. Returns 'win' / 'loss' / 'breakeven', or None if unreadable."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    text = normalize_header(value)
    if not text or text == "nan":
        return None

    # Exact match first. Short tokens like "be", "w" and "l" must never be matched as a
    # substring, or "below target" would read as breakeven.
    if text in BREAKEVEN_WORDS:
        return BREAKEVEN
    if text in WIN_WORDS:
        return WIN
    if text in LOSS_WORDS:
        return LOSS

    # Then whole-word matching, so "Break Even Trade" or "Win (partial)" still resolve.
    words = re.findall(r"[\w/\-]+", text)
    if any(word in BREAKEVEN_WORDS for word in words):
        return BREAKEVEN
    if any(word in WIN_WORDS for word in words):
        return WIN
    if any(word in LOSS_WORDS for word in words):
        return LOSS

    for phrase in BREAKEVEN_WORDS:
        if " " in phrase and phrase in text:
            return BREAKEVEN

    return None


def breakeven_threshold(pnls):
    """
    The size below which a result is a scratch rather than a real win or loss.

    Anchored on the median absolute P&L, which is the trader's own typical trade size, so a
    futures scalper and a swing trader each get a band that fits them. Calibrated against a
    real journal whose breakeven trades topped out at 28 while the smallest genuine loss was
    35.50 - this fraction separated all 95 trades correctly.
    """
    sizes = [abs(p) for p in pnls if p is not None]

    if not sizes:
        return 0.0

    sizes.sort()
    middle = len(sizes) // 2
    median = sizes[middle] if len(sizes) % 2 else (sizes[middle - 1] + sizes[middle]) / 2

    return median * BREAKEVEN_RISK_FRACTION


def outcome_from_pnl(pnl, threshold):
    if pnl is None:
        return None
    if abs(pnl) <= threshold:
        return BREAKEVEN
    return WIN if pnl > 0 else LOSS


def parse_duration(value):
    """Reads '14m 12s', '1h 20m', '00:14:12' into seconds."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    clock = re.match(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?$", text)
    if clock:
        hours, minutes = int(clock.group(1)), int(clock.group(2))
        seconds = int(clock.group(3)) if clock.group(3) else 0
        return hours * 3600 + minutes * 60 + seconds

    total = 0
    found = False
    for amount, unit in re.findall(r"(\d+)\s*([dhms])", text):
        found = True
        total += int(amount) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]

    return total if found else None


def clean_text(value):
    """Strips HTML so the model reads the trader's words, not markup."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""

    text = re.sub(r"<br\s*/?>", "\n", text, flags = re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags = re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))

    return re.sub(r"\n{3,}", "\n\n", text).strip()



# ------------- DEDUPLICATION:
def build_dedup_hash(trade):
    """Identity of a trade: when, what, which way, how much, at what price."""
    parts = [
        trade["executed_at"].strftime("%Y-%m-%d %H:%M:%S") if trade.get("executed_at") else "",
        str(trade.get("symbol") or "").upper(),
        str(trade.get("direction") or ""),
        f"{trade.get('quantity'):.4f}" if trade.get("quantity") is not None else "",
        f"{trade.get('entry_price'):.6f}" if trade.get("entry_price") is not None else "",
        f"{trade.get('exit_price'):.6f}" if trade.get("exit_price") is not None else "",
        f"{trade.get('pnl'):.4f}" if trade.get("pnl") is not None else "",
        str(trade.get("account_id") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()



# ------------- THE PIPELINE:
def _missing_required(mapping):
    """Which of the three blocking fields the mapping still cannot supply."""
    missing = [field for field in REQUIRED_FIELDS if field not in mapping]

    # A file without a P&L column is still usable if entry and exit prices are present.
    has_outcome = "pnl" in mapping or ("entry_price" in mapping and "exit_price" in mapping)

    if not has_outcome:
        missing.append("pnl")

    return missing


def parse_file(file_bytes, filename, source_timezone = DEFAULT_SOURCE_TIMEZONE,
               mapping = None, allow_model = False, billed_to = None):
    """
    Reads a file and returns (trades, report).

    trades - normalized dicts ready to become Trade rows.
    report - what was found, what was skipped and why, for the confirmation screen.

    `mapping` re-uses a mapping resolved earlier, which is how confirmation re-reads the
    stored original and arrives at exactly the same trades as the preview did - and how it
    does so without paying for the fallback below a second time.

    `allow_model` permits the LLM column mapping when the dictionary cannot find the required
    fields. It is off by default: the temporary documents attached in chat go through here
    too, and a comparison file is not worth a model call of its own.

    `billed_to` is who that call is charged to. It travels with `allow_model` and for the
    same reason - **this is the one model call in the product that does not go through the
    chat's gate**, so without it the upload screen is a way around the budget.
    """
    df = read_table(file_bytes, filename)
    df = df.dropna(how = "all")

    sample = {column: df[column].head(20).tolist() for column in df.columns}

    mapped_by_model = False

    if mapping:
        # Given by the caller, so neither the dictionary nor the model runs. Columns that have
        # since vanished from the file are dropped rather than trusted.
        mapping = {field: column for field, column in mapping.items() if column in df.columns}
    else:
        mapping = map_columns(df, sample)

        # The dictionary goes first, always, and the model only sees files it could not read.
        if allow_model and _missing_required(mapping):
            found = map_with_model(list(df.columns), sample, mapping, billed_to = billed_to)

            if found:
                mapping = {**mapping, **found}
                mapped_by_model = True

    # Brokers split the cost across Commission / TransFee / ECNFee and friends. Every fee-ish
    # column that is not already claimed by another field gets summed into one number.
    fee_columns = _find_fee_columns(df, mapping)

    missing_required = _missing_required(mapping)

    if missing_required:
        # An execution log looks superficially similar - it has a symbol, a side, a quantity
        # and a single price - but it holds one row per fill, not one row per closed trade.
        # Saying "no result column" would send the user hunting for a column that cannot
        # exist in that kind of file.
        if _looks_like_execution_log(df, mapping):
            raise ValueError(
                "הקובץ הזה נראה כמו יומן ביצועים (שורה לכל פקודה) ולא כמו רשימת עסקאות סגורות. "
                "יש בו מחיר יחיד לכל שורה, בלי מחיר כניסה ויציאה ובלי רווח/הפסד. "
                "ייצא מהפלטפורמה את דוח העסקאות הסגורות (Trades / Closed Positions) והעלה אותו.")

        raise ValueError(describe_missing(missing_required))

    trades = []
    skipped_rows = []

    for index, row in df.iterrows():
        def cell(field):
            column = mapping.get(field)
            return row[column] if column is not None and column in row else None

        executed_at = parse_datetime(cell("closed_date"), cell("closed_time"), source_timezone)
        symbol = clean_text(cell("symbol"))

        if executed_at is None:
            skipped_rows.append({"row": int(index) + 2, "reason": "תאריך לא תקין"})
            continue
        if not symbol:
            skipped_rows.append({"row": int(index) + 2, "reason": "חסר סימבול"})
            continue

        entry_price = parse_number(cell("entry_price"))
        exit_price = parse_number(cell("exit_price"))
        pnl = parse_number(cell("pnl"))
        direction = parse_direction(cell("direction"))
        quantity = parse_number(cell("quantity"))

        # With prices but no P&L column, the result is derived - this is what keeps files
        # that only carry an execution log usable.
        if pnl is None and entry_price is not None and exit_price is not None and direction != "unknown":
            move = exit_price - entry_price if direction == "long" else entry_price - exit_price
            pnl = move * (quantity if quantity else 1)

        if pnl is None and (entry_price is None or exit_price is None):
            skipped_rows.append({"row": int(index) + 2, "reason": "אין תוצאה ואין מחירי כניסה ויציאה"})
            continue

        opened_at = parse_datetime(cell("opened_date") or cell("closed_date"), cell("opened_time"), source_timezone)

        duration_seconds = parse_duration(cell("duration"))
        if duration_seconds is None and opened_at and executed_at and executed_at >= opened_at:
            duration_seconds = int((executed_at - opened_at).total_seconds())

        orders_count = parse_number(cell("orders_count"))
        rating = parse_number(cell("rating"))

        stop_loss = parse_number(cell("stop_loss"))
        take_profit = parse_number(cell("take_profit"))

        # Journals that expose the field but leave it unfilled export a literal 0. Treating
        # that as a real stop would produce nonsense R values.
        stop_loss = stop_loss if stop_loss else None
        take_profit = take_profit if take_profit else None

        r_multiple = parse_number(cell("r_multiple"))
        if r_multiple is None and stop_loss is not None and entry_price is not None and pnl is not None:
            risk_per_unit = abs(entry_price - stop_loss)
            if risk_per_unit > 0:
                risk = risk_per_unit * (quantity if quantity else 1)
                r_multiple = pnl / risk if risk else None

        # Excursion, folded to a fixed sign so the meaning does not depend on the journal.
        # MFE is favourable (non-negative), MAE is adverse (non-positive); a file that wrote
        # MAE as a positive magnitude and one that wrote it negative now store the same thing.
        mfe = parse_number(cell("mfe"))
        mae = parse_number(cell("mae"))
        mfe = abs(mfe) if mfe is not None else None
        mae = -abs(mae) if mae is not None else None

        trade = {
            "executed_at": executed_at,
            "opened_at": opened_at,
            "symbol": symbol.upper(),
            "instrument": normalize_symbol(symbol),
            "account_id": clean_text(cell("account_id")),
            "direction": direction,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "mfe": mfe,
            "mae": mae,
            "highest_price": parse_number(cell("highest_price")),
            "lowest_price": parse_number(cell("lowest_price")),
            "was_documented": parse_bool(cell("was_documented")),
            "points": parse_number(cell("points")),
            "fees": _sum_fees(row, fee_columns),
            "r_multiple": r_multiple,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "duration_seconds": duration_seconds,
            "orders_count": int(orders_count) if orders_count is not None else None,
            "setups": clean_text(cell("setups")),
            "tags": clean_text(cell("tags")),
            "mistakes": clean_text(cell("mistakes")),
            "notes": clean_text(cell("notes")),
            "rating": rating,
            "screenshot_url": clean_text(cell("screenshot_url")),
            "source_timezone": source_timezone,
            "currency": (clean_text(cell("currency")) or DEFAULT_CURRENCY).upper()[:8],
            # None here means the file did not say; it is filled in below from the P&L.
            "outcome": parse_outcome(cell("status")),
        }
        trade["dedup_hash"] = build_dedup_hash(trade)

        trades.append(trade)

    # Second pass: any trade the file did not label is classified against a breakeven band
    # derived from this trader's own typical trade size.
    threshold = breakeven_threshold([t["pnl"] for t in trades])
    derived_outcomes = 0

    for trade in trades:
        if trade["outcome"] is None:
            trade["outcome"] = outcome_from_pnl(trade["pnl"], threshold)
            derived_outcomes += 1

    enrichment_found, enrichment_empty, enrichment_missing = assess_enrichment(trades, mapping)

    report = {
        "total_rows": int(len(df)),
        "parsed": len(trades),
        "skipped_rows": skipped_rows[:20],
        "skipped_count": len(skipped_rows),
        "mapped_fields": sorted(mapping.keys()),
        # Kept so confirmation can re-read the stored file the same way, and so the
        # screen can say when the columns were identified by the model.
        "mapping": {field: str(column) for field, column in mapping.items()},
        "mapped_by_model": mapped_by_model,
        "unmapped_columns": [str(c) for c in df.columns if c not in mapping.values()],
        "enrichment_found": enrichment_found,
        "enrichment_empty": enrichment_empty,
        "enrichment_missing": enrichment_missing,
        "source_timezone": source_timezone,
        # Tells the confirmation screen whether outcomes were read or inferred.
        "outcome_from_file": len(trades) - derived_outcomes,
        "outcome_derived": derived_outcomes,
        "breakeven_threshold": round(threshold, 2),
        "accounts": sorted({t["account_id"] for t in trades if t["account_id"]}),
        "symbols": sorted({t["symbol"] for t in trades}),
        "date_from": min((t["executed_at"] for t in trades), default = None),
        "date_to": max((t["executed_at"] for t in trades), default = None),
    }

    return trades, report


def _looks_like_execution_log(df, mapping):
    """One row per fill: a symbol, a quantity and a single unqualified price column."""
    if "pnl" in mapping or "entry_price" in mapping or "exit_price" in mapping:
        return False

    if "symbol" not in mapping or "quantity" not in mapping:
        return False

    return any(normalize_header(column) == "price" for column in df.columns)


def describe_missing(missing):
    """A rejection has to teach the user how to export correctly, not just say no."""
    labels = {
        "closed_date": "תאריך העסקה",
        "symbol": "הסימבול (שם הנכס)",
        "pnl": "התוצאה — עמודת רווח/הפסד, או מחיר כניסה ומחיר יציאה יחד",
    }
    names = [labels.get(field, field) for field in missing]
    return (
        "לא מצאנו בקובץ את " + ", ".join(names) + ". "
        "כדי שנוכל לקלוט אותו, הייצוא צריך לכלול לפחות תאריך, סימבול ותוצאה. "
        "אפשר לייצא מחדש מהיומן או מהברוקר עם העמודות האלה, ולהעלות שוב."
    )

# ------------------------- INGESTION ENGINE END ------------------------- #
