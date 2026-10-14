import logging

from django.conf import settings

from .models import NotificationReceipt

logger = logging.getLogger(__name__)


class TemporaryProviderError(Exception):
    pass


class PermanentProviderError(Exception):
    pass


def mock_notify(technician, order, idempotency_key):
    mode = settings.NOTIFICATION_PROVIDER_MODE
    if mode == "temporary":
        raise TemporaryProviderError("Mock provider temporary failure.")
    if mode == "permanent":
        raise PermanentProviderError("Mock provider permanently rejected the notification.")
    receipt, created = NotificationReceipt.objects.get_or_create(
        idempotency_key=idempotency_key, defaults={"work_order": order}
    )
    logger.info(
        "mock notification accepted" if created else "mock notification duplicate suppressed",
        extra={"notification_key": receipt.idempotency_key, "technician": technician.pk},
    )
