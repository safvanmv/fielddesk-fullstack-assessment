import uuid

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q, Value

# Constraint names the service layer reacts to: an overlap becomes a 409, a reference collision a retry.
SCHEDULE_OVERLAP_CONSTRAINT = "no_technician_schedule_overlap"
REFERENCE_CONSTRAINT = "unique_org_work_reference"


class WorkOrder(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="work_orders")
    reference = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="assigned_work_orders",
    )
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    site_name = models.CharField(max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_work_orders")
    assignment_revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "reference"], name=REFERENCE_CONSTRAINT),
            models.CheckConstraint(
                condition=Q(scheduled_start__isnull=True, scheduled_end__isnull=True)
                | Q(scheduled_start__isnull=False, scheduled_end__isnull=False, scheduled_start__lt=F("scheduled_end")),
                name="valid_work_order_window",
            ),
            ExclusionConstraint(
                name=SCHEDULE_OVERLAP_CONSTRAINT,
                expressions=[
                    (models.F("assigned_technician"), RangeOperators.EQUAL),
                    (
                        Func(
                            F("scheduled_start"),
                            F("scheduled_end"),
                            Value("[)"),
                            function="TSTZRANGE",
                            output_field=DateTimeRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=Q(assigned_technician__isnull=False)
                & Q(scheduled_start__isnull=False)
                & ~Q(status__in=["completed", "cancelled"]),
                deferrable=models.Deferrable.IMMEDIATE,
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "scheduled_start"], name="wo_org_status_start_idx"),
            models.Index(fields=["organization", "priority"], name="wo_org_priority_idx"),
        ]

    def __str__(self):
        return f"{self.title} - {self.assigned_technician}"


def attachment_upload_path(instance, filename):
    return f"org/{instance.organization_id}/work-orders/{instance.work_order_id}/{uuid.uuid4().hex}"


class Attachment(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="attachments")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ProgressEvent(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="progress_events")
    event_id = models.CharField(max_length=100)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="progress_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=30)
    occurred_at = models.DateTimeField()
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "event_id"], name="unique_org_event_id")]
        ordering = ["received_at"]
