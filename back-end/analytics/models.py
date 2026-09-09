from django.db import models
from django.contrib.auth.models import User



# ------------------------- TRADER PROFILE START ------------------------- #

# The written half of the resume. The statistics are recomputed on every request and never
# stored; this document is stored because generating it costs a model call.
class TraderProfile(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE, related_name = "trader_profile")

    profile_text = models.TextField()

    # Which accounts the text is about. A profile written for the funded account alone must
    # not be presented as describing everything.
    accounts = models.TextField(blank = True)

    generated_at = models.DateTimeField(auto_now = True)
    trades_at_generation = models.IntegerField(default = 0)
    score_at_generation = models.IntegerField(default = 0)

    def __str__(self):
        return f"פרופיל של {self.user.username}"

# ------------------------- TRADER PROFILE END ------------------------- #
