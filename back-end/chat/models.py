from django.db import models
from django.contrib.auth.models import User



# ------------------------- CONVERSATION START ------------------------- #

DEFAULT_TITLE = "שיחה חדשה"


class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = "conversations")

    # Taken from the first thing the trader asked, so the sidebar reads like a list of
    # questions rather than a list of timestamps. No model call is spent on naming it.
    title = models.CharField(max_length = 120, default = DEFAULT_TITLE)

    # The mentor is a single, permanent conversation - a relationship rather than a list of
    # threads. It lives in this table because it is the same machinery, and it is flagged so
    # the general chat's sidebar never shows it.
    is_mentor = models.BooleanField(default = False)

    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username} - {self.title}"

# ------------------------- CONVERSATION END ------------------------- #



# ------------------------- MESSAGE START ------------------------- #

USER = "user"
ASSISTANT = "assistant"

ROLE_CHOICES = [
    (USER, "User"),
    (ASSISTANT, "Larson"),
]


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete = models.CASCADE, related_name = "messages")

    role = models.CharField(max_length = 20, choices = ROLE_CHOICES)
    content = models.TextField(blank = True)

    # ------------- TEMPORARY DOCUMENT:
    # A file attached to one message is parsed into this conversation and nowhere else. It
    # never reaches the trades table, so a backtest the trader wants to compare against
    # cannot quietly become part of the resume it is being compared to.
    attachment_name = models.CharField(max_length = 255, blank = True)
    attachment_digest = models.TextField(blank = True)

    # ------------- THE VERDICT:
    # Whether this answer was a debrief that found broken rules, or one that found none. It
    # is stored rather than sent once, because a signal that vanishes on refresh is a signal
    # nobody can trust. Empty on every message that is not a debrief.
    # **The one question Larson asks under a debrief**, stored rather than only streamed -
    # the same lesson as `verdict` one field down. A card that exists only in the stream is
    # a card that vanishes on refresh, and this one asks him to commit to something.
    # Cleared the moment he answers it, either way.
    suggestion = models.JSONField(null = True, blank = True)

    verdict = models.CharField(max_length = 20, blank = True, choices = [
        ("kept", "Kept the rules"),
        ("broken", "Broke a rule"),
    ])

    # ------------- SAVED BY THE TRADER:
    # A starred answer is the one he wants to find again, and it is kept in the database
    # rather than in the browser: it is a pointer to a specific message row, and a pointer
    # that lives only on one device stops meaning anything the moment he opens another one.
    is_starred = models.BooleanField(default = False)
    starred_at = models.DateTimeField(null = True, blank = True)

    created_at = models.DateTimeField(auto_now_add = True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"

# ------------------------- MESSAGE END ------------------------- #
