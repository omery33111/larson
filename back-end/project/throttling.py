"""
The rate limits, in one file because the expensive ones are shared across three apps.

**What these are actually for.** Nothing here stops a determined attacker; a limit that low
would stop the product working. What they stop is the case that actually happens: a retry
loop in the client, a script somebody wrote against their own account, or a tab left open
re-firing a request - any of which can spend real money without anyone noticing, because
every one of the three AI endpoints is allowed up to 64k output tokens per answer.

The rates live in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` in settings, so they can be
tuned without touching code.
"""

from rest_framework.settings import api_settings
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle



class LiveRate:
    """
    Read the rate when the request arrives instead of when the module is imported.

    DRF binds `THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES` as a class attribute at
    import time, so the class keeps a reference to whichever dict existed then. Reloading the
    settings - which is what `override_settings` does - builds a *new* dict, and the class
    goes on reading the old one. **The limits are therefore untestable as DRF ships them:**
    a test that turns them on gets the value from startup, which for this project is the
    "off" one used by the suite.

    A rate of None means unlimited, which is exactly what the suite wants everywhere except
    in the tests written to prove the limits work.
    """

    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)



# ------------------------- THE ENDPOINTS THAT COST MONEY ------------------------- #
# Two windows, applied together, because one cannot cover both shapes of the problem: an
# hourly cap generous enough for a real working session still allows a slow loop to run all
# night underneath it, and a daily cap tight enough to stop that would break a heavy day.
class AIBurstThrottle(LiveRate, UserRateThrottle):
    scope = "ai"


class AIDailyThrottle(LiveRate, UserRateThrottle):
    scope = "ai-day"

    # Two throttles on one view must not share a bucket, and DRF keys the cache by scope for
    # UserRateThrottle - so these are already separate. Named here because it is the kind of
    # thing that silently collapses into one counter if a scope is ever reused.
    cache_format = "throttle_%(scope)s_%(ident)s"



# ------------------------- ANYTHING THAT SENDS MAIL ------------------------- #
# Keyed by IP rather than by user, because these are reachable without logging in - which is
# the point of them. Without a limit, "I forgot my password" is an open relay for delivering
# our mail, repeatedly, to any address the sender chooses.
class EmailThrottle(LiveRate, AnonRateThrottle):
    scope = "email"



# ------------------------- THE FRONT DOOR ------------------------- #
class LoginThrottle(LiveRate, AnonRateThrottle):
    scope = "login"


class RegisterThrottle(LiveRate, AnonRateThrottle):
    scope = "register"
