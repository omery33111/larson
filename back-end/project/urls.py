import os

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns



# **What a host pings to decide whether this instance is alive.** It has to touch nothing -
# no database, no model, no authentication - because a health check that can fail for a second
# reason tells the host to restart a server that was fine.
def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path('healthz/', health),

    path('authentication/', include('authentication.urls')),
    path('trades/', include('trades.urls')),
    path('analytics/', include('analytics.urls')),
    path('chat/', include('chat.urls')),
    path('mentor/', include('mentor.urls')),
    path('usage/', include('usage.urls')),
]


# **Media is deliberately not served, at any setting.** `static()` is inert once DEBUG is
# off, so this was only ever a development route - but in development it answered
# `/media/trade_files/<name>` for anybody at all, with no token and no owner check, and the
# names are the ones the traders' own computers gave the files. Nothing in the product ever
# linked to it: the export screen fetches through an authenticated request and always did.
# **The admin is off unless something explicitly asks for it, and in production nothing does.**
#
# It is Django's own login form, and nothing in this project rate-limits it: the DRF throttles
# cover the API, while the admin is a plain Django view that every bot on the internet knows to
# try. Moving its path is turning off the porch light, not a lock.
#
# **What was tried instead and rejected: an allowlist of IP addresses.** It reads as the strong
# answer and is the fragile one for a single operator - a home connection whose address changes,
# a router somebody else reconfigures, a change of provider nobody announces, and the lock has
# locked out the only person who holds the key, on the one day he needed it.
#
# **Off is stronger than guarded, and it costs nothing here**, because every day-to-day thing
# lives in the product's own screens. When it is genuinely needed it comes back for as long as
# it is needed, by setting one variable and taking it away afterwards - a door that is opened
# deliberately and closed again, instead of one that stands ajar behind a rule.
if settings.DEBUG or os.environ.get('DJANGO_ADMIN_ENABLED') == '1':
    urlpatterns.append(
        path(os.environ.get('DJANGO_ADMIN_PATH', 'admin') + '/', admin.site.urls))


urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += staticfiles_urlpatterns()
