from django.contrib import admin
from django.urls import include, path

api_patterns = [
    path("", include("apps.common.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.work_orders.urls")),
    path("", include("apps.activity.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]
