from django.db import models
from django.contrib.auth.models import User



# ------------------------- TRADE FILE START ------------------------- #

# Every uploaded file is kept exactly as it arrived. This is the insurance policy of the
# resume: if a parsing bug is found, the parser is fixed and ingestion is re-run from here.
class TradeFile(models.Model):
    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = "trade_files")

    file = models.FileField(upload_to = "trade_files/")
    original_name = models.CharField(max_length = 255)
    source_platform = models.CharField(max_length = 100, blank = True)

    uploaded_at = models.DateTimeField(auto_now_add = True)

    row_count = models.IntegerField(default = 0)
    imported_count = models.IntegerField(default = 0)
    skipped_count = models.IntegerField(default = 0)

    # Kept apart from skipped_count, which lumps duplicates together with rows the parser
    # could not read. The mentor's receipt states this number out loud, so it has to mean
    # exactly one thing.
    duplicate_count = models.IntegerField(default = 0)

    # How this file's columns were resolved. Stored so confirmation re-reads the original the
    # same way the preview did - and so a mapping that cost a model call is paid for once.
    column_mapping = models.TextField(blank = True)
    mapped_by_model = models.BooleanField(default = False)

    confirmed = models.BooleanField(default = False)

    # Confirmed into the resume, and still waiting for the trader to press send on the mentor
    # screen. It lives here rather than in the browser because the file has to still be there
    # after he walks away, changes page, or logs out and comes back on another machine - the
    # trades are already saved, and the thing left undone is the conversation about them.
    awaiting_debrief = models.BooleanField(default = False)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.user.username} - {self.original_name}"

# ------------------------- TRADE FILE END ------------------------- #



# ------------------------- TRADE START ------------------------- #

LONG = "long"
SHORT = "short"
UNKNOWN = "unknown"

DIRECTION_CHOICES = [
    (LONG, "Long"),
    (SHORT, "Short"),
    (UNKNOWN, "Unknown"),
]

WIN = "win"
LOSS = "loss"
BREAKEVEN = "breakeven"

OUTCOME_CHOICES = [
    (WIN, "Win"),
    (LOSS, "Loss"),
    (BREAKEVEN, "Breakeven"),
    (UNKNOWN, "Unknown"),
]


class Trade(models.Model):
    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = "trades")
    trade_file = models.ForeignKey(TradeFile, on_delete = models.SET_NULL, null = True, related_name = "trades")

    # ------------- REQUIRED CORE:
    executed_at = models.DateTimeField()

    # The ticker exactly as the file wrote it - MNQU6, MNQM6, /ESH25.
    symbol = models.CharField(max_length = 50)

    # The chart behind that ticker. MNQU6 and MNQM6 are the same instrument, and so are
    # NQ, MNQ and the nano contract; the analysis groups by this so a trader's history is
    # not scattered across buckets too small to mean anything.
    instrument = models.CharField(max_length = 50, blank = True, db_index = True)

    # ------------- IDENTITY:
    # Kept from the file so a funded account and a personal account never pollute each
    # other's baseline. Deliberately has no UI - the pipeline just preserves the field.
    account_id = models.CharField(max_length = 100, blank = True)
    source_platform = models.CharField(max_length = 100, blank = True)

    # executed_at and opened_at are true UTC. This records which wall clock they came from,
    # so the UI can render the hour the trader actually traded at.
    source_timezone = models.CharField(max_length = 64, blank = True)

    # ------------- OUTCOME:
    # Read from the journal's own status column when it has one. That column reflects the
    # breakeven range the trader configured in their tool, so it beats any arithmetic we
    # could do - a trade they scratched is a scratch, not a small loss.
    outcome = models.CharField(max_length = 12, choices = OUTCOME_CHOICES, default = UNKNOWN)

    direction = models.CharField(max_length = 10, choices = DIRECTION_CHOICES, default = UNKNOWN)
    quantity = models.FloatField(null = True, blank = True)
    entry_price = models.FloatField(null = True, blank = True)
    exit_price = models.FloatField(null = True, blank = True)
    pnl = models.FloatField(null = True, blank = True)
    # Read from the file when it says so, otherwise USD. Every amount shown to the user is
    # rendered with this, so a number never appears without knowing what it is.
    currency = models.CharField(max_length = 8, default = "USD")
    points = models.FloatField(null = True, blank = True)
    fees = models.FloatField(null = True, blank = True)
    r_multiple = models.FloatField(null = True, blank = True)

    # ------------- RISK:
    stop_loss = models.FloatField(null = True, blank = True)
    take_profit = models.FloatField(null = True, blank = True)

    # ------------- EXCURSION (how far the trade ran each way before it closed):
    # MFE and MAE are the headline here - the best unrealised profit and the worst unrealised
    # loss reached while the trade was open, in money. They answer a question the realised
    # P&L cannot: not "did it win" but "how much was on the table, and how much heat did it
    # take to get there". A trader who reaches +$300 on every trade but keeps a tenth of it
    # is told something no win-rate can say.
    #
    # **Normalised by sign at parse time, not stored as the journal happened to write it.**
    # MFE is favourable by definition, so it is stored non-negative; MAE is adverse, so it is
    # stored non-positive. Journals disagree on whether MAE is "-40.5" or "40.5"; folding the
    # sign here means every downstream number means the same thing regardless of the source.
    mfe = models.FloatField(null = True, blank = True)
    mae = models.FloatField(null = True, blank = True)

    # The raw price path - the highest and lowest the instrument traded while the position
    # was open. The price-terms counterpart to MFE/MAE; kept as the file wrote them.
    highest_price = models.FloatField(null = True, blank = True)
    lowest_price = models.FloatField(null = True, blank = True)

    # **True when MFE/MAE were not in the file and were derived from the high/low prices.**
    # The dollars-per-point is backed out of this same trade's realised P&L and price move -
    # never a hardcoded table - so MNQ recovers ~$2 and NQ ~$20 on their own. The one
    # inaccuracy is fees, which the realised P&L already carries, so a derived figure is an
    # estimate and is marked as one everywhere it is shown. A measured value is never
    # overwritten by a derived one.
    excursion_estimated = models.BooleanField(default = False)

    # Whether the trader journaled this trade (TradeReport's "documented" flag). None when the
    # file did not say. Kept because it was asked for; it drives no scoring - journaling
    # coverage is already visible from the qualitative fields.
    was_documented = models.BooleanField(null = True, blank = True)

    # ------------- EXECUTION DETAIL:
    opened_at = models.DateTimeField(null = True, blank = True)
    duration_seconds = models.IntegerField(null = True, blank = True)
    orders_count = models.IntegerField(null = True, blank = True)

    # ------------- THE QUALITATIVE LAYER (this is what makes the mentor a mentor):
    setups = models.TextField(blank = True)
    tags = models.TextField(blank = True)
    mistakes = models.TextField(blank = True)
    notes = models.TextField(blank = True)
    rating = models.FloatField(null = True, blank = True)
    screenshot_url = models.TextField(blank = True)

    # ------------- DEDUPLICATION:
    dedup_hash = models.CharField(max_length = 64, db_index = True)

    created_at = models.DateTimeField(auto_now_add = True)

    class Meta:
        ordering = ["-executed_at"]
        # The same trade may legitimately appear in two files the user uploads. It is
        # stored once per user, and re-uploading an overlapping export is a no-op.
        constraints = [
            models.UniqueConstraint(fields = ["user", "dedup_hash"], name = "unique_trade_per_user")
        ]

    def __str__(self):
        return f"{self.symbol} {self.direction} @ {self.executed_at}"

# ------------------------- TRADE END ------------------------- #
