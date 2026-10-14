from django.contrib import admin

from .models import Attachment, ProgressEvent, WorkOrder

admin.site.register(WorkOrder)
admin.site.register(Attachment)
admin.site.register(ProgressEvent)