import json
import logging

from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from project.throttling import AIBurstThrottle, AIDailyThrottle
from usage import budget
from trades.models import Trade
from trades.parsers import SUPPORTED_EXTENSIONS, parse_file

from . import retrieval
from .failures import CALL_FAILED, configuration_fault
from .context import (EFFORT, MAX_TOKENS, MODEL, build_messages, build_system,
                      effort_for, statistics_document)
from .models import ASSISTANT, DEFAULT_TITLE, USER, Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer, StarredMessageSerializer



MAX_ATTACHMENT_MB = 20
TITLE_LENGTH = 60

# Everything below turns a failure into a sentence for the trader. Each of those places
# writes a line here as well, because a sentence he reads is not a record anybody can look
# at afterwards - and an exception caught inside a generator never reaches Django's own
# request logger, so without this it exists nowhere at all.
log = logging.getLogger("larson")



# ------------------------- CONVERSATIONS START ------------------------- #

# ------------- LIST / CREATE:
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def conversations(request):
    if request.method == "POST":
        created = Conversation.objects.create(user = request.user)
        return Response(ConversationSerializer(created).data, status = status.HTTP_201_CREATED)

    rows = Conversation.objects.filter(user = request.user, is_mentor = False)
    return Response(ConversationSerializer(rows, many = True).data)


# ------------- READ / RENAME / DELETE:
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def conversation(request, conversation_id):
    row = get_object_or_404(Conversation, id = conversation_id, user = request.user,
                            is_mentor = False)

    if request.method == "DELETE":
        row.delete()
        return Response(status = status.HTTP_204_NO_CONTENT)

    # Renaming costs nothing - no model call, one column. The auto-title is the first
    # question verbatim, which is a good default and a poor label for a thread that grew.
    if request.method == "PATCH":
        title = str(request.data.get("title", "")).strip()

        if not title:
            return Response({"error": "שם השיחה לא יכול להיות ריק."},
                            status = status.HTTP_400_BAD_REQUEST)

        row.title = title[:TITLE_LENGTH]
        row.save()

        return Response(ConversationSerializer(row).data)

    return Response({
        **ConversationSerializer(row).data,
        "messages": MessageSerializer(row.messages.all(), many = True).data,
    })

# ------------------------- CONVERSATIONS END ------------------------- #



# ------------------------- SAVED ANSWERS START ------------------------- #
#
# The trader marks the answers he wants to come back to. They are stored on the message row
# itself rather than in a list of their own: a saved answer is not a copy of the text, it is
# a pointer back to the moment it was said, and the screen uses it to jump there.

# ------------- TOGGLE:
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def star(request, message_id):
    row = get_object_or_404(Message, id = message_id, conversation__user = request.user)

    row.is_starred = not row.is_starred
    row.starred_at = timezone.now() if row.is_starred else None
    row.save()

    return Response({"id": row.id, "is_starred": row.is_starred})


# ------------- LIST:
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def starred(request):
    rows = (Message.objects
            .filter(conversation__user = request.user, is_starred = True)
            .select_related("conversation")
            # `-id` breaks the tie. Two answers starred inside the same millisecond share a
            # timestamp, and then the order is whatever the database felt like - which is how
            # a "newest first" test fails once in every few runs and passes the rest.
            .order_by("-starred_at", "-id"))

    return Response(StarredMessageSerializer(rows, many = True).data)

# ------------------------- SAVED ANSWERS END ------------------------- #



# ------------------------- TEMPORARY DOCUMENT START ------------------------- #
#
# A file attached to a message is parsed straight into the prompt and nowhere else. It never
# reaches the trades table, which is the whole point: a backtest you want to measure your
# execution against must not become part of the record you are measuring.

