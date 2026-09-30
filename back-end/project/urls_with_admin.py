"""
The URL map with the admin mounted, used by the tests of the allowlist middleware.

**The project no longer mounts the admin in production at all** - see the note in `urls.py`.
These tests are about whether the lock works, not about whether the door is hung, so they need
a map where the door exists.
"""

from django.contrib import admin
from django.urls import path

from .urls import urlpatterns as base


urlpatterns = base + [path('admin/', admin.site.urls)]
