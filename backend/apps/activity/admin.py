from django.contrib import admin

from .models import AuditLog, RealtimeEvent


admin.site.register(AuditLog)
admin.site.register(RealtimeEvent)