def _attachment_digest(uploaded):
    """Returns (digest_text, error_message). Exactly one of them is filled."""
    if not any(uploaded.name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        return None, "סוג הקובץ אינו נתמך. אפשר לצרף CSV, TSV, אקסל (xlsx/xls) או דוח HTML של MT4/MT5."

    if uploaded.size > MAX_ATTACHMENT_MB * 1024 * 1024:
        return None, f"הקובץ גדול מ-{MAX_ATTACHMENT_MB}MB."

    try:
        parsed, report = parse_file(uploaded.read(), uploaded.name)
    except ValueError as e:
        return None, str(e)
    except Exception:
        # A file the parser chokes on in some other way still has to come back as a sentence.
        # Left to raise, it would 500 before the stream opens, and the client - which only
        # knows how to read events - would report it as a dropped connection.
        #
        # **Warning and not error, deliberately.** A file somebody exported wrong is an outcome
        # this function is built to have, not a fault in the server. At error level the SDK
        # would raise a ticket and send mail every time a trader picks the wrong export, which
        # is how a monitor becomes something people stop reading.
        log.warning("Attachment %s could not be parsed", uploaded.name, exc_info = True)
        return None, "לא הצלחנו לקרוא את הקובץ. ודא שזה ייצוא עסקאות תקין."

    if not parsed:
        return None, "לא נמצאו עסקאות תקינות בקובץ."

    # Built in memory and never saved. Running them through the same engine as the resume is
    # what makes the two sides comparable at all - a digest in some other shape would leave
    # the model doing arithmetic across two formats, which is exactly what it must not do.
    document = statistics_document(Trade(**row) for row in parsed)

    if document is None:
        return None, "לא נמצאו בקובץ עסקאות עם תוצאה."

    digest = {
        "שם_הקובץ": uploaded.name,
        "שורות_בקובץ": report["total_rows"],
        "עסקאות_שנקראו": report["parsed"],
        "נתוני_הקובץ": document,
    }

    return json.dumps(digest, ensure_ascii = False, indent = 1, default = str), None

# ------------------------- TEMPORARY DOCUMENT END ------------------------- #



# ------------------------- STREAMING START ------------------------- #
#
# SSE, not WebSocket. Token flow is one-directional, which is exactly the case
# StreamingHttpResponse already covers - no channels, no ASGI, no Redis.

def _event(payload):
    return f"data: {json.dumps(payload, ensure_ascii = False)}\n\n"


def _sse(generator):
    response = StreamingHttpResponse(generator, content_type = "text/event-stream")
    response["Cache-Control"] = "no-cache"
    # Tells a proxy not to sit on the response until it is complete, which would turn a
    # streamed answer back into the frozen screen this milestone exists to avoid.
    response["X-Accel-Buffering"] = "no"
    return response


def _error_stream(message):
    """
    An error found before the model is called is still delivered as a stream.

    The client then has one code path for every outcome, instead of a JSON branch and a
    stream branch that have to be kept in agreement.
    """
    def once():
        yield _event({"type": "error", "error": message})

    return _sse(once())


# Two windows on the meter, because this is the endpoint that spends money: one
# answer is allowed up to 64k output tokens. See project/throttling.py.
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIBurstThrottle, AIDailyThrottle])
def stream(request, conversation_id):
    # The mentor has its own endpoint, its own persona and its own rules about what a file
    # means. Reaching it through this one would quietly strip all three.
    row = get_object_or_404(Conversation, id = conversation_id, user = request.user,
                            is_mentor = False)

    text = str(request.data.get("message", "")).strip()
    uploaded = request.FILES.get("file")

    if not text and not uploaded:
        return _error_stream("אין מה לשלוח.")

    digest = ""

    if uploaded:
        digest, error = _attachment_digest(uploaded)
        if error:
            return _error_stream(error)

    if not settings.ANTHROPIC_API_KEY:
        return _error_stream(configuration_fault("ANTHROPIC_API_KEY is empty"))

    question = Message.objects.create(
        conversation = row,
        role = USER,
        content = text,
        attachment_name = uploaded.name if uploaded else "",
        attachment_digest = digest or "",
    )

    # The first question names the conversation. Spending a model call on a title would add
    # a second call to every new thread, to save the user reading his own words back.
    if row.title == DEFAULT_TITLE:
        source = text or (uploaded.name if uploaded else "")
        if source:
            row.title = source[:TITLE_LENGTH].strip() + ("…" if len(source) > TITLE_LENGTH else "")

    row.save()

    system = build_system(request.user)
    messages = build_messages(row)

    # **A question about a specific trade gets that trade, not an average.**
    #
    # Only when the question looks specific, which most are not - a general one pays neither
    # the mapping call nor the second of silence before the first token, and that silence is
    # the thing the whole product feels like. See `retrieval.py` for why the model returns
    # parameters and never a query.
    retrieval.attach(messages, retrieval.block_for(request.user, text,
                                                   billed_to = request.user))

    return _sse(_answer(row, question, system, messages))


