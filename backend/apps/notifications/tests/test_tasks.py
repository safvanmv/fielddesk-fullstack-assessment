from django.test import override_settings

from apps.common.testing import TenantTestCase
from apps.notifications.models import NotificationDelivery
from apps.notifications.tasks import notify_technician


class NotificationTaskTests(TenantTestCase):
    def test_notification_success_is_deduplicated_and_permanent_failure_is_terminal(self):
        order = self.order(assignee=self.tech)
        with override_settings(NOTIFICATION_PROVIDER_MODE="success"):
            first = notify_technician.apply(args=[str(order.pk)]).get()
            second = notify_technician.apply(args=[str(order.pk)]).get()
        self.assertEqual(first, "sent")
        self.assertEqual(second, "sent")
        self.assertEqual(NotificationDelivery.objects.filter(work_order=order).count(), 1)
        self.assertEqual(order.notificationreceipt_set.count(), 1)
        order.assignment_revision += 1
        order.save(update_fields=["assignment_revision"])
        with override_settings(NOTIFICATION_PROVIDER_MODE="permanent"):
            failed = notify_technician.apply(args=[str(order.pk)]).get()
            retry = notify_technician.apply(args=[str(order.pk)]).get()
        self.assertEqual(failed, "failed")
        self.assertEqual(retry, "failed")
        self.assertEqual(NotificationDelivery.objects.get(work_order=order, assignment_revision=1).attempts, 1)

    def test_notification_retries_temporary_provider_failure(self):
        order = self.order(assignee=self.tech)
        with override_settings(NOTIFICATION_PROVIDER_MODE="temporary"):
            result = notify_technician.apply(args=[str(order.pk)]).get()
        delivery = NotificationDelivery.objects.get(work_order=order)
        self.assertEqual(result, "failed")
        self.assertEqual(delivery.outcome, NotificationDelivery.Outcome.FAILED)
        self.assertEqual(delivery.attempts, notify_technician.max_retries + 1)
