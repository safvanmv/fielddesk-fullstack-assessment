from django.core.files.uploadedfile import SimpleUploadedFile

from apps.common.testing import TenantTestCase


class OrganizationSettingsTests(TenantTestCase):
    def test_owner_can_manage_org_settings_but_non_owner_cannot(self):
        self.client.force_authenticate(self.dispatcher)
        self.assertEqual(self.client.get("/api/organization/settings/").status_code, 200)
        self.assertEqual(
            self.client.patch("/api/organization/settings/", {"storage_limit_bytes": 2048}, format="json").status_code,
            403,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.patch("/api/organization/settings/", {
            "name": "Org A Updated", "storage_limit_bytes": 2048,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Org A Updated")
        self.assertEqual(response.json()["storage_limit_bytes"], 2048)
        audit = self.client.get("/api/audit/?limit=10")
        self.assertIn("organization.settings_updated", {entry["action"] for entry in audit.json()})
        invalid = self.client.patch("/api/organization/settings/", {"storage_limit_bytes": -1}, format="json")
        self.assertEqual(invalid.status_code, 400)

        # A limit below what the organization already stores is refused.
        report = SimpleUploadedFile("report.pdf", b"%PDF-1.4 stored report", content_type="application/pdf")
        uploaded = self.client.post(f"/api/work-orders/{self.order().pk}/attachments/", {"file": report})
        self.assertEqual(uploaded.status_code, 201)
        used = self.client.get("/api/organization/settings/").json()["storage_used_bytes"]
        self.assertEqual(used, uploaded.json()["size"])
        overused = self.client.patch("/api/organization/settings/", {"storage_limit_bytes": used - 1}, format="json")
        self.assertEqual(overused.status_code, 400)
        exact = self.client.patch("/api/organization/settings/", {"storage_limit_bytes": used}, format="json")
        self.assertEqual(exact.status_code, 200)
