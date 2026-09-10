from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db.models import Q

from project.throttling import EmailThrottle, LoginThrottle, RegisterThrottle

from .mail import send_password_changed, send_password_reset, send_verification
from .personal_data import erase, export
from .tokens import unpack_uid, verification_token



# ------------------------- HOME PAGE START ------------------------- #
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def index(request):
    return Response({"username": request.user.username, "email": request.user.email})
# ------------------------- HOME PAGE END ------------------------- #



# ------------------------- PASSWORDS START ------------------------- #

# Django's validators answer in English, and every message this product shows is in Hebrew.
# The mapping is on the validator's CODE rather than on its text, so it cannot drift when a
# Django release rewords a message.
PASSWORD_PROBLEMS = {
    "password_too_short": "הסיסמה קצרה מדי — צריך לפחות 8 תווים.",
    "password_too_common": "הסיסמה הזו נפוצה מדי וקל לנחש אותה.",
    "password_entirely_numeric": "סיסמה שכולה ספרות קלה מדי לפיצוח. הוסף אותיות.",
    "password_too_similar": "הסיסמה דומה מדי לשם המשתמש או לכתובת המייל שלך.",
}

FALLBACK_PROBLEM = "הסיסמה אינה עומדת בדרישות. נסה סיסמה ארוכה יותר עם אותיות וספרות."


def password_problem(password, user = None):
    """
    The first thing wrong with the password, in Hebrew - or None if it is fine.

    **The validators were configured in settings from the first day and never actually ran**,
    because `User.objects.create_user` does not call them; only Django's own forms and DRF
    serializers do. Until this existed, the password "1" was accepted.
    """
    try:
        validate_password(password, user)
    except ValidationError as problem:
        for item in getattr(problem, "error_list", []):
            if item.code in PASSWORD_PROBLEMS:
                return PASSWORD_PROBLEMS[item.code]
        return FALLBACK_PROBLEM

    return None

# ------------------------- PASSWORDS END ------------------------- #



# ------------------------- AUTHENTICATION START ------------------------- #

