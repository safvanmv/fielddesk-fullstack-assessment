from django.db.models import Count
from django.http import FileResponse, StreamingHttpResponse
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasMembership, membership_for

from .export import csv_rows
from .models import Attachment
from .permissions import WorkOrderRolePermission
from .selectors import scoped_orders
from .serializers import AttachmentSerializer, ProgressEventSerializer, WorkOrderSerializer
from .services.attachments import AttachmentRejected, add_attachment
from .services.progress_events import WorkOrderNotAssigned, submit_progress_event
from .services.work_orders import ScheduleConflict, create_work_order, update_work_order
from .throttles import EventRateThrottle

SCHEDULE_CONFLICT_DETAIL = "Technician already has a work order in this time window."


class WorkOrderViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderSerializer
    permission_classes = [WorkOrderRolePermission]
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_queryset(self):
        return scoped_orders(self.request)

    def paginate(self, queryset):
        try:
            page = max(1, int(self.request.query_params.get("page", "1")))
            page_size = min(100, max(1, int(self.request.query_params.get("page_size", "25"))))
        except ValueError:
            page, page_size = 1, 25
        count = queryset.count()
        items = queryset[(page - 1) * page_size: page * page_size]
        return {
            "count": count,
            "page": page,
            "page_size": page_size,
            "results": self.get_serializer(items, many=True).data,
        }

    def list(self, request, *args, **kwargs):
        return Response(self.paginate(self.filter_queryset(self.get_queryset())))

    def perform_create(self, serializer):
        serializer.instance = create_work_order(
            organization=membership_for(self.request.user).organization,
            user=self.request.user,
            data=serializer.validated_data,
        )

    def perform_update(self, serializer):
        serializer.instance = update_work_order(
            order=serializer.instance, user=self.request.user, data=serializer.validated_data,
        )

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ScheduleConflict:
            return Response({"detail": SCHEDULE_CONFLICT_DETAIL}, status=409)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except ScheduleConflict:
            return Response({"detail": SCHEDULE_CONFLICT_DETAIL}, status=409)


class DashboardView(APIView):
    permission_classes = [HasMembership]

    def get(self, request):
        orders = scoped_orders(request)
        grouped = {row["status"]: row["count"] for row in orders.values("status").annotate(count=Count("id"))}
        return Response({"total": sum(grouped.values()), "by_status": grouped})


class ProgressEventView(APIView):
    permission_classes = [HasMembership]
    throttle_classes = [EventRateThrottle]

    def post(self, request):
        serializer = ProgressEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            event, duplicate = submit_progress_event(
                user=request.user,
                organization=membership_for(request.user).organization,
                event=serializer.validated_data,
            )
        except WorkOrderNotAssigned:
            return Response({"detail": "Work order not found or not assigned to you."}, status=404)
        return Response({"eventId": event.event_id, "duplicate": duplicate}, status=200 if duplicate else 201)


class WorkOrderExportView(APIView):
    permission_classes = [HasMembership]

    def get(self, request):
        response = StreamingHttpResponse(csv_rows(scoped_orders(request)), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="work-orders.csv"'
        return response


class AttachmentView(APIView):
    permission_classes = [HasMembership]

    def post(self, request, work_order_id):
        membership = membership_for(request.user)
        order = scoped_orders(request).filter(pk=work_order_id).first()
        if not order:
            return Response({"detail": "Not found."}, status=404)
        if membership.role == "technician":
            return Response({"detail": "You do not have permission to upload attachments."}, status=403)
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "A file is required."}, status=400)
        try:
            attachment = add_attachment(
                organization_id=membership.organization_id, order=order, user=request.user, uploaded=uploaded,
            )
        except AttachmentRejected as exc:
            return Response({"detail": exc.detail}, status=exc.status)
        return Response(AttachmentSerializer(attachment).data, status=201)


class AttachmentDownloadView(APIView):
    permission_classes = [HasMembership]

    def get(self, request, attachment_id):
        attachment = Attachment.objects.filter(
            pk=attachment_id, organization=membership_for(request.user).organization
        ).first()
        if not attachment:
            return Response({"detail": "Not found."}, status=404)
        if membership_for(request.user).role == "technician" and attachment.work_order.assigned_technician_id != request.user.pk:
            return Response({"detail": "Not found."}, status=404)
        return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.original_name,
                            content_type=attachment.content_type)
