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

    # **Django's own login form, and nothing in this project rate-limits it.** The DRF
    # throttles cover the API; the admin is a plain Django view and every bot on the internet
    # knows to try `/admin/`. Moving it is not a lock - it is turning off the porch light, and
    # it costs one environment variable. The real lock is a host rule or an IP allowlist.
    path(os.environ.get('DJANGO_ADMIN_PATH', 'admin') + '/', admin.site.urls),
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
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += staticfiles_urlpatterns()
