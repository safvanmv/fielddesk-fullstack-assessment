import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.activity.models import AuditLog
from apps.work_orders.models import WorkOrder

from .models import NotificationDelivery
from .providers import PermanentProviderError, TemporaryProviderError, mock_notify

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=4, name="fielddesk.notify_technician")
def notify_technician(self, work_order_id):
    order = WorkOrder.objects.select_related("organization", "assigned_technician").filter(pk=work_order_id).first()
    if not order or not order.assigned_technician_id:
        logger.warning("notification skipped: order missing or unassigned", extra={"work_order_id": work_order_id})
        return "skipped"
    revision = order.assignment_revision
    with transaction.atomic():
        delivery, _ = NotificationDelivery.objects.get_or_create(
            work_order=order,
            assignment_revision=revision,
            defaults={
                "organization": order.organization,
                "technician": order.assigned_technician,
            },
        )
        delivery = NotificationDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.outcome in (NotificationDelivery.Outcome.SENT, NotificationDelivery.Outcome.FAILED):
            return delivery.outcome
        if (
            delivery.outcome == NotificationDelivery.Outcome.PROCESSING
            and delivery.updated_at > timezone.now() - timedelta(minutes=10)
        ):
            return "already_processing"
        delivery.attempts += 1
        delivery.outcome = NotificationDelivery.Outcome.PROCESSING
        delivery.save(update_fields=["attempts", "outcome", "updated_at"])
    key = f"{order.pk}:{revision}"
    try:
        mock_notify(order.assigned_technician, order, key)
    except PermanentProviderError as exc:
        outcome = NotificationDelivery.Outcome.FAILED
        error = str(exc)
    except TemporaryProviderError as exc:
        error = str(exc)
        if self.request.retries >= self.max_retries:
            outcome = NotificationDelivery.Outcome.FAILED
        else:
            NotificationDelivery.objects.filter(pk=delivery.pk).update(
                outcome=NotificationDelivery.Outcome.PENDING, last_error=error
            )
            AuditLog.objects.create(
                organization=order.organization, actor=None, action="notification.retrying",
                target_type="WorkOrder", target_id=str(order.pk),
                changes={"attempt": delivery.attempts, "error": error},
            )
            raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
    else:
        outcome = NotificationDelivery.Outcome.SENT
        error = ""
    NotificationDelivery.objects.filter(pk=delivery.pk).update(outcome=outcome, last_error=error)
    AuditLog.objects.create(
        organization=order.organization,
        actor=None,
        action="notification." + ("sent" if outcome == NotificationDelivery.Outcome.SENT else "failed"),
        target_type="WorkOrder",
        target_id=str(order.pk),
        changes={"attempts": delivery.attempts, "outcome": outcome, "error": error},
    )
    logger.info("notification finished", extra={"work_order_id": str(order.pk), "outcome": outcome, "attempts": delivery.attempts})
    return outcome
