from django.conf import settings
from django.db import models


class NotificationDelivery(models.Model):
    class Outcome(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    work_order = models.ForeignKey("work_orders.WorkOrder", on_delete=models.CASCADE)
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assignment_revision = models.PositiveIntegerField()
    outcome = models.CharField(max_length=10, choices=Outcome.choices, default=Outcome.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "assignment_revision"], name="unique_assignment_notification"
            )
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.get_outcome_display()}"


class NotificationReceipt(models.Model):
    idempotency_key = models.CharField(max_length=120, unique=True)
    work_order = models.ForeignKey("work_orders.WorkOrder", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
