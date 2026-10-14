from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AttachmentDownloadView,
    AttachmentView,
    DashboardView,
    ProgressEventView,
    WorkOrderExportView,
    WorkOrderViewSet,
)

router = SimpleRouter()
router.register("work-orders", WorkOrderViewSet, basename="work-order")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("progress-events/", ProgressEventView.as_view(), name="progress-events"),
    path("events/", ProgressEventView.as_view(), name="progress-events-legacy"),
    path("reports/work-orders.csv", WorkOrderExportView.as_view(), name="work-order-export"),
    path("work-orders/export.csv", WorkOrderExportView.as_view(), name="work-order-export-legacy"),
    path("work-orders/<uuid:work_order_id>/attachments/", AttachmentView.as_view(), name="attachment-upload"),
    path("attachments/<int:attachment_id>/download/", AttachmentDownloadView.as_view(), name="attachment-download"),
    path("", include(router.urls)),
]
