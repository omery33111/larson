from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import budget



# ------------------------- THE METER START ------------------------- #

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def state(request):
    """
    Where this trader stands against his budget.

    **Read once when a screen opens, and not polled.** The fresh state rides the `done` event
    at the end of every answer, so the only moment the client needs to ask is the one before
    it has heard anything - and a meter that polls is a meter that costs something to watch.
    """
    return Response(budget.state(request.user))

# ------------------------- THE METER END ------------------------- #
