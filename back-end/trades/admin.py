from django.contrib import admin

from .models import Trade, TradeFile


admin.site.register(TradeFile)
admin.site.register(Trade)
