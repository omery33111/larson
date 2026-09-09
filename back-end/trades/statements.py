import re
from html.parser import HTMLParser



# ------------------------- STATEMENT EXTRACTION START ------------------------- #
#
# MT4 and MT5 hand the trader an HTML statement. It is the default export of the platform
# and it is a genuine trade record - the file most retail forex and CFD traders actually
# have - so it belongs in the engine.
#
# This module does one job: HTML in, tables of text out. It knows nothing about what a
# column means. That is deliberate and it is the whole reason milestone 7 splits in two:
# a statement is an **extraction** problem, and the mapping problem after it is already
# solved by the dictionary that reads every other export. Keeping the seam here means the
# column dictionary, the LLM fallback, the dedup and the timezone handling all apply to a
# statement without a single line written twice.
#
# Written on `html.parser` from the standard library rather than on lxml or BeautifulSoup.
# The reason is not only the dependency: a statement is routinely malformed - `<td>` left
# unclosed, `<tr>` never terminated - and reading it off **start** tags alone, as this does,
# survives that better than a parser that tries to build a correct tree from it.


# A statement is small; anything past this is not one, and is not worth the memory.
MAX_TABLES = 200
MAX_ROWS = 20000


class _Tables(HTMLParser):
    """Every <table> in the document, as a grid of stripped cell text."""

    def __init__(self):
        super().__init__(convert_charrefs = True)
        self.tables = []
        self._open = []       # tables currently open, innermost last
        self._row = None
        self._cell = None

    # ------------- ROWS AND CELLS:
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            # A row left open by the wrapper table is abandoned here on purpose: a cell that
            # contains a table holds layout, never a trade.
            self._row = None
            self._open.append([])

        elif tag == "tr":
            self._finish_row()
            self._row = []

        elif tag in ("td", "th"):
            self._finish_cell()
            self._cell = []

        elif tag == "br":
            if self._cell is not None:
                self._cell.append(" ")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._finish_cell()

        elif tag == "tr":
            self._finish_row()

        elif tag == "table":
            self._finish_row()
            if self._open:
                rows = self._open.pop()
                if rows and len(self.tables) < MAX_TABLES:
                    self.tables.append(rows)

    # ------------- CLOSING:
    def _finish_cell(self):
        if self._cell is None:
            return

        text = re.sub(r"\s+", " ", "".join(self._cell)).strip()

        if self._row is None:
            self._row = []

        self._row.append(text)
        self._cell = None

    def _finish_row(self):
        self._finish_cell()

        if self._row is None:
            return

        if self._open and any(self._row) and len(self._open[-1]) < MAX_ROWS:
            self._open[-1].append(self._row)

        self._row = None

    def close(self):
        # A document that never closes its last <table> still gives up its rows.
        super().close()
        self._finish_row()
        while self._open:
            rows = self._open.pop()
            if rows and len(self.tables) < MAX_TABLES:
                self.tables.append(rows)


# ------------- ENCODING:
# Statements come out of the platform in whatever codepage the terminal was running in, and
# the declared charset is the only reliable clue. Everything after it is a fallback ladder.
FALLBACK_ENCODINGS = ["utf-8-sig", "utf-8", "cp1255", "cp1252", "utf-16", "latin-1"]


def decode(file_bytes):
    declared = re.search(rb"charset\s*=\s*[\"']?\s*([\w\-]+)", file_bytes[:4096], re.IGNORECASE)

    encodings = list(FALLBACK_ENCODINGS)

    if declared:
        encodings.insert(0, declared.group(1).decode("ascii", "ignore"))

    for encoding in encodings:
        try:
            return file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    # latin-1 above cannot fail, so this is only reachable for an empty ladder.
    return file_bytes.decode("utf-8", "replace")


def read_html_tables(file_bytes):
    """Returns [[[cell, ...], ...], ...] - one grid per <table>, in document order."""
    parser = _Tables()

    try:
        parser.feed(decode(file_bytes))
        parser.close()
    except Exception:
        # A statement mangled past parsing is a rejection with a sentence, not a traceback.
        return parser.tables

    return parser.tables

# ------------------------- STATEMENT EXTRACTION END ------------------------- #
