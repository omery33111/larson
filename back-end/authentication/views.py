from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from django.contrib.auth.models import User, UnicodeUsernameValidator
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q

from project.throttling import EmailThrottle, LoginThrottle, RegisterThrottle

from .google import GoogleError, claims_from_credential
from .mail import send_password_changed, send_password_reset, send_verification
from .models import TERMS_VERSION, GoogleIdentity, TermsAcceptance
from .personal_data import erase, export
from .tokens import unpack_uid, verification_token



# ------------------------- HOME PAGE START ------------------------- #
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def index(request):
    """
    **`has_password` is not a detail.** An account opened with Google has no password at all,
    and three screens are built on the assumption that one exists: changing it, and deleting
    the account, both of which ask for the current one. The client has to know which of them
    to offer before the trader is standing in front of a field he can never fill.
    """
    google = GoogleIdentity.objects.filter(user = request.user).first()

    return Response({"username": request.user.username, "email": request.user.email,
                     "has_password": request.user.has_usable_password(),
                     "google_email": google.email if google else ""})
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

def _agreed(value):
    """
    Whether a tick box came back ticked.

    **A form post carries `False` as the string "False", and every non-empty string is true.**
    Reading this with a plain truth test accepts an unticked box, which is the one thing the
    box exists to prevent.
    """
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")

    return bool(value)


