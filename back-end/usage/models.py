from django.contrib.auth.models import User
from django.db import models



# ------------------------- WHAT EACH ANSWER COST ------------------------- #

CHAT = "chat"
MENTOR = "mentor"
PROFILE = "profile"
MAPPING = "mapping"

KIND_CHOICES = [
    (CHAT, "צ'אט"),
    (MENTOR, "תחקיר"),
    (PROFILE, "פרופיל כתוב"),
    (MAPPING, "מיפוי עמודות"),
]


class TokenSpend(models.Model):
    """
    One row per call to the model, with what it actually cost.

    **The numbers are the API's own, not an estimate.** Every response carries a `usage`
    block, and it is the only figure that counts the thinking the model did on the way -
    which is billed as output and can be several times the answer the trader reads. A
    character count of the prompt would miss all of it.

    Rows are kept rather than folded into a running total on the user, because a total
    cannot answer "when does this free up again": a rolling window needs to know when each
    piece of it was spent. They are also what makes a bill explicable after the fact.
    """

    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = "token_spends")

    kind = models.CharField(max_length = 20, choices = KIND_CHOICES)

    input_tokens = models.IntegerField(default = 0)
    output_tokens = models.IntegerField(default = 0)

    # **Cached tokens are a third and fourth price, not a discount on the first.** `input_tokens`
    # is only the uncached remainder - the total the model actually read is the three input
    # figures added together - so a ledger that stored one of them would under-count a cached
    # request by most of its size and over-count its cost per token.
    cache_write_tokens = models.IntegerField(default = 0)
    cache_read_tokens = models.IntegerField(default = 0)

    created_at = models.DateTimeField(auto_now_add = True)

    class Meta:
        # Every read is "this user, since this moment", and it runs before each answer.
        indexes = [
            models.Index(fields = ["user", "created_at"]),
            # **`site_spent` filters on the date alone**, and an index whose leading column
            # is the user cannot serve that - it scanned the whole table once per call to
            # the model. Harmless at ten traders, a full scan per answer at a thousand.
            models.Index(fields = ["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} · {self.kind} · {self.input_tokens}+{self.output_tokens}"
