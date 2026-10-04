from django.contrib.auth.models import User
from django.db import models



# ------------------------- DECLARED RULES START ------------------------- #
#
# **The difference between an auditor and a mentor.**
#
# `compliance.py` has always derived rules from the record: the losing buckets, each carried
# with the evidence that produced it. That finds what is broken, and it is the harder half.
# What it cannot do is hold the trader to something **he decided** - "this month I do not
# enter before 10:00" - because nothing anywhere stored that he had decided it.
#
# **A declared rule is structured, never free text, and that is not a limitation of the form.**
# Every number in this product is computed in python and only narrated by the model; a rule
# typed as a sentence could only be judged by the model, which would make compliance an
# opinion. A kind and a number can be judged by a loop, which is why the trade that broke it
# can be named by date and by time.
#
# The kinds are deliberately the ones the checker already understands, plus the two that are
# about a day rather than a trade. Nothing here is a new concept the engine has to learn - it
# is the same five families, with the threshold coming from the trader instead of from his
# losses.


class TraderRule(models.Model):
    """One commitment, in a shape a loop can judge."""

    # ------------- THE KINDS:
    #
    # Each maps onto a check that already exists or onto a day-level pass. `needs` says what
    # the number means, because a rule whose unit is ambiguous is a rule that gets set wrong
    # once and then quietly never fires.
    NO_BEFORE = "no_before"
    NO_AFTER = "no_after"
    MIN_HOLD = "min_hold"
    MAX_SIZE = "max_size"
    NO_REVENGE_WITHIN = "no_revenge_within"
    MAX_TRADES_PER_DAY = "max_trades_per_day"
    MAX_DAILY_LOSS = "max_daily_loss"
    ONLY_SETUPS = "only_setups"

    KINDS = [
        (NO_BEFORE, "לא להיכנס לפני שעה"),
        (NO_AFTER, "לא להיכנס אחרי שעה"),
        (MIN_HOLD, "לא להחזיק פחות מ-X דקות"),
        (MAX_SIZE, "לא לעלות מעל X חוזים"),
        (NO_REVENGE_WITHIN, "לא להיכנס תוך X דקות מהפסד"),
        (MAX_TRADES_PER_DAY, "לא יותר מ-X עסקאות ביום"),
        (MAX_DAILY_LOSS, "לא לעבור הפסד יומי של X"),
        (ONLY_SETUPS, "לסחור רק בסטאפים מהרשימה"),
    ]

    user = models.ForeignKey(User, on_delete = models.CASCADE, related_name = "trading_rules")

    kind = models.CharField(max_length = 32, choices = KINDS)

    # The threshold. Hours for the two time rules, minutes for hold and revenge, contracts for
    # size, a count for the daily cap, money for the daily loss.
    number = models.FloatField(null = True, blank = True)

    # Only `only_setups` uses this: a comma-separated allow-list, matched after the same
    # cleaning every label from a file goes through.
    setups = models.TextField(blank = True)

    # **Switched off rather than deleted, because a rule he kept for two months and then
    # dropped is part of the story.** The debrief only checks the active ones.
    is_active = models.BooleanField(default = True)

    created_at = models.DateTimeField(auto_now_add = True)

    class Meta:
        ordering = ["kind", "id"]
        constraints = [
            # One rule per kind per trader. Two conflicting ceilings on the same thing is not
            # a stricter plan, it is a plan with no answer - and the debrief would report both.
            models.UniqueConstraint(fields = ["user", "kind"], name = "one_rule_per_kind"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.kind}"

# ------------------------- DECLARED RULES END ------------------------- #
