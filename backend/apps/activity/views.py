import json
import time

from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.http import StreamingHttpResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Membership
from apps.accounts.permissions import HasMembership, membership_for
from apps.work_orders.models import Attachment
from apps.work_orders.selectors import scoped_orders

from .models import AuditLog, RealtimeEvent
from .renderers import EventStreamRenderer


class WorkOrderActivityView(APIView):
    permission_classes = [HasMembership]

    def get(self, request, work_order_id):
        order = scoped_orders(request).filter(pk=work_order_id).first()
        if not order:
            return Response({"detail": "Not found."}, status=404)
        attachment_ids = Attachment.objects.filter(work_order=order).annotate(
            id_string=Cast("pk", output_field=CharField())
        ).values_list("id_string", flat=True)
        records = AuditLog.objects.filter(organization=order.organization).filter(
            Q(target_type="WorkOrder", target_id=str(order.pk))
            | Q(target_type="Attachment", target_id__in=attachment_ids)
        ).select_related("actor")
        return Response([{
            "id": item.pk,
            "action": item.action,
            "actor": item.actor.get_username() if item.actor else None,
            "changes": item.changes,
            "created_at": item.created_at,
        } for item in records])


class AuditListView(APIView):
    permission_classes = [HasMembership]

    def get(self, request):
        orders = scoped_orders(request)
        order_ids = orders.annotate(id_string=Cast("pk", output_field=CharField())).values_list("id_string", flat=True)
        attachment_ids = Attachment.objects.filter(work_order__in=orders).annotate(
            id_string=Cast("pk", output_field=CharField())
        ).values_list("id_string", flat=True)
        membership = membership_for(request.user)
        records = AuditLog.objects.filter(organization=membership.organization).filter(
            Q(target_type="WorkOrder", target_id__in=order_ids)
            | Q(target_type="Attachment", target_id__in=attachment_ids)
        )
        if membership.role == Membership.Role.OWNER:
            records = AuditLog.objects.filter(organization=membership.organization).filter(
                Q(target_type="WorkOrder", target_id__in=order_ids)
                | Q(target_type="Attachment", target_id__in=attachment_ids)
                | Q(target_type="Membership")
                | Q(target_type="Organization", target_id=str(membership.organization_id))
            )
        work_order_id = request.query_params.get("work_order")
        if work_order_id:
            order = orders.filter(pk=work_order_id).first()
            if not order:
                return Response({"detail": "Not found."}, status=404)
            attachment_ids = Attachment.objects.filter(work_order=order).annotate(
                id_string=Cast("pk", output_field=CharField())
            ).values_list("id_string", flat=True)
            records = records.filter(
                Q(target_type="WorkOrder", target_id=str(order.pk))
                | Q(target_type="Attachment", target_id__in=attachment_ids)
            )
        try:
            limit = min(100, max(1, int(request.query_params.get("limit", "50"))))
        except ValueError:
            limit = 50
        records = records.select_related("actor").order_by("-created_at", "-pk")[:limit]
        return Response([{
            "id": item.pk,
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "actor": item.actor.get_username() if item.actor else None,
            "changes": item.changes,
            "created_at": item.created_at,
        } for item in records])


class EventStreamView(APIView):
    permission_classes = [HasMembership]
    # Browsers' EventSource sends Accept: text/event-stream; JSON stays first for other clients.
    renderer_classes = [JSONRenderer, EventStreamRenderer]

    def get(self, request):
        organization_id = membership_for(request.user).organization_id
        try:
            cursor = max(0, int(request.headers.get("Last-Event-ID", "0")))
        except ValueError:
            cursor = 0

        def stream():
            nonlocal cursor
            for _ in range(25):
                batch = list(RealtimeEvent.objects.filter(
                    organization_id=organization_id, id__gt=cursor
                ).order_by("id")[:100])
                if batch:
                    for item in batch:
                        cursor = item.pk
                        yield f"id: {item.pk}\nevent: {item.event_type}\ndata: {json.dumps(item.data, separators=(',', ':'))}\n\n"
                else:
                    yield ": keep-alive\n\n"
                time.sleep(1)

        response = StreamingHttpResponse(stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