# ------------- REGISTRATION:
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
def register(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    email = (request.data.get("email") or "").strip().lower()

    if not (username and password and email):
        return Response({"error": "אנא מלא את כל השדות"}, status=status.HTTP_400_BAD_REQUEST)

    # **Enforced here and not only in the form.** A tick box that the server does not insist on
    # is a graphic, and the record of what was agreed to is the thing that has to exist later.
    if not _agreed(request.data.get("accepted_terms")):
        return Response({"error": "צריך לאשר את תנאי השימוש ומדיניות הפרטיות."},
                        status=status.HTTP_400_BAD_REQUEST)

    # **Nor was the username.** It reaches the navbar, the token claims and the body of
    # every mail this product sends, and nothing stopped it being a line of HTML or a
    # lookalike of somebody else's name. Django's own validator is what every one of its
    # forms uses: letters, digits, and @ . + - _ only.
    try:
        UnicodeUsernameValidator()(username)
    except ValidationError:
        return Response(
            {"error": "שם המשתמש יכול להכיל אותיות, ספרות והתווים . + - _ @ בלבד."},
            status=status.HTTP_400_BAD_REQUEST)

    # **Never checked before this.** `create_user` runs no validators - the same gap that let
    # the password "1" through - so an address that cannot receive mail was accepted, and the
    # account it opened could never be verified by the one mail that would have activated it.
    try:
        validate_email(email)
    except ValidationError:
        return Response({"error": "כתובת המייל אינה תקינה."}, status=status.HTTP_400_BAD_REQUEST)

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

    TermsAcceptance.objects.create(user = user, version = TERMS_VERSION,
                                   via = TermsAcceptance.VIA_FORM)

    send_verification(user)

    return Response(
        {"success": "כמעט סיימנו — שלחנו לך מייל אישור. פתח אותו כדי להפעיל את החשבון."},
        status=status.HTTP_201_CREATED)



# ------------- EMAIL VERIFICATION:
@api_view(["POST"])
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
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



# ------------- SIGNING IN WITH GOOGLE:

def _pair_for(user):
    """The same token pair the password login issues, claims included."""
    token = MyTokenObtainPairSerializer.get_token(user)
    return {"access": str(token.access_token), "refresh": str(token)}


def _free_username(email, name):
    """
    A username nobody has. Google does not supply one, and this product shows it everywhere.

    The address' local part first, because that is what the person already calls themselves;
    their display name second; and a number only if both are taken.
    """
    for candidate in (email.split("@")[0], name.replace(" ", "")):
        base = "".join(c for c in candidate if c.isalnum() or c in "._-")[:140]
        if not base:
            continue

        if not User.objects.filter(username__iexact = base).exists():
            return base

        for n in range(2, 200):
            taken = f"{base}{n}"
            if not User.objects.filter(username__iexact = taken).exists():
                return taken

    return f"trader{User.objects.count() + 1}"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def google_login(request):
    """
    One button that both registers and signs in, because from where the trader is standing
    those are the same act and asking him which one he meant is a question he cannot answer.

    **The order of the lookups is the security of the whole thing:**

    1. **The stored link first.** Once an account is tied to a Google subject, that is what a
       later sign-in follows - not the address, which can be changed on Google's side.
    2. **A verified address second, and only to link.** This is what lets somebody who
       registered with a password here press the Google button and land in the account they
       already have, instead of quietly opening a second one beside it. It is safe only
       because `claims_from_credential` refuses a token whose address Google has not proved.
    3. **A new account last**, with no usable password: there is nothing to guess, and the way
       to gain one is the ordinary reset mail, which proves the mailbox all over again.
    """
    try:
        claims = claims_from_credential(request.data.get("credential") or "")
    except GoogleError as problem:
        return Response({"error": str(problem)}, status=status.HTTP_400_BAD_REQUEST)

    identity = GoogleIdentity.objects.filter(subject = claims["subject"]).select_related("user").first()

    if identity:
        user = identity.user

        # The address on the Google account can change, and the row should follow it so the
        # account page keeps telling the truth about which account this is.
        if identity.email != claims["email"]:
            identity.email = claims["email"]
            identity.save(update_fields = ["email"])
    else:
        with transaction.atomic():
            user = User.objects.filter(email__iexact = claims["email"]).first()
            created = user is None

            # **The address links once and once only.** Arriving here with a second Google
            # subject on an address that already has one means Google handed that address to
            # a different account - and opening the existing record for them is exactly the
            # takeover the subject link exists to prevent. Refusing also keeps one address to
            # one account, which registration already relies on.
            if user and GoogleIdentity.objects.filter(user = user).exists():
                return Response(
                    {"error": "כתובת המייל הזו כבר מקושרת לחשבון גוגל אחר. "
                              "אפשר להתחבר עם סיסמה, או לאפס סיסמה דרך \"שכחתי סיסמה\"."},
                    status=status.HTTP_400_BAD_REQUEST)

            if created:
                user = User.objects.create(username = _free_username(claims["email"], claims["name"]),
                                           email = claims["email"], is_active = True)
                # **No password rather than a random one.** An unusable password cannot be
                # guessed, cannot be brute-forced, and makes `has_usable_password` tell the
                # truth to every screen that asks.
                user.set_unusable_password()
                user.save()

                TermsAcceptance.objects.create(user = user, version = TERMS_VERSION,
                                               via = TermsAcceptance.VIA_GOOGLE)

            GoogleIdentity.objects.create(user = user, subject = claims["subject"],
                                          email = claims["email"])

    # Somebody who registered here, never opened the verification mail, and then arrived
    # through Google has just had the address proved by Google itself. Sending him back to an
    # inbox to prove it again would be asking for something he has already given.
    if not user.is_active:
        user.is_active = True
        user.save(update_fields = ["is_active"])

    return Response(_pair_for(user))



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
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
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

    # **An account opened with Google has no current password to give.** Letting it set one
    # from inside the session would mean an access token left on a shared machine is enough to
    # fit the account with a second, permanent door. The reset mail is the way in, and it
    # proves the mailbox rather than merely holding a token.
    if not request.user.has_usable_password():
        return Response({"error": "החשבון הזה נפתח עם גוגל ואין לו סיסמה. "
                                  "כדי לקבוע סיסמה, השתמש ב\"שכחתי סיסמה\" ונאמת את כתובת המייל."},
                        status=status.HTTP_400_BAD_REQUEST)

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

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def end_sessions(request):
    """
    Sign out of everywhere else, without changing the password.

    The machinery already existed and only a password change could reach it. **The situation
    it is for does not always involve a password**: a session left open on somebody else's
    laptop, a phone that was lost, a shared machine at a prop firm. Making that person change
    a password they are happy with, in order to close a door, is a tax on doing the safe thing.
    """
    end_other_sessions(request.user)

    # Including this caller's, so a fresh pair goes back with the answer for the same reason
    # the password change returns one: the safe action must not log you out of the device you
    # did it from.
    pair = RefreshToken.for_user(request.user)

    return Response({"success": "כל שאר החיבורים לחשבון נותקו.",
                     "access": str(pair.access_token), "refresh": str(pair)})

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
    credential = request.data.get("google_credential") or ""

    # **An account opened with Google still has to prove itself, with the thing it actually
    # has.** Accepting the typed confirmation alone would make this the one destructive action
    # in the product that a stolen access token can finish on its own.
    if request.user.has_usable_password():
        if not request.user.check_password(password):
            return Response({"error": "הסיסמה שגויה."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        try:
            claims = claims_from_credential(credential)
        except GoogleError as problem:
            return Response({"error": str(problem)}, status=status.HTTP_400_BAD_REQUEST)

        linked = GoogleIdentity.objects.filter(user = request.user).first()

        if not linked or linked.subject != claims["subject"]:
            return Response({"error": "חשבון הגוגל שאושר אינו החשבון המקושר."},
                            status=status.HTTP_400_BAD_REQUEST)

    removed = erase(request.user)

    return Response({"deleted": removed}, status=status.HTTP_200_OK)

# ------------------------- THE ACCOUNT ITSELF END ------------------------- #
