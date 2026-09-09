from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chat.models import ASSISTANT, USER, Conversation, Message
from chat.serializers import MessageSerializer
from chat.views import _answer, _error_stream, _sse
from trades.models import Trade, TradeFile

from analytics.statistics import compute_statistics

from .compliance import check_plan
from .context import (GREETING, baseline_set, mentor_messages, mentor_system, receipt,
                      update_prompt)
from .deviation import build_deviation



MENTOR_TITLE = "המנטור"



# ------------------------- THE ONE CONVERSATION START ------------------------- #
#
# One conversation per trader, forever. It is not a list with a single row by accident - the
# mentor is a standing relationship, and being unable to open a second one is the feature:
# there is exactly one place where the record of "how have I been doing" lives.

def _conversation(user):
    row = Conversation.objects.filter(user = user, is_mentor = True).first()

    if not row:
        row = Conversation.objects.create(user = user, is_mentor = True, title = MENTOR_TITLE)

        # He speaks first, and what he says is the ask. An empty screen would put the burden
        # of starting on the trader, which is the opposite of what this page is for.
        Message.objects.create(conversation = row, role = ASSISTANT, content = GREETING)

    _note_baseline(row, user)

    return row


def _note_baseline(conversation, user):
    """
    The line that says there is finally something to compare against.

    It answers to the state rather than to an event: the moment the resume stops being empty,
    the mentor says so and names what he is waiting for next. That makes it right however the
    founding trades arrived - through this screen, or filed through "my resume" before he ever
    came here.

    The thread is its own guard. It is written only while the greeting is still the only thing
    in it, so it can be said exactly once without a flag of its own to keep in sync.
    """
    if conversation.messages.count() != 1:
        return

    total = Trade.objects.filter(user = user).count()

    if not total:
        return

    Message.objects.create(conversation = conversation, role = ASSISTANT,
                           content = baseline_set(total))


def _resume_state(user):
    """
    What Larson currently knows, and how stale it is.

    `last_trade` rather than "last upload" on purpose: the gap that matters is between the
    trading he has done and the trading he has told anyone about.
    """
    trades = Trade.objects.filter(user = user)
    total = trades.count()

    if not total:
        return {"total_trades": 0, "last_trade": None, "days_since": None}

    last = trades.order_by("-executed_at").first().executed_at

    return {
        "total_trades": total,
        "last_trade": last,
        "days_since": (timezone.now() - last).days,
    }