def _answer(row, question, system, messages, prelude = "", verdict = "",
            budget_kind = "chat", suggestion = None):
    """
    Yields the answer token by token, then stores it.

    `prelude` is text the server wrote itself and that belongs at the top of the same bubble -
    the mentor's documentation receipt. It goes out as the first delta and is stored as part
    of the answer, so there is one message row and one code path rather than two rows to
    reconcile afterwards.

    Anything that goes wrong here is delivered as an event rather than raised: the response
    headers are already out by the time this runs, so an exception would reach the browser
    as a truncated body with no explanation attached.
    """
    try:
        import anthropic
    except ImportError:
        yield _event({"type": "error",
                      "error": configuration_fault("the anthropic package is not installed")})
        return

    # **Checked before the call and not after it.** The rate limits above count requests; this
    # counts what they cost, and it is the one that stands between a loop and the bill. It
    # goes out as an error event like everything else here, so the client has one path.
    if not budget.has_room(row.user):
        yield _event({"type": "error", "error": budget.exhausted_message(row.user),
                      "usage": budget.state(row.user)})
        return

    client = anthropic.Anthropic(api_key = settings.ANTHROPIC_API_KEY)

    answer = Message.objects.create(conversation = row, role = ASSISTANT, content = prelude,
                                    verdict = verdict, suggestion = suggestion)

    # The verdict rides the start event as well, so the avatar carries it while the answer is
    # still being written rather than only after a reload. The card does not: it belongs
    # **under** a finished answer, and showing it while he is still reading would ask him to
    # decide before he has heard why.
    yield _event({"type": "start", "message_id": answer.id, "question_id": question.id,
                  "title": row.title, "verdict": verdict})

    collected = []

    if prelude:
        collected.append(prelude)
        yield _event({"type": "delta", "text": prelude})

    try:
        try:
            with client.messages.stream(
                model = MODEL,
                max_tokens = MAX_TOKENS,
                # Drops to a shorter deliberation only once he is near his ceiling, which
                # buys him about 25% more answers out of the same money. See `effort_for`.
                output_config = {"effort": effort_for(row.user)},
                system = system,
                messages = messages,
            ) as handle:
                for delta in handle.text_stream:
                    collected.append(delta)
                    yield _event({"type": "delta", "text": delta})

                final = handle.get_final_message()

        except Exception as e:
            log.exception("Claude stream failed (conversation %s)", row.id)
            # **The exception text is logged, not shown.** It comes from a third party's
            # client library and describes our infrastructure, not anything the trader can
            # act on - request ids, endpoints, whatever the SDK chose to say. He gets a
            # sentence he can do something with; the detail is on the line above.
            yield _event({"type": "error",
                          "error": CALL_FAILED})
            return

        # A safety classifier declines with HTTP 200 and no usable content, so the stop
        # reason has to be read before the text is trusted.
        if final.stop_reason == "refusal":
            yield _event({"type": "error", "error": "המודל סירב לענות על ההודעה הזו."})
            return

        # Touched only once the answer exists, so the sidebar orders by real activity.
        row.save()

        # What it actually cost, taken from the response rather than estimated - the API's
        # figure is the only one that counts the thinking, which is billed as output and can
        # be several times the answer the trader reads.
        if getattr(final, "usage", None):
            budget.record(row.user, budget_kind, final.usage)

        # The fresh state rides the last event, so the meter is current without the client
        # having to ask for it after every answer.
        yield _event({"type": "done", "suggestion": suggestion, "message_id": answer.id,
                      "usage": budget.state(row.user)})

    finally:
        # Runs on every path there is: a finished answer, a failed call, and a browser that
        # hung up mid-answer - which closes this generator rather than raising anything a
        # normal except clause would see. Whatever arrived is kept, so pressing stop leaves
        # a readable thread instead of an empty bubble.
        answer.content = "".join(collected).strip()
        answer.save()

# ------------------------- STREAMING END ------------------------- #
