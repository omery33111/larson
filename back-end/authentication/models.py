from django.contrib.auth.models import User
from django.db import models



# ------------------------- GOOGLE IDENTITY START ------------------------- #
#
# Which Google account an account here belongs to.
#
# **The link is kept on Google's subject id and not on the email address**, because the address
# is the part that moves. Somebody can change the address on their Google account, and Google
# can hand a freed address to a different person; the subject is issued once and never reused.
# Matching on email alone is how a login quietly starts opening somebody else's record.
#
# The address is still what joins a Google sign-in to an account that registered with a
# password here - but only on the first sign-in, only when Google says the address is verified,
# and after that this row is what the sign-in follows.

class GoogleIdentity(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE, related_name = "google")
    subject = models.CharField(max_length = 64, unique = True)
    email = models.EmailField()
    linked_at = models.DateTimeField(auto_now_add = True)

    def __str__(self):
        return f"{self.user.username} ← {self.email}"

# ------------------------- GOOGLE IDENTITY END ------------------------- #



# ------------------------- CONSENT START ------------------------- #
#
# That the terms and the privacy policy were accepted, when, and which wording was on the
# screen at the time.
#
# **A tick box with nothing behind it proves nothing.** This product sends a summary of
# somebody's trading record to a third party to answer them, the privacy policy is where that
# is disclosed, and consent that was never recorded cannot be shown afterwards. The version
# matters as much as the date: the answer to "what did they agree to" is a document, and
# documents get rewritten.

TERMS_VERSION = "2026-09"


class TermsAcceptance(models.Model):
    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = "acceptances")
    version = models.CharField(max_length = 20)
    accepted_at = models.DateTimeField(auto_now_add = True)

    # How the account was opened. Not decoration: a Google sign-up never sees the registration
    # form, so it has to be recorded that the notice it did see was the one on that button.
    VIA_FORM = "form"
    VIA_GOOGLE = "google"
    via = models.CharField(max_length = 10, default = VIA_FORM)

    class Meta:
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"{self.user.username} · {self.version} · {self.via}"

# ------------------------- CONSENT END ------------------------- #
