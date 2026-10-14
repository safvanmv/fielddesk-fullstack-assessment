from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Organization
from apps.work_orders.models import ProgressEvent, WorkOrder

User = get_user_model()


def closing_connection(fn):
    """Run ``fn`` on a worker thread and always close that thread's database connection.

    close_old_connections() keeps a connection younger than CONN_MAX_AGE open, and a leaked
    thread connection stops the test runner from dropping the test database at teardown.
    """
    def run(*args):
        try:
            return fn(*args)
        finally:
            connection.close()
    return run


class ScheduleConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.org = Organization.objects.create(name="Schedule Org")
        self.dispatcher = User.objects.create_user(username="dispatcher", password="password")
        self.tech = User.objects.create_user(username="technician", password="password")
        Membership.objects.create(user=self.dispatcher, organization=self.org, role="dispatcher")
        Membership.objects.create(user=self.tech, organization=self.org, role="technician")

    def test_simultaneous_overlapping_assignments_return_one_conflict(self):
        barrier = Barrier(2)
        def create(title):
            client = APIClient()
            client.force_authenticate(self.dispatcher)
            barrier.wait(timeout=10)
            response = client.post("/api/work-orders/", {
                "title": title,
                "site_name": "Plant",
                "assigned_technician": self.tech.pk,
                "scheduled_start": "2026-08-04T10:00:00Z",
                "scheduled_end": "2026-08-04T11:00:00Z",
            }, format="json")
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(closing_connection(create), ["Job C1", "Job C2"]))
        self.assertCountEqual(results, [201, 409])
        self.assertEqual(WorkOrder.objects.count(), 1)

    def test_simultaneous_creates_drawing_the_same_reference_both_succeed(self):
        # Both requests draw the same reference first, so exactly one of them collides on the
        # unique constraint (possibly while blocked on the other's uncommitted insert) and retries.
        references = iter(["FD-SAMEREF2", "FD-SAMEREF2", "FD-RETRY234", "FD-RETRY567"])
        draw_lock = Lock()

        def draw_reference():
            with draw_lock:
                return next(references)

        barrier = Barrier(2)

        def create(title):
            client = APIClient()
            client.force_authenticate(self.dispatcher)
            barrier.wait(timeout=10)
            response = client.post("/api/work-orders/", {"title": title, "site_name": "Plant"}, format="json")
            return response.status_code, response.json().get("reference")

        with patch("apps.work_orders.services.work_orders.generate_reference", side_effect=draw_reference):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(closing_connection(create), ["Job A", "Job B"]))
        self.assertEqual([status for status, _ in results], [201, 201])
        assigned = {reference for _, reference in results}
        self.assertEqual(assigned, {"FD-SAMEREF2", "FD-RETRY234"})
        self.assertCountEqual(WorkOrder.objects.values_list("reference", flat=True), assigned)

    def test_simultaneous_duplicate_progress_event_is_applied_once(self):
        order = WorkOrder.objects.create(
            organization=self.org, reference="FD-EVENT", title="Event race", site_name="Plant",
            created_by=self.dispatcher, assigned_technician=self.tech,
        )
        barrier = Barrier(2)

        def submit(_):
            client = APIClient()
            client.force_authenticate(self.tech)
            barrier.wait(timeout=10)
            response = client.post("/api/progress-events/", {
                "eventId": "evt-race", "workOrderId": str(order.pk), "type": "status_changed",
                "occurredAt": "2026-08-04T10:30:00Z", "payload": {"status": "in_progress"},
            }, format="json")
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(closing_connection(submit), range(2)))
        self.assertCountEqual(results, [201, 200])
        self.assertEqual(ProgressEvent.objects.filter(organization=self.org, event_id="evt-race").count(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, WorkOrder.Status.IN_PROGRESS)
