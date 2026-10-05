import logging



# ------------------------- WHAT THE TRADER IS TOLD WHEN IT BREAKS ------------------------- #
#
# **Larson is Larson. The user never learns which model answers for him, and these messages
# are where that leaked.**
#
# Three of them named Claude outright, two told the trader to run `pip install anthropic`,
# and two gave him a path inside the repository and told him to restart a server he does
# not have. Every one of those is a fault only the operator can fix, so the detail reached
# the one person who could do nothing with it.
#
# That is not only a branding problem, which is how it was reported. **A product whose error
# message names the model it resells invites exactly one thought - "so I am paying for a
# wrapper"** - and it arrives at the worst possible moment, when something has just failed.
# It is also the same rule the security review already applied to the SDK's own exception
# text: what the trader sees is what he can act on, and the rest goes to the log.
#
# **The single exception is the privacy policy**, which names Anthropic on purpose and must
# keep doing so. It exists to disclose who processes his trading record; a policy that hides
# the processor is not a policy. The distinction is honest and worth keeping straight:
# **the service has a name he is entitled to know, and the error message is not where he
# learns it.**

log = logging.getLogger(__name__)


# One sentence, no cause, nothing to act on - because there is nothing he can do about any
# of these. They differ only in whether trying again is worth his time.
NOT_CONFIGURED = "לארסון לא זמין כרגע. אנחנו כבר יודעים על זה ומטפלים."

CALL_FAILED = "לארסון לא הצליח לענות כרגע. נסה שוב בעוד רגע."


def configuration_fault(detail):
    """
    Log what actually went wrong, hand back what the trader should read.

    **Called at every point where a missing key or a missing package would otherwise have
    been described to him.** The operator needs "ANTHROPIC_API_KEY is empty" and gets it in
    the log; the trader needs to know it is not his fault and that somebody is on it.
    """
    log.error("Larson is not configured: %s", detail)

    return NOT_CONFIGURED

# ------------------------- END ------------------------- #
