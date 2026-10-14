from unittest.mock import patch

from django.db import OperationalError
from psycopg.errors import DeadlockDetected

from apps.activity.models import AuditLog
from apps.activity.services import record_change
from apps.common.testing import TenantTestCase
from apps.work_orders.models import WorkOrder
from apps.work_orders.services import work_orders as services

SERVICE = "apps.work_orders.services.work_orders"
WINDOW = {"scheduled_start": "2026-08-04T10:00:00Z", "scheduled_end": "2026-08-04T11:00:00Z"}


def deadlock():
    """The error Django raises when PostgreSQL picks this transaction as a deadlock victim."""
    error = OperationalError("deadlock detected")
    error.__cause__ = DeadlockDetected("deadlock detected")
    return error


def deadlock_once(real):
    """Run ``real`` and then fail as a deadlock victim on the first call only, so its writes must roll back."""
    calls = []

    def wrapper(*args, **kwargs):
        calls.append(1)
        result = real(*args, **kwargs)
        if len(calls) == 1:
            raise deadlock()
        return result
    return wrapper


class DeadlockRetryTests(TenantTestCase):
    def test_deadlocked_create_is_retried_without_leaving_partial_writes(self):
        self.client.force_authenticate(self.dispatcher)
        with patch(f"{SERVICE}.record_change", side_effect=deadlock_once(record_change)):
            response = self.client.post("/api/work-orders/", {"title": "Retried job", "site_name": "Plant"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(WorkOrder.objects.filter(title="Retried job").count(), 1)
        self.assertEqual(AuditLog.objects.filter(action="work_order.created").count(), 1)

    def test_deadlock_victim_with_an_overlap_gets_a_conflict(self):
        self.order(assignee=self.tech, **WINDOW)
        self.client.force_authenticate(self.dispatcher)
        real_insert = services._insert_with_unique_reference
        calls = []

        def victim_then_real(**fields):
            calls.append(1)
            if len(calls) == 1:
                raise deadlock()
            return real_insert(**fields)

        with patch(f"{SERVICE}._insert_with_unique_reference", side_effect=victim_then_real):
            response = self.client.post("/api/work-orders/", {
                "title": "Overlapping job", "site_name": "Plant", "assigned_technician": self.tech.pk, **WINDOW,
            }, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(calls), 2)
        self.assertFalse(WorkOrder.objects.filter(title="Overlapping job").exists())

    def test_deadlocked_reassignment_bumps_the_revision_once(self):
        order = self.order()
        self.client.force_authenticate(self.dispatcher)
        with patch(f"{SERVICE}.record_change", side_effect=deadlock_once(record_change)):
            response = self.client.patch(f"/api/work-orders/{order.pk}/", {"assigned_technician": self.tech.pk}, format="json")
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.assigned_technician_id, self.tech.pk)
        self.assertEqual(order.assignment_revision, 1)
        self.assertEqual(AuditLog.objects.filter(action="work_order.updated").count(), 1)

    def test_repeated_deadlocks_are_not_retried_forever(self):
        self.client.force_authenticate(self.dispatcher)
        self.client.raise_request_exception = False

        def always_deadlock(**fields):
            raise deadlock()

        with patch(f"{SERVICE}._insert_with_unique_reference", side_effect=always_deadlock) as insert:
            response = self.client.post("/api/work-orders/", {"title": "Job", "site_name": "Plant"}, format="json")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(insert.call_count, services.DEADLOCK_ATTEMPTS)
