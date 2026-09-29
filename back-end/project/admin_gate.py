"""
Who may even see the admin login form.

**Nothing in this project rate-limits it.** The DRF throttles cover the API; the Django admin
is a plain Django view with a session cookie, and every bot on the internet tries `/admin/`.
Moving the path with `DJANGO_ADMIN_PATH` turns off the porch light. This is the lock.

Off unless `DJANGO_ADMIN_ALLOWED_IPS` is set, because a lock that arrives switched on is a
lock that locks the owner out on the first deploy. With a list, anything else gets a 404 -
not a 403, which would confirm that there is something there to find.
"""

import os

from django.http import Http404



def _allowed():
    raw = os.environ.get('DJANGO_ADMIN_ALLOWED_IPS', '')
    return [part.strip() for part in raw.split(',') if part.strip()]


def _caller(request, proxies):
    """
    The address to judge, counted back past the proxies we know are in front.

    **The same reasoning as the rate limits**, and the same trap: `X-Forwarded-For` is written
    by the caller, so trusting the whole of it would let anyone claim to be on the list. With
    no proxy, the socket address is the only thing that cannot be forged.
    """
    if proxies <= 0:
        return request.META.get('REMOTE_ADDR', '')

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')

    if not forwarded:
        return request.META.get('REMOTE_ADDR', '')

    addresses = [part.strip() for part in forwarded.split(',')]

    return addresses[-min(proxies, len(addresses))]


class AdminAllowlist:
    """Sits above everything, so a refused caller never reaches a session or a form."""

    def __init__(self, get_response):
        self.get_response = get_response

        self.allowed = _allowed()
        self.prefix = '/' + os.environ.get('DJANGO_ADMIN_PATH', 'admin') + '/'
        self.proxies = int(os.environ.get('TRUSTED_PROXY_COUNT', '0'))

    def __call__(self, request):
        if self.allowed and request.path.startswith(self.prefix):
            if _caller(request, self.proxies) not in self.allowed:
                raise Http404

        return self.get_response(request)
