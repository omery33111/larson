import logging
import json
import os

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from mentor.rules import refresh as refresh_rules

from django.core.exceptions import SuspiciousFileOperation
from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from analytics.models import TraderProfile

from project.throttling import AIBurstThrottle, AIDailyThrottle

from .models import Trade, TradeFile
from .parsers import SUPPORTED_EXTENSIONS, parse_file
from .serializers import TradeFileSerializer, TradeSerializer


log = logging.getLogger(__name__)



MAX_FILE_MB = 20



# ------------------------- INGESTION START ------------------------- #

# ------------- UPLOAD (parse and preview, nothing is saved to the resume yet):
# **On the AI meter, because it can reach the model.** A file the column dictionary cannot
# read falls back to the LLM mapping, so this endpoint is a way to spend money - and until it
# was listed here it was the one route to the model with no cap on it at all. A file it CAN
# read costs nothing and the throttle is never the binding constraint on those.
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIBurstThrottle, AIDailyThrottle])
def upload(request):
    uploaded = request.FILES.get("file")

    if not uploaded:
        return Response({"error": "לא נבחר קובץ."}, status = status.HTTP_400_BAD_REQUEST)

    if not any(uploaded.name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        return Response(
            {"error": "סוג הקובץ אינו נתמך. אפשר להעלות CSV, TSV או אקסל (xlsx/xls)."},
            status = status.HTTP_400_BAD_REQUEST)

    if uploaded.size > MAX_FILE_MB * 1024 * 1024:
        return Response({"error": f"הקובץ גדול מ-{MAX_FILE_MB}MB."}, status = status.HTTP_400_BAD_REQUEST)

    file_bytes = uploaded.read()

    # Parsed before anything is stored, so a file we cannot read never leaves a record behind.
    # This is the one path allowed to fall back to the model for its column mapping: it is a
    # file the trader is deliberately adding to his record.
    try:
        trades, report = parse_file(file_bytes, uploaded.name, allow_model = True,
                                    billed_to = request.user)
    except ValueError as e:
        return Response({"error": str(e)}, status = status.HTTP_400_BAD_REQUEST)

    if not trades:
        return Response({"error": "לא נמצאו עסקאות תקינות בקובץ."}, status = status.HTTP_400_BAD_REQUEST)

    uploaded.seek(0)

    # **The name is stripped to its last component before it is stored.** Django refuses a
    # path that tries to climb out of the media folder - it raises `SuspiciousFileOperation`
    # and the traversal never happens - but that refusal is an exception, and an exception
    # here is a 500 rather than a sentence. Browsers send a bare filename; a crafted client
    # does not have to. The name the trader sees is kept as it arrived, because it is only
    # ever displayed.
    uploaded.name = os.path.basename(str(uploaded.name).replace("\\", "/"))

    # **The basename strip closes traversal, but the storage layer can still refuse a name
    # for its own reasons** - a Windows reserved device name (`con`, `nul`, `aux`, `lpt1`)
    # raises `SuspiciousFileOperation` at save time, and an uncaught one here is a 500 with a
    # traceback rather than a sentence. Production is Linux, where those names save fine, so
    # this only bites a crafted client on a Windows host; it is caught anyway so the refusal
    # reads like every other rejected file, not like the server fell over.
    try:
        trade_file = TradeFile.objects.create(
            user = request.user,
            file = uploaded,
            original_name = uploaded.name,
            row_count = report["total_rows"],
            column_mapping = json.dumps(report["mapping"], ensure_ascii = False),
            mapped_by_model = report["mapped_by_model"],
        )
    except SuspiciousFileOperation:
        return Response({"error": "שם הקובץ אינו תקין. נסה לשנות את שם הקובץ ולהעלות שוב."},
                        status = status.HTTP_400_BAD_REQUEST)

    # How many of these are actually new tells the user what the merge will do before it happens.
    hashes = [t["dedup_hash"] for t in trades]
    existing = set(Trade.objects.filter(user = request.user, dedup_hash__in = hashes)
                                .values_list("dedup_hash", flat = True))
    new_count = sum(1 for h in hashes if h not in existing)

    return Response({
        "trade_file": TradeFileSerializer(trade_file).data,
        "report": {
            "total_rows": report["total_rows"],
            "parsed": report["parsed"],
            "skipped_count": report["skipped_count"],
            "skipped_rows": report["skipped_rows"],
            "new_count": new_count,
            "duplicate_count": report["parsed"] - new_count,
            "accounts": report["accounts"],
            "symbols": report["symbols"],
            "date_from": report["date_from"],
            "date_to": report["date_to"],
            "source_timezone": report["source_timezone"],
            "outcome_from_file": report["outcome_from_file"],
            "outcome_derived": report["outcome_derived"],
            "breakeven_threshold": report["breakeven_threshold"],
            "enrichment_found": report["enrichment_found"],
            "enrichment_empty": report["enrichment_empty"],
            "enrichment_missing": report["enrichment_missing"],
            "unmapped_columns": report["unmapped_columns"],
            "mapped_by_model": report["mapped_by_model"],
        },
        "sample": trades_to_sample(trades),
    }, status = status.HTTP_200_OK)


def trades_to_sample(trades):
    """First, middle and last trade - enough for the user to confirm the parse looks right."""
    if len(trades) <= 3:
        picks = trades
    else:
        picks = [trades[0], trades[len(trades) // 2], trades[-1]]

    return [{
        "executed_at": t["executed_at"],
        "symbol": t["symbol"],
        "direction": t["direction"],
        "quantity": t["quantity"],
        "entry_price": t["entry_price"],
        "exit_price": t["exit_price"],
        "pnl": t["pnl"],
        "outcome": t["outcome"],
        "setups": t["setups"],
        "mistakes": t["mistakes"],
    } for t in picks]



# ------------- CONFIRM (this is the only place trades enter the resume):
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm(request):
    trade_file_id = request.data.get("trade_file_id")

    if not trade_file_id:
        return Response({"error": "חסר מזהה קובץ."}, status = status.HTTP_400_BAD_REQUEST)

    trade_file = get_object_or_404(TradeFile, id = trade_file_id, user = request.user)

    if trade_file.confirmed:
        return Response({"error": "הקובץ הזה כבר נקלט לרזומה."}, status = status.HTTP_400_BAD_REQUEST)

    # Re-parsed from the stored original rather than held in memory between the two requests.
    # The file is the source of truth, so there is no temporary state to keep in sync.
    # Re-read with the mapping the preview resolved, so what is saved is exactly what the
    # trader was shown - and so a mapping the model produced is not bought twice.
    try:
        stored = json.loads(trade_file.column_mapping) if trade_file.column_mapping else None
    except json.JSONDecodeError:
        stored = None

    try:
        with trade_file.file.open("rb") as f:
            trades, report = parse_file(f.read(), trade_file.original_name, mapping = stored)
    except ValueError as e:
        return Response({"error": str(e)}, status = status.HTTP_400_BAD_REQUEST)

    existing = set(Trade.objects.filter(user = request.user).values_list("dedup_hash", flat = True))

    # Whether he had a resume at all before this file. Read here, before the rows are written,
    # because it decides what the mentor does with the file afterwards.
    had_trades = bool(existing)

    to_create = []
    seen = set()
    duplicates = 0

    for t in trades:
        # Skips both trades already in the resume and repeats inside this same file.
        if t["dedup_hash"] in existing or t["dedup_hash"] in seen:
            duplicates += 1
            continue
        seen.add(t["dedup_hash"])
        to_create.append(Trade(user = request.user, trade_file = trade_file, **t))

    try:
        Trade.objects.bulk_create(to_create)
    except IntegrityError:
        return Response({"error": "שגיאה בשמירת העסקאות. נסה שוב."},
                        status = status.HTTP_500_INTERNAL_SERVER_ERROR)

    trade_file.imported_count = len(to_create)
    trade_file.duplicate_count = duplicates
    trade_file.skipped_count = duplicates + report["skipped_count"]
    trade_file.confirmed = True

    # Only a file the mentor screen asked for waits there. A file added through "my resume"
    # was an act of filing, not of starting a conversation, and it would be a surprise to
    # find it attached to a screen the trader was not on.
    #
    # And only a file that has something to be compared against. The one that founds the
    # resume is the baseline itself, not a session to be debriefed - there is exactly one
    # slot, so leaving it sitting there would take the place of the recent trades the mentor
    # is asking for next, which is the opposite of what the screen means. The mentor says so
    # himself in the thread instead.
    if request.data.get("for_mentor") and had_trades:
        # One slot, so attaching another file replaces the one waiting rather than queueing
        # behind it. The replaced file's trades are already in the resume either way; what it
        # loses is only its own debrief, and it becomes part of the baseline for the next one.
        TradeFile.objects.filter(user = request.user, awaiting_debrief = True).update(
            awaiting_debrief = False)

        trade_file.awaiting_debrief = True

    trade_file.save()

    # ------------- AND HIS OWN RULES READ THEMSELVES AGAIN:
    #
    # **New labels only ever arrive with new trades, so this is the moment they appear.**
    # A free-text rule interpreted against the words he used in June knows nothing about the
    # word he starts tagging with in August - it keeps reporting, keeps sounding certain, and
    # quietly stops seeing the thing it was written about. Nothing on any screen would say so.
    #
    # Here and not inside the debrief: the debrief is a streaming response he is watching,
    # and a model call that is not about his question does not belong in front of it. It
    # fires only when there are labels no rule has seen, so stable tagging costs nothing.
    try:
        refresh_rules(request.user)
    except Exception:
        # **Never fail the import over this.** The trades are saved and that is the thing he
        # asked for; a rule reading itself a week late is a smaller cost by far.
        log.exception("Could not re-read the trader's own rules after an import")

    return Response({
        "success": True,
        "imported": len(to_create),
        "duplicates": duplicates,
        "invalid_rows": report["skipped_count"],
        "total_trades": Trade.objects.filter(user = request.user).count(),
    }, status = status.HTTP_201_CREATED)

# ------------------------- INGESTION END ------------------------- #



# ------------------------- RESUME READ START ------------------------- #

# ------------- LIST:
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trade_list(request):
    trades = Trade.objects.filter(user = request.user)

    limit = int(request.GET.get("limit", 50))
    offset = int(request.GET.get("offset", 0))

    return Response({
        "count": trades.count(),
        "results": TradeSerializer(trades[offset:offset + limit], many = True).data,
    })


# ------------- SUMMARY (metadata only - the real statistics engine is milestone 3):
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary(request):
    trades = Trade.objects.filter(user = request.user)
    total = trades.count()

    if total == 0:
        return Response({"total_trades": 0})

    ordered = trades.order_by("executed_at")
    files = TradeFile.objects.filter(user = request.user, confirmed = True)
    newest = files.order_by("-uploaded_at").first()

    return Response({
        "total_trades": total,
        "date_from": ordered.first().executed_at,
        "date_to": ordered.last().executed_at,
        "symbols": sorted(set(trades.values_list("symbol", flat = True))),
        "accounts": sorted({a for a in trades.values_list("account_id", flat = True) if a}),
        # When the resume last grew, as opposed to when he last traded. The mentor's nudge
        # counts the second; this dialog is about the record itself.
        "last_updated": newest.uploaded_at if newest else None,
        "files": TradeFileSerializer(files, many = True).data,
    })

# ------------------------- RESUME READ END ------------------------- #



# ------------------------- DELETING THE RESUME START ------------------------- #
#
# Every component, or none. The resume is four things - the source files on disk, the trades
# table, the aggregates and the written profile - and leaving any one of them behind produces
# a state nothing in the product knows how to describe: a profile about trades that no longer
# exist, or a file that silently re-imports itself as a duplicate.
#
# The aggregates need no line of their own: they are computed at request time and never
# stored, so they are gone the moment the trades are.

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def resume(request):
    files = TradeFile.objects.filter(user = request.user)

    deleted = {
        "trades": Trade.objects.filter(user = request.user).count(),
        "files": files.count(),
    }

    # Django stopped deleting the file behind a FileField when the row goes, so the bytes on
    # disk have to be removed by hand - otherwise "delete everything" leaves the originals.
    for trade_file in files:
        if trade_file.file:
            trade_file.file.delete(save = False)

    files.delete()
    Trade.objects.filter(user = request.user).delete()

    # The written profile describes trades that no longer exist.
    TraderProfile.objects.filter(user = request.user).delete()

    # Conversations are deliberately left alone. They are his words as much as Larson's, and
    # the spec lists four components - this is not one of them. The dialog says so out loud.
    return Response({"deleted": deleted}, status = status.HTTP_200_OK)

# ------------------------- DELETING THE RESUME END ------------------------- #
