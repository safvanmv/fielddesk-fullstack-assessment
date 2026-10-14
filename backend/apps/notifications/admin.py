from django.contrib import admin

from .models import NotificationDelivery, NotificationReceipt


admin.site.register(NotificationDelivery)
admin.site.register(NotificationReceipt)