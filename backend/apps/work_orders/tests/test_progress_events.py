from unittest.mock import patch

from apps.common.testing import TenantTestCase
from apps.work_orders.models import ProgressEvent, WorkOrder


class ProgressEventTests(TenantTestCase):
    def test_event_is_idempotent_and_cross_org_denied(self):
        order = self.order(assignee=self.tech)
        self.client.force_authenticate(self.tech)
        payload = {
            "eventId": "evt-unique", "workOrderId": str(order.pk), "type": "status_changed",
            "occurredAt": "2026-08-04T10:30:00Z",
            "payload": {"status": "in_progress", "note": "Started"},
        }
        first = self.client.post("/api/progress-events/", payload, format="json")
        duplicate = self.client.post("/api/progress-events/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        order.refresh_from_db()
        self.assertEqual(order.status, WorkOrder.Status.IN_PROGRESS)
        self.assertEqual(ProgressEvent.objects.filter(event_id="evt-unique").count(), 1)
        second = self.order(organization=self.other_org, assignee=self.user("foreign-tech", self.other_org, "technician", "p"))
        payload.update(eventId="evt-cross", workOrderId=str(second.pk))
        self.assertEqual(self.client.post("/api/progress-events/", payload, format="json").status_code, 404)

    def test_event_and_order_update_roll_back_together(self):
        order = self.order(assignee=self.tech)
        self.client.force_authenticate(self.tech)
        self.client.raise_request_exception = False
        payload = {
            "eventId": "evt-rollback", "workOrderId": str(order.pk), "type": "status_changed",
            "occurredAt": "2026-08-04T10:30:00Z", "payload": {"status": "in_progress"},
        }
        with patch("apps.work_orders.services.progress_events.record_change", side_effect=RuntimeError("forced audit failure")):
            response = self.client.post("/api/progress-events/", payload, format="json")
        self.assertEqual(response.status_code, 500)
        order.refresh_from_db()
        self.assertEqual(order.status, WorkOrder.Status.OPEN)
        self.assertFalse(ProgressEvent.objects.filter(event_id="evt-rollback").exists())

    def test_status_change_note_is_kept_in_the_activity_history(self):
        order = self.order(assignee=self.tech)
        self.client.force_authenticate(self.tech)
        self.client.post("/api/progress-events/", {
            "eventId": "evt-note", "workOrderId": str(order.pk), "type": "status_changed",
            "occurredAt": "2026-08-04T10:30:00Z", "payload": {"status": "in_progress", "note": "On site"},
        }, format="json")
        activity = self.client.get(f"/api/work-orders/{order.pk}/activity/").json()
        entry = next(item for item in activity if item["action"] == "work_order.status_changed")
        self.assertEqual(entry["changes"]["note"], "On site")
        self.assertEqual(entry["changes"]["status"], {"before": "open", "after": "in_progress"})
