from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.common.testing import TenantTestCase


class AttachmentTests(TenantTestCase):
    def test_attachment_validates_type_quota_and_tenant_access(self):
        order = self.order()
        self.client.force_authenticate(self.dispatcher)
        invalid = SimpleUploadedFile("fake.pdf", b"not a pdf", content_type="application/pdf")
        self.assertEqual(self.client.post(f"/api/work-orders/{order.pk}/attachments/", {"file": invalid}).status_code, 400)
        valid = SimpleUploadedFile("report.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        uploaded = self.client.post(f"/api/work-orders/{order.pk}/attachments/", {"file": valid})
        self.assertEqual(uploaded.status_code, 201)
        self.assertNotIn("path", uploaded.json())
        attachment_id = uploaded.json()["id"]
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/attachments/{attachment_id}/download/").status_code, 404)
        self.client.force_authenticate(self.dispatcher)
        with override_settings(ATTACHMENT_MAX_BYTES=8):
            too_large = SimpleUploadedFile("large.pdf", b"%PDF-1.4x", content_type="application/pdf")
            self.assertEqual(self.client.post(f"/api/work-orders/{order.pk}/attachments/", {"file": too_large}).status_code, 400)
        self.client.force_authenticate(self.dispatcher)
        too_large_for_quota = SimpleUploadedFile("b.pdf", b"%PDF-" + b"x" * 1024, content_type="application/pdf")
        self.assertEqual(self.client.post(f"/api/work-orders/{order.pk}/attachments/", {"file": too_large_for_quota}).status_code, 413)
