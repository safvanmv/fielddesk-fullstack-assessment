import re
from unittest.mock import patch

from apps.common.testing import TenantTestCase
from apps.work_orders.models import WorkOrder
from apps.work_orders.services.work_orders import REFERENCE_ATTEMPTS

REFERENCE_PATTERN = re.compile(r"^FD-[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8}$")
GENERATE_REFERENCE = "apps.work_orders.services.work_orders.generate_reference"


class WorkOrderAPITests(TenantTestCase):
    def test_role_and_tenant_boundaries_are_enforced(self):
        order = self.order()
        self.client.force_authenticate(self.tech)
        self.assertEqual(self.client.post("/api/work-orders/", {}).status_code, 403)
        self.assertEqual(self.client.get(f"/api/work-orders/{order.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/members/").status_code, 403)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/work-orders/{order.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/work-orders/").json()["count"], 0)

    def test_work_order_validation_and_list_search(self):
        self.client.force_authenticate(self.dispatcher)
        invalid = self.client.post("/api/work-orders/", {
            "title": "Bad schedule", "site_name": "Plant",
            "scheduled_start": "2026-08-04T12:00:00Z", "scheduled_end": "2026-08-04T11:00:00Z",
        }, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.order(title="Pump repair")
        response = self.client.get("/api/work-orders/?search=pump&page=1&page_size=5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_server_assigns_reference_and_ignores_client_value(self):
        existing = self.order(reference="FD-100")
        self.client.force_authenticate(self.dispatcher)
        created = self.client.post("/api/work-orders/", {
            "reference": existing.reference, "title": "New job", "site_name": "Plant",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        reference = created.json()["reference"]
        self.assertRegex(reference, REFERENCE_PATTERN)
        renamed = self.client.patch(f"/api/work-orders/{created.json()['id']}/", {"reference": "CHANGED"}, format="json")
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["reference"], reference)
        self.assertEqual(WorkOrder.objects.get(pk=created.json()["id"]).reference, reference)

    def test_reference_collision_is_retried_with_a_new_reference(self):
        self.order(reference="FD-TAKEN234")
        self.client.force_authenticate(self.dispatcher)
        with patch(GENERATE_REFERENCE, side_effect=["FD-TAKEN234", "FD-FRESH234"]) as generate:
            response = self.client.post("/api/work-orders/", {"title": "Job", "site_name": "Plant"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["reference"], "FD-FRESH234")
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(WorkOrder.objects.filter(organization=self.org).count(), 2)

    def test_reference_collisions_never_produce_a_duplicate(self):
        self.order(reference="FD-TAKEN234")
        self.client.force_authenticate(self.dispatcher)
        self.client.raise_request_exception = False
        with patch(GENERATE_REFERENCE, return_value="FD-TAKEN234") as generate:
            response = self.client.post("/api/work-orders/", {"title": "Job", "site_name": "Plant"}, format="json")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(generate.call_count, REFERENCE_ATTEMPTS)
        self.assertEqual(WorkOrder.objects.filter(reference="FD-TAKEN234").count(), 1)
