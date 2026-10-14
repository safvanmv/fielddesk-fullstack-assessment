from django.db import IntegrityError, transaction

from apps.activity.services import record_change

from ..models import ProgressEvent, WorkOrder


class WorkOrderNotAssigned(Exception):
    """The work order does not exist in the caller's organization or is not assigned to them."""


def submit_progress_event(*, user, organization, event):
    """Apply a validated progress event exactly once.

    Transaction boundary: the work-order row lock, the event insert, the status update and the
    audit/realtime rows commit or roll back together. The unique (organization, event_id) constraint
    makes a concurrent or repeated submission fail its insert, and it is then reported as a duplicate.

    Returns ``(progress_event, duplicate)``.
    """
    try:
        with transaction.atomic():
            order = WorkOrder.objects.select_for_update().filter(
                pk=event["workOrderId"], organization=organization, assigned_technician=user,
            ).first()
            if order is None:
                raise WorkOrderNotAssigned
            accepted = ProgressEvent.objects.create(
                organization=organization, event_id=event["eventId"],
                work_order=order, actor=user, event_type=event["type"],
                occurred_at=event["occurredAt"], payload=event["payload"],
            )
            if event["type"] == "status_changed":
                before = order.status
                order.status = event["payload"]["status"]
                order.save(update_fields=["status", "updated_at"])
                changes = {"status": {"before": before, "after": order.status}, "event_id": accepted.event_id}
                if event["payload"].get("note"):
                    changes["note"] = event["payload"]["note"]
                record_change(organization, user, "work_order.status_changed", order, changes)
            else:
                record_change(organization, user, "work_order.note_added", order,
                              {"note": event["payload"]["note"], "event_id": accepted.event_id})
        return accepted, False
    except IntegrityError:
        existing = ProgressEvent.objects.filter(organization=organization, event_id=event["eventId"]).first()
        if existing:
            return existing, True
        raise
