from datetime import timedelta

from django.core import signing
from django.utils import timezone

from analytics.formatting import money, percent, trades as trade_count
from analytics.insights import build_insights
from analytics.statistics import compute_statistics

from trades.models import Trade

from .models import EmailPreference



# ------------------------- THE WEEKLY DIGEST START ------------------------- #
#
# **The whole feature is the decision not to send.**
#
# A weekly email that says "you have not updated Larson" gets unsubscribed, and then it does
# something worse: a spam complaint lands on the sending domain, and that is the **same
# domain that carries the verification and password-reset mail.** A nagging digest can break
# account recovery for people who never received it. So the rule is narrow and enforced here
# rather than left to judgement:
#
#   he added trades this week      -> a real summary of them, which is worth opening
#   he did not, and it is recent   -> **silence**
#   he did not, and it has been a while -> **one** reminder, once, not one a week
#
# The third case is the one that needs state, which is why `EmailPreference` carries two
# timestamps. Without them the command cannot tell a quiet week from a quiet month.
#
# **And what it sends is a summary and not a nudge**, because those are different products
# wearing the same envelope. "Here is your week" earns the open; "come back" spends it.


# How long a silence has to run before it is worth one mention. Shorter than this is a trader
# who simply had a quiet week, and a mentor who comments on that is a mentor who comments on
# everything.
NUDGE_AFTER_DAYS = 14

# The digest covers the week; a second one inside it would be the same week twice.
MIN_DAYS_BETWEEN_DIGESTS = 5

WINDOW_DAYS = 7

UNSUBSCRIBE_SALT = "larson.email.unsubscribe"

# Six months, because the link has to work in the last email he kept - not only in the newest
# one. A link that expires is a link that sends him looking for the spam button instead.
UNSUBSCRIBE_MAX_AGE = 60 * 60 * 24 * 180



def unsubscribe_token(user):
    """Signed, stateless, and good for months.

    Nothing is stored: the token is a signed statement of which account it belongs to, in the
    same spirit as the verification links - **no table of open tokens to leak or to clean.**
    """
    return signing.dumps({"user": user.pk}, salt = UNSUBSCRIBE_SALT)


def user_id_from_token(token):
    """The account a token names, or None. Never raises - this is reached without a login."""
    try:
        payload = signing.loads(token, salt = UNSUBSCRIBE_SALT, max_age = UNSUBSCRIBE_MAX_AGE)
    except signing.BadSignature:
        return None

    return payload.get("user") if isinstance(payload, dict) else None



def decide(user, now = None):
    """
    What this trader should receive this week, if anything.

    Returns `(kind, payload)` where kind is "digest", "nudge" or "silence". **The silence case
    carries its reason**, because a command that sends nothing and says nothing is a command
    nobody can tell is working.
    """
    now = now or timezone.now()

    prefs, _ = EmailPreference.objects.get_or_create(user = user)

    if not prefs.weekly_digest:
        return "silence", {"reason": "הסוחר ביטל את ההרשמה לסיכום."}

    if not user.email or not user.is_active:
        return "silence", {"reason": "אין כתובת מאומתת."}

    window_start = now - timedelta(days = WINDOW_DAYS)

    # **What arrived in the resume this week**, not what he traded this week - those are
    # different questions, and only the first one is knowable from here. A trader who traded
    # and did not tell Larson is exactly the case the reminder exists for.
    fresh = list(Trade.objects.filter(user = user, created_at__gte = window_start))

    if fresh:
        if (prefs.last_digest_at
                and now - prefs.last_digest_at < timedelta(days = MIN_DAYS_BETWEEN_DIGESTS)):
            return "silence", {"reason": "סיכום נשלח כבר השבוע."}

        return "digest", _summary(user, fresh, now)

    # Nothing new. How long has it been?
    latest = (Trade.objects.filter(user = user).order_by("-created_at")
                           .values_list("created_at", flat = True).first())

    if not latest:
        return "silence", {"reason": "הרזומה ריקה — אין על מה לדווח ואין על מה להזכיר."}

    gap = (now - latest).days

    if gap < NUDGE_AFTER_DAYS:
        return "silence", {"reason": f"רק {gap} ימים מהעדכון האחרון — זה שבוע שקט, לא פער."}

    # **Once per silence, not once a week.** A reminder already sent since the last update is
    # the whole reason this stamp exists.
    if prefs.last_nudge_at and prefs.last_nudge_at > latest:
        return "silence", {"reason": "כבר נשלחה תזכורת אחת על הפער הזה."}

    return "nudge", {"days": gap}



def _summary(user, fresh, now):
    """The week itself, computed here and only narrated by the template.

    Two figures and the sharpest finding. **A digest that reproduces the whole ID page is a
    page sent by email**, and the trader already has the page - what an email can do that a
    page cannot is arrive.
    """
    statistics = compute_statistics(fresh)
    currency = statistics.get("currency", "USD")

    core = statistics.get("core", {})
    _, leaks = build_insights(statistics, fresh)

    payload = {
        "trades": len(fresh),
        "net_pnl": money(core.get("net_pnl", 0), currency),
        "win_rate": percent(core.get("win_rate", 0)),
        "count_text": trade_count(len(fresh)),
    }

    if leaks:
        leak = leaks[0]
        payload["leak_title"] = leak["title"]
        payload["leak_detail"] = leak["detail"]
        # The named instance, which is the whole difference between a report and a mentor.
        if leak.get("examples"):
            payload["leak_example"] = leak["examples"][0]

    return payload



def mark_sent(user, kind, now = None):
    """Record what went out, so next week can tell a quiet week from a quiet month."""
    now = now or timezone.now()
    prefs, _ = EmailPreference.objects.get_or_create(user = user)

    if kind == "digest":
        prefs.last_digest_at = now
        prefs.save(update_fields = ["last_digest_at"])
    elif kind == "nudge":
        prefs.last_nudge_at = now
        prefs.save(update_fields = ["last_nudge_at"])

# ------------------------- THE WEEKLY DIGEST END ------------------------- #
