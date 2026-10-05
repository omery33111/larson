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
# **A rule in his own words comes first, and the structured kinds behind it are examples.**
# "Only enter when delta is high and there is an IFVG" is what a trader's plan actually
# sounds like; "do not enter before 10:00" is one narrow case of that, and leading with the
# narrow cases teaches him the feature is a menu rather than a place to write his plan down.
#
# **His sentence is still judged by a loop, never by the model**, and the way that holds is
# the `llm_mapping` pattern: the sentence is interpreted **once, when he saves it**, into
# terms stored on the row, and every check after that is python comparing strings. One
# interpretation, bought once, identical on every run - so the trade that broke it can be
# named by date and by time, exactly like the hour rule.
#
# **And it is only ever as precise as the trade's own record, which is not a flaw in the
# code.** Entry time is a column on every trade, so an hour rule can always be judged. "Delta
# was high" is a column nowhere, and "IFVG" exists only if he tagged it - so a trade carrying
# no text at all cannot answer, and is reported as unjudged rather than as kept. `coverage`
# on the save response says how many of his trades can answer at all, because a rule that
# silently judges nothing is worse than no rule.
#
# The structured kinds are deliberately the ones the checker already understands, plus the two
# that are about a day rather than a trade.
#
# **`min_hold` was removed, and the reason is worth keeping.** "Do not hold for less than X
# minutes" reads like discipline and is not: a good entry that hits its stop in ninety seconds
# is a short hold the trader did not choose. A rule he cannot obey by deciding to is a rule
# that fires at him for the market's behaviour, and that is the one way this feature loses
# his trust completely.


class TraderRule(models.Model):
    """One commitment, in a shape a loop can judge."""

    # ------------- THE KINDS:
    #
    # Each maps onto a check that already exists or onto a day-level pass. `needs` says what
    # the number means, because a rule whose unit is ambiguous is a rule that gets set wrong
    # once and then quietly never fires.
    CUSTOM = "custom"
    NO_BEFORE = "no_before"
    NO_AFTER = "no_after"
    MAX_SIZE = "max_size"
    NO_REVENGE_WITHIN = "no_revenge_within"
    MAX_TRADES_PER_DAY = "max_trades_per_day"
    MAX_DAILY_LOSS = "max_daily_loss"
    ONLY_SETUPS = "only_setups"

    KINDS = [
        # First in the list because it is first on the screen, and the ordering on this model
        # is what the menu is rendered from.
        (CUSTOM, "תנאי בניסוח שלך"),
        (NO_BEFORE, "לא להיכנס לפני שעה"),
        (NO_AFTER, "לא להיכנס אחרי שעה"),
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

    # ------------- THE FREE-TEXT RULE:
    #
    # **His sentence, kept exactly as he typed it, because it is what the screen shows back
    # and what the debrief quotes.** It is never what gets judged.
    text = models.TextField(blank = True)

    # **What gets judged**: the terms his sentence was interpreted into, once, at save time.
    #
    #     {"require": [["ifvg", "inverse fvg"], ["delta"]], "forbid": ["news"]}
    #
    # Each requirement is a list of spellings and is satisfied by any one of them, because a
    # trader tags "IFVG" one day and "inverse fvg" the next and meant the same thing both
    # times. Validated into this shape in `interpret.py` - nothing the model returns reaches
    # here unchecked.
    terms = models.JSONField(null = True, blank = True)

    # **The labels that existed when the sentence was last interpreted.**
    #
    # Without it the interpretation is frozen on the day he wrote the rule, and that is the
    # worst of the three ways this can miss: he starts tagging with a new word next month,
    # the rule knows nothing about it, and **it degrades silently** - still reporting, still
    # confident, and now wrong. Comparing this with his current vocabulary is how the rule
    # knows to read itself again.
    known_labels = models.JSONField(default = list, blank = True)

    # **Switched off rather than deleted, because a rule he kept for two months and then
    # dropped is part of the story.** The debrief only checks the active ones.
    is_active = models.BooleanField(default = True)

    created_at = models.DateTimeField(auto_now_add = True)

    class Meta:
        ordering = ["kind", "id"]
        constraints = [
            # One rule per kind per trader. Two conflicting ceilings on the same thing is not
            # a stricter plan, it is a plan with no answer - and the debrief would report both.
            #
            # **Except the free-text one, which is the whole point of it.** Two ceilings on
            # size contradict each other; "only with an IFVG" and "never during news" are two
            # separate commitments that are both true at once, and a trader with a written
            # plan has several of them. The cap on how many lives in the view, not here.
            models.UniqueConstraint(fields = ["user", "kind"], name = "one_rule_per_kind",
                                    condition = ~models.Q(kind = "custom")),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.kind}"

# ------------------------- DECLARED RULES END ------------------------- #
