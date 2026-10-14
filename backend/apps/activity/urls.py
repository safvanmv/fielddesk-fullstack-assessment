from django.urls import path

from .views import AuditListView, EventStreamView, WorkOrderActivityView

urlpatterns = [
    path("events/stream/", EventStreamView.as_view(), name="event-stream"),
    path("stream/", EventStreamView.as_view(), name="event-stream-legacy"),
    path("audit/", AuditListView.as_view(), name="audit"),
    path("work-orders/<uuid:work_order_id>/activity/", WorkOrderActivityView.as_view(), name="work-order-activity"),
]
