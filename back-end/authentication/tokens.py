"""
The one-time links: verifying an address, and resetting a forgotten password.

**Nothing is stored.** Both tokens are signed hashes of state that already lives on the user
row, so a link stops working the moment the thing it was issued for has happened - and there
is no table of outstanding tokens to expire, clean up or leak.

Django's own `default_token_generator` is used unchanged for password reset: its hash
includes the password hash and `last_login`, so setting a password invalidates the link that
set it, and so does logging in.

Verification needs its own generator, because activating an account changes neither of
those. Including `is_active` makes the link single-use by construction, and including the
address means a link mailed to an old address dies if the address changes.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from django.contrib.auth.models import User



class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_active}{user.email}"


verification_token = EmailVerificationTokenGenerator()



def pack_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def unpack_uid(uid):
    """The user a link points at, or None - a bad link is never an exception."""
    try:
        return User.objects.filter(pk = int(force_str(urlsafe_base64_decode(uid)))).first()
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