def _pending(user):
    """
    The confirmed file that is still waiting to be sent, if there is one.

    It is read from the database rather than held on the screen for one reason: the trader
    may attach a file, get called away, close the tab, and come back tomorrow on another
    machine. His trades are already saved - what is still owed is the conversation about
    them - and something he was in the middle of should not disappear because he navigated.
    """
    row = (TradeFile.objects
           .filter(user = user, confirmed = True, awaiting_debrief = True)
           .order_by("-uploaded_at")
           .first())

    if not row:
        return None

    return {
        "id": row.id,
        "original_name": row.original_name,
        "imported_count": row.imported_count,
        "duplicate_count": row.duplicate_count,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mentor(request):
    row = _conversation(request.user)

    return Response({
        "conversation_id": row.id,
        "messages": MessageSerializer(row.messages.all(), many = True).data,
        "resume": _resume_state(request.user),
        "pending_file": _pending(request.user),
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def pending(request):
    """
    Take the waiting file off the composer.

    It does not remove anything from the resume, and the screen says so: the trades were
    saved the moment he confirmed them, and undoing that is what "my resume" is for. All
    this drops is the debrief he decided not to ask for.
    """
    TradeFile.objects.filter(user = request.user, awaiting_debrief = True).update(
        awaiting_debrief = False)

    return Response({"pending_file": None})

# ------------------------- THE ONE CONVERSATION END ------------------------- #



# ------------------------- THE DEBRIEF START ------------------------- #

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stream(request):
    row = _conversation(request.user)

    text = str(request.data.get("message", "")).strip()
    trade_file_id = request.data.get("trade_file_id")

    if not text and not trade_file_id:
        return _error_stream("אין מה לשלוח.")

    # A debrief with nothing to compare against is not a debrief. Talking to him before he has
    # seen a single trade would cost a model call to produce generalities, and would teach the
    # trader that the mentor has nothing specific to say - which is the one impression this
    # screen cannot afford to make first. Sending a file is always allowed: that is the way
    # out of this state.
    if not trade_file_id and not Trade.objects.filter(user = request.user).exists():
        return _error_stream(
            "לארסון עוד לא ראה אף עסקה שלך, אז אין לו למה להשוות. שלח לו קובץ עסקאות קודם.")

    if not settings.ANTHROPIC_API_KEY:
        return _error_stream(
            "לא הוגדר מפתח API של Claude. אם כבר הוספת ANTHROPIC_API_KEY לקובץ back-end/.env, "
            "עצור את השרת לגמרי והפעל אותו מחדש.")

    prelude = ""
    verdict = ""
    briefing = text

    if trade_file_id:
        trade_file = get_object_or_404(TradeFile, id = trade_file_id, user = request.user)

        if not trade_file.confirmed:
            # The gate is the point. Nothing is analysed until the trader has said yes to it
            # entering his record.
            return _error_stream("הקובץ עדיין לא אושר לקליטה.")

        # The baseline is the resume as it stood before this file - which is exactly what
        # "compared to what I already know about you" means.
        recent = list(Trade.objects.filter(user = request.user, trade_file = trade_file))
        baseline = list(Trade.objects.filter(user = request.user).exclude(trade_file = trade_file))

        currency = _currency(recent or baseline)
        zone = _timezone(recent or baseline)

        report = build_deviation(baseline, recent, currency, zone)

        # The second report, and the one that answers a session of one. The deviation needs a
        # sample; this needs a single trade, because a rule is broken or kept by each trade on
        # its own. Without it, closing a day on one trade got "come back with more" - which is
        # the mentor refusing to do the only job he has.
        plan = check_plan(compute_statistics(baseline), baseline, recent, currency, zone)

        # The plan check already decided this; reading it is free. Broken rules outrank kept
        # ones - a debrief that found a repeat offence is not a green day whatever else went
        # right in it.
        if plan.get("available"):
            verdict = "broken" if plan["broken"] else ("kept" if plan["kept"] else "")

        # Consumed the moment it is sent, not when the answer finishes: the screen has to
        # stop offering it immediately, and a second press must not produce a second debrief.
        if trade_file.awaiting_debrief:
            trade_file.awaiting_debrief = False
            trade_file.save(update_fields = ["awaiting_debrief"])

        prelude = receipt(trade_file)
        # `text` is still whatever he typed here - the fallback title below has not run yet -
        # so a note sent with the file reaches the model instead of being replaced away.
        briefing = update_prompt(report, plan, len(baseline) + len(recent), len(recent),
                                 trade_file.original_name, is_first = not baseline, note = text)

        if not text:
            text = f"עדכון: {trade_file.original_name}"

    question = Message.objects.create(conversation = row, role = USER, content = text,
                                      attachment_name = trade_file.original_name
                                                        if trade_file_id else "")

    row.save()

    system = mentor_system(request.user)
    messages = mentor_messages(row)

    # The briefing replaces the last user turn rather than being appended as its own message:
    # what the trader typed is on screen, and what the model needs to see is the report.
    if messages and briefing != text:
        messages[-1]["content"] = briefing

    return _sse(_answer(row, question, system, messages, prelude, verdict))


def _currency(trades):
    for trade in trades:
        if trade.currency:
            return trade.currency
    return "USD"


def _timezone(trades):
    for trade in trades:
        if trade.source_timezone:
            return trade.source_timezone
    return "Asia/Jerusalem"

# ------------------------- THE DEBRIEF END ------------------------- #
