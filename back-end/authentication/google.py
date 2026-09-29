"""
Signing in with a Google account, verified here rather than taken on trust.

**Google itself is the whole integration.** No django-allauth, no social-auth, no third-party
identity service in the middle: the browser gets an ID token from Google, posts it here, and
this file checks the signature against Google's own published keys. That is the entire
protocol, it costs nothing, and there is no vendor between the trader and his account.

**What the check is actually for.** An ID token is a signed statement by Google that says
"this is the person, and this is their address". Without verifying the signature, anyone
could post a hand-written JSON blob naming somebody else's email and be handed their trading
record. Three things are checked and each one is load-bearing:

* **the signature**, against the keys at Google's JWKS endpoint, so the statement is Google's;
* **`aud`**, which must be our own client id - a token minted for a different site is a valid
  Google token and must not be accepted here, or any other site's login becomes ours;
* **`email_verified`**, because a Google account can carry an address it never proved, and an
  unproved address is exactly how one person signs in as another.
"""

import jwt
from jwt import PyJWKClient

from django.conf import settings



CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# Google's own documentation accepts both spellings in the issuer claim.
ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# The keys rotate every few days, and fetching them on every sign-in would put Google's
# endpoint in the middle of our login path. The client caches them and refetches when it sees
# a key id it does not hold.
_keys = None


def _key_client():
    global _keys
    if _keys is None:
        _keys = PyJWKClient(CERTS_URL, cache_keys = True)
    return _keys


class GoogleError(Exception):
    """Raised with a sentence that is safe to show the trader."""


def claims_from_credential(credential):
    """
    The claims inside a Google ID token, once it has been proved to be Google's.

    Split out from the view on purpose: this is the only part that talks to the network and
    does the cryptography, so everything around it can be tested without either.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleError("כניסה עם גוגל אינה מוגדרת בשרת.")

    if not credential:
        raise GoogleError("לא התקבל אישור מגוגל.")

    try:
        key = _key_client().get_signing_key_from_jwt(credential)

        claims = jwt.decode(
            credential,
            key.key,
            algorithms = ["RS256"],
            audience = settings.GOOGLE_CLIENT_ID,
            # Checked below against both spellings, which `issuer` cannot express in every
            # version of this library.
            options = {"verify_iss": False, "require": ["aud", "exp", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise GoogleError("האישור מגוגל פג. נסה שוב.")
    except Exception:
        # Deliberately one message for every other failure. Telling a caller which part of the
        # check it failed is a way to work out what would pass.
        raise GoogleError("האישור מגוגל אינו תקף.")

    if claims.get("iss") not in ISSUERS:
        raise GoogleError("האישור מגוגל אינו תקף.")

    if not claims.get("email"):
        raise GoogleError("חשבון גוגל הזה לא מסר כתובת מייל.")

    # **A Google account can hold an address it never proved.** Accepting one would let
    # somebody sign in as the owner of an address they merely typed into Google.
    if not claims.get("email_verified"):
        raise GoogleError("כתובת המייל בחשבון גוגל הזה אינה מאומתת.")

    return {
        # The stable identifier. An address can move between accounts and be changed by its
        # owner; this cannot, which is why the link is stored on it rather than on the email.
        "subject": str(claims["sub"]),
        "email": claims["email"].strip().lower(),
        "name": (claims.get("name") or "").strip(),
    }
