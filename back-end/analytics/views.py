from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from project.throttling import AIBurstThrottle, AIDailyThrottle

from trades.models import Trade

from .insights import build_insights
from .periods import build_periods
from .models import TraderProfile
from .profile import generate_profile
from .statistics import compute_statistics



# ------------------------- ACCOUNT SELECTION START ------------------------- #
#
# A trader with a funded account and a personal one is really two traders, and averaging
# them produces a profile that describes neither. The whole page is therefore computed over
# whichever accounts are ticked.
#
# This costs nothing extra: the statistics are already recomputed from the trades table on
# every request, so a filter is a narrower list in, the same arithmetic out. No model call
# is involved - only the written profile calls Claude, and only when its button is pressed.

UNASSIGNED = "__none__"


def _requested_accounts(request):
    """`?accounts=A,B`. Absent or empty means every account."""
    raw = request.GET.get("accounts", "").strip()

    if not raw:
        return None

    return [part.strip() for part in raw.split(",") if part.strip()]


def _filter_by_accounts(trades, accounts):
    if accounts is None:
        return trades

    wanted = set(accounts)

    # Trades whose file carried no account id are reachable under an explicit bucket, so
    # they are never silently unreachable.
    return [t for t in trades
            if (t.account_id or UNASSIGNED) in wanted]


def _account_directory(trades):
    """
    Every account the user has, with enough detail to choose between them.

    Deliberately built from the unfiltered list, so narrowing the selection never empties
    the menu you narrowed it with.
    """
    accounts = {}

    for trade in trades:
        key = trade.account_id or UNASSIGNED
        entry = accounts.setdefault(key, {
            "account_id": key,
            "label": trade.account_id or "ללא מספר חשבון",
            "trades": 0,
            "net_pnl": 0.0,
            "last_traded": None,
        })

        entry["trades"] += 1
        entry["net_pnl"] += trade.pnl or 0.0
        if entry["last_traded"] is None or trade.executed_at > entry["last_traded"]:
            entry["last_traded"] = trade.executed_at

    for entry in accounts.values():
        entry["net_pnl"] = round(entry["net_pnl"], 2)

    # Most recently traded first - that is the one the user is thinking about.
    return sorted(accounts.values(), key = lambda a: a["last_traded"], reverse = True)

# ------------------------- ACCOUNT SELECTION END ------------------------- #



# ------------------------- OVERVIEW START ------------------------- #

# ------------- EVERYTHING THE PROFILE PAGE NEEDS, IN ONE REQUEST:
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def overview(request):
    all_trades = list(Trade.objects.filter(user = request.user))

    if not all_trades:
        return Response({"total_trades": 0, "has_enough_data": False, "available_accounts": []})

    directory = _account_directory(all_trades)
    requested = _requested_accounts(request)
    trades = _filter_by_accounts(all_trades, requested)

    selected = requested if requested is not None else [a["account_id"] for a in directory]

    # Recomputed on every request, so the numbers can never be stale.
    statistics = compute_statistics(trades)

    if not statistics.get("total_trades"):
        return Response({
            "total_trades": 0,
            "has_enough_data": False,
            "available_accounts": directory,
            "selected_accounts": selected,
            "profile": _profile_payload(request.user),
        })

    strengths, leaks = build_insights(statistics, trades)

    return Response({
        **statistics,
        "strengths": strengths,
        "leaks": leaks,
        # **The axis the page never had.** Everything above is computed over the whole record
        # at once, so the question a mentor exists for - am I getting better - had no answer
        # anywhere on this screen. It costs nothing extra: the statistics were already being
        # recomputed per request, and this is the same rows cut into windows.
        "periods": build_periods(trades, statistics.get("currency", "USD"),
                                 statistics.get("timezone", "Asia/Jerusalem")),
        "available_accounts": directory,
        "selected_accounts": selected,
        "profile": _profile_payload(request.user),
    })


def _profile_payload(user):
    written = TraderProfile.objects.filter(user = user).first()

    if not written:
        return None

    return {
        "text": written.profile_text,
        "generated_at": written.generated_at,
        "trades_at_generation": written.trades_at_generation,
        "score_at_generation": written.score_at_generation,
        # Which accounts this text is actually about, so a stale profile can be spotted.
        "accounts": [a for a in written.accounts.split(",") if a],
    }

# ------------------------- OVERVIEW END ------------------------- #



# ------------------------- WRITTEN PROFILE START ------------------------- #

# ------------- READ:
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile(request):
    payload = _profile_payload(request.user)

    if not payload:
        return Response({"error": "עדיין לא נוצר פרופיל."}, status = status.HTTP_404_NOT_FOUND)

    return Response(payload)


# ------------- GENERATE:
# Two windows on the meter, because this is the endpoint that spends money: one
# answer is allowed up to 64k output tokens. See project/throttling.py.
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIBurstThrottle, AIDailyThrottle])
def generate(request):
    all_trades = list(Trade.objects.filter(user = request.user))

    # The written profile describes exactly the accounts that were ticked when the button was
    # pressed, which is what makes "what does the mentor make of these two together?" a real
    # question the user can ask.
    raw = str(request.data.get("accounts", "")).strip()
    requested = [part.strip() for part in raw.split(",") if part.strip()] or None

    trades = _filter_by_accounts(all_trades, requested)
    statistics = compute_statistics(trades)

    if not statistics.get("has_enough_data"):
        return Response(
            {"error": f"נדרשות לפחות {statistics.get('min_trades_for_profile', 20)} עסקאות "
                      f"כדי לבנות פרופיל. בבחירה הנוכחית יש {statistics.get('total_trades', 0)}."},
            status = status.HTTP_400_BAD_REQUEST)

    strengths, leaks = build_insights(statistics, trades)

    covered = requested if requested is not None else sorted(
        {t.account_id or UNASSIGNED for t in all_trades})

    try:
        written = generate_profile(request.user, statistics, strengths, leaks, covered)
    except RuntimeError as e:
        return Response({"error": str(e)}, status = status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(_profile_payload(request.user), status = status.HTTP_201_CREATED)

# ------------------------- WRITTEN PROFILE END ------------------------- #