# ------------- REGISTRATION:
@api_view(["POST"])
@throttle_classes([RegisterThrottle])
def register(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    email = (request.data.get("email") or "").strip().lower()

    if not (username and password and email):
        return Response({"error": "אנא מלא את כל השדות"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(Q(username=username) | Q(email=email)).exists():
        return Response({"error": "שם המשתמש או כתובת האימייל כבר בשימוש."}, status=status.HTTP_400_BAD_REQUEST)

    problem = password_problem(password, User(username = username, email = email))
    if problem:
        return Response({"error": problem}, status=status.HTTP_400_BAD_REQUEST)

    # `is_active = False` until the address is confirmed, which is Django's own meaning of
    # the flag: the account exists and cannot be logged into. Nothing else in the product has
    # to learn a second notion of "verified", and every account that predates this is already
    # active and therefore already verified.
    try:
        user = User.objects.create_user(username=username, password=password, email=email,
                                        is_active=False)
    except ValidationError as e:
        return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)

    user.is_staff = False
    user.save()

    send_verification(user)

    return Response(
        {"success": "כמעט סיימנו — שלחנו לך מייל אישור. פתח אותו כדי להפעיל את החשבון."},
        status=status.HTTP_201_CREATED)



# ------------- EMAIL VERIFICATION:
@api_view(["POST"])
@throttle_classes([EmailThrottle])
def verify_email(request):
    user = unpack_uid(request.data.get("uid") or "")
    token = request.data.get("token") or ""

    if user and user.is_active:
        # The link was already used. From where the trader is standing that is a success, and
        # calling it a failure would send him looking for a second mail that will never come.
        # The token is dead either way - `is_active` is inside its hash.
        return Response({"success": "הכתובת כבר אושרה. אפשר להתחבר."})

    if not user or not verification_token.check_token(user, token):
        return Response({"error": "הקישור אינו תקף או שפג תוקפו. אפשר לבקש מייל חדש."},
                        status=status.HTTP_400_BAD_REQUEST)

    user.is_active = True
    user.save(update_fields = ["is_active"])

    return Response({"success": "הכתובת אושרה. אפשר להתחבר."})


@api_view(["POST"])
@throttle_classes([EmailThrottle])
def resend_verification(request):
    email = (request.data.get("email") or "").strip().lower()

    user = User.objects.filter(email__iexact = email, is_active = False).first()
    if user:
        send_verification(user)

    # The same answer whether or not that address is here. See the note on enumeration in
    # `forgot_password` - it applies word for word.
    return Response({"success": "אם הכתובת הזו ממתינה לאישור, המייל בדרך."})



# ------------- LOGIN:
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token['is_staff'] = user.is_staff
        return token


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        """
        One failure gets a specific answer instead of "wrong password": the right password on
        an account that has not confirmed its address.

        **It is only ever said to somebody who has just proved they own the account**, by
        giving its password - so it reveals nothing the password does not already. Without
        it, the trader is told his password is wrong, tries it again, and has no way to learn
        that a mail is sitting unopened in his inbox.
        """
        row = User.objects.filter(username = request.data.get("username") or "").first()

        if row and not row.is_active and row.check_password(request.data.get("password") or ""):
            return Response({"error": "החשבון קיים אבל כתובת המייל עוד לא אושרה.",
                             "needs_verification": True, "email": row.email},
                            status=status.HTTP_403_FORBIDDEN)

        return super().post(request, *args, **kwargs)



# ------------- KEEPING THE SESSION ALIVE:
class MyTokenRefreshView(TokenRefreshView):
    """
    The endpoint that was missing, and its absence was a bug rather than a gap.

    A refresh token was issued at login, stored by the client and blacklisted at logout - and
    never once exchanged for a new access token. So the 90-day refresh was decoration and the
    real session was `ACCESS_TOKEN_LIFETIME`: one day, after which the interceptor saw a 401
    and logged the trader out wherever he happened to be standing - mid-debrief included.

    `ROTATE_REFRESH_TOKENS` is already on, so each refresh returns a new pair and blacklists
    the one it replaced: a stolen refresh token stops working the moment the real client
    uses its own.
    """
    throttle_classes = [LoginThrottle]



# ------------- LOGOUT:
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.data.get("refresh_token")

    if not refresh_token:
        return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"success": "User has been logged out."})
    except Exception as e:
        return Response({"error": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

# ------------------------- AUTHENTICATION END ------------------------- #



# ------------------------- FORGOTTEN PASSWORD START ------------------------- #

@api_view(["POST"])
@throttle_classes([EmailThrottle])
def forgot_password(request):
    """
    **The answer is identical whether or not the address is registered, always.**

    An endpoint that says "no such user" is a way to ask this server, one address at a time,
    who its customers are - and for a product about somebody's trading account, that list is
    worth having to the wrong person. The rate limit is the other half: without it the same
    endpoint delivers our mail, on demand and repeatedly, to any address a sender picks.
    """
    email = (request.data.get("email") or "").strip().lower()

    user = User.objects.filter(email__iexact = email, is_active = True).first()
    if user:
        send_password_reset(user)

    return Response({"success": "אם הכתובת רשומה אצלנו, שלחנו אליה קישור לאיפוס הסיסמה."})


def end_other_sessions(user):
    """
    Blacklist every refresh token the account has out.

    **This is most of what a password change is for.** Somebody changing a password often
    believes another person is inside the account, and a session left holding a valid 90-day
    refresh token would make the change theatre.
    """
    for outstanding in OutstandingToken.objects.filter(user = user):
        BlacklistedToken.objects.get_or_create(token = outstanding)


@api_view(["POST"])
@throttle_classes([EmailThrottle])
def reset_password(request):
    user = unpack_uid(request.data.get("uid") or "")
    token = request.data.get("token") or ""
    password = request.data.get("password") or ""

    if not user or not default_token_generator.check_token(user, token):
        return Response({"error": "הקישור אינו תקף או שפג תוקפו. אפשר לבקש קישור חדש."},
                        status=status.HTTP_400_BAD_REQUEST)

    problem = password_problem(password, user)
    if problem:
        return Response({"error": problem}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(password)
    user.save(update_fields = ["password"])

    # The link itself dies on its own - Django's token hashes the password it was issued
    # against - and everything else the account had open dies here.
    end_other_sessions(user)

    # And the owner is told, whether or not he is the one who did it. See mail.py.
    send_password_changed(user)

    return Response({"success": "הסיסמה הוחלפה. אפשר להתחבר."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Changing a password from inside the account, which had no route at all before this.

    Without it, somebody who simply wanted a new password had to pretend to have forgotten
    the one he knows and go out through his inbox to get back in.

    **The current password is required even though the caller is already authenticated.** An
    access token left behind on a shared machine would otherwise be enough to take the
    account permanently, which is exactly the move this is meant to cost something.
    """
    current = request.data.get("current_password") or ""
    password = request.data.get("password") or ""

    if not request.user.check_password(current):
        return Response({"error": "הסיסמה הנוכחית שגויה."}, status=status.HTTP_400_BAD_REQUEST)

    problem = password_problem(password, request.user)
    if problem:
        return Response({"error": problem}, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(password)
    request.user.save(update_fields = ["password"])

    end_other_sessions(request.user)
    send_password_changed(request.user)

    # Every refresh token was just blacklisted, this caller's included - so a fresh pair goes
    # back with the answer. **Otherwise changing your own password would log you out**, which
    # teaches people not to change it.
    pair = RefreshToken.for_user(request.user)

    return Response({"success": "הסיסמה הוחלפה. שאר החיבורים לחשבון נותקו.",
                     "access": str(pair.access_token), "refresh": str(pair)})

# ------------------------- FORGOTTEN PASSWORD END ------------------------- #



# ------------------------- THE ACCOUNT ITSELF START ------------------------- #

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_data(request):
    """
    Everything held about the trader, as one JSON file he can keep.

    A download rather than a screen: this is his record, and the whole point of it is that it
    leaves with him.
    """
    payload = export(request.user)

    response = Response(payload)
    response["Content-Disposition"] = \
        f'attachment; filename="larson-{request.user.username}.json"'
    return response


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """
    **The password is required, and not as a formality.** This is the one irreversible action
    in the product that a stolen access token could otherwise carry out by itself - and
    unlike deleting the resume, there is no account left afterwards to notice it happened.
    """
    password = request.data.get("password") or ""

    if not request.user.check_password(password):
        return Response({"error": "הסיסמה שגויה."}, status=status.HTTP_400_BAD_REQUEST)

    removed = erase(request.user)

    return Response({"deleted": removed}, status=status.HTTP_200_OK)

# ------------------------- THE ACCOUNT ITSELF END ------------------------- #
