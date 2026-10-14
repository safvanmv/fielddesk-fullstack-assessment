from django.conf import settings
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=120, unique=True)
    storage_limit_bytes = models.PositiveBigIntegerField(default=1073741824)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def storage_used_bytes(self):
        return self.attachments.aggregate(total=models.Sum("size"))["total"] or 0


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        DISPATCHER = "dispatcher", "Dispatcher"
        TECHNICIAN = "technician", "Technician"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        indexes = [models.Index(fields=["organization", "role"], name="membership_org_role_idx")]
