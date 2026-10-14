from apps.common.testing import TenantTestCase


class AuditContractTests(TenantTestCase):
    def test_frontend_technician_audit_and_me_contract_routes(self):
        self.client.force_authenticate(self.dispatcher)
        # Create through the API, as a client would, so the creation is audited.
        created = self.client.post("/api/work-orders/", {"title": "Repair pump", "site_name": "Plant 1"}, format="json")
        self.assertEqual(created.status_code, 201)
        order_id = created.json()["id"]
        technician_response = self.client.get("/api/technicians/")
        self.assertEqual(technician_response.status_code, 200)
        self.assertEqual(technician_response.json(), [{
            "id": self.tech.pk, "username": "tech", "email": "tech@example.test",
        }])
        me_response = self.client.get("/api/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["role"], "dispatcher")
        audit_response = self.client.get(f"/api/audit/?work_order={order_id}")
        self.assertEqual(audit_response.status_code, 200)
        entries = audit_response.json()
        self.assertEqual([entry["action"] for entry in entries], ["work_order.created"])
        self.assertEqual(entries[0]["target_id"], order_id)
        self.assertEqual(entries[0]["actor"], "dispatch")
