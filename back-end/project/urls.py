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

    path('admin/', admin.site.urls),
    path('authentication/', include('authentication.urls')),
    path('trades/', include('trades.urls')),
    path('analytics/', include('analytics.urls')),
    path('chat/', include('chat.urls')),
    path('mentor/', include('mentor.urls')),
    path('usage/', include('usage.urls')),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += staticfiles_urlpatterns()
