import logging

from django.conf import settings
from django.db import transaction

from apps.accounts.models import Organization
from apps.activity.services import record_change

from ..models import Attachment

logger = logging.getLogger(__name__)

ALLOWED_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}


class AttachmentRejected(Exception):
    def __init__(self, detail, status=400):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def _validate_upload(uploaded):
    if uploaded.size > settings.ATTACHMENT_MAX_BYTES:
        raise AttachmentRejected("File exceeds the per-file size limit.")
    content_type = uploaded.content_type
    signatures = ALLOWED_SIGNATURES.get(content_type)
    head = uploaded.read(12)
    uploaded.seek(0)
    valid = signatures and any(head.startswith(signature) for signature in signatures)
    if content_type == "image/webp":
        valid = valid and head[8:12] == b"WEBP"
    if not valid:
        raise AttachmentRejected("Only valid JPEG, PNG, GIF, WebP and PDF files are accepted.")
    return content_type


def add_attachment(*, organization_id, order, user, uploaded):
    """Validate and store an upload, enforcing the organization quota under a row lock."""
    content_type = _validate_upload(uploaded)
    try:
        with transaction.atomic():
            organization = Organization.objects.select_for_update().get(pk=organization_id)
            if organization.storage_used_bytes + uploaded.size > organization.storage_limit_bytes:
                raise AttachmentRejected("Organization storage quota exceeded.", status=413)
            attachment = Attachment.objects.create(
                organization=organization, work_order=order, file=uploaded,
                original_name=uploaded.name[:255], content_type=content_type,
                size=uploaded.size, uploaded_by=user,
            )
            record_change(organization, user, "attachment.added", attachment)
    except AttachmentRejected:
        raise
    except Exception:
        logger.exception("attachment upload failed")
        raise
    return attachment
