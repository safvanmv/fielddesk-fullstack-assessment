from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Organization
from apps.work_orders.models import WorkOrder

User = get_user_model()


class TenantTestCase(TestCase):
    """Org A has an owner, a dispatcher and a technician; Org B has only an owner."""

    def setUp(self):
        self.org = Organization.objects.create(name="Org A", storage_limit_bytes=1024)
        self.other_org = Organization.objects.create(name="Org B")
        self.owner = self.user("owner", self.org, "owner", "owner-password")
        self.dispatcher = self.user("dispatch", self.org, "dispatcher", "dispatch-password")
        self.tech = self.user("tech", self.org, "technician", "tech-password")
        self.other = self.user("other", self.other_org, "owner", "other-password")
        self.client = APIClient()

    def user(self, username, organization, role, password):
        user = User.objects.create_user(username=username, password=password, email=f"{username}@example.test")
        Membership.objects.create(user=user, organization=organization, role=role)
        return user

    def order(self, *, organization=None, assignee=None, **values):
        return WorkOrder.objects.create(
            organization=organization or self.org,
            reference=values.pop("reference", "FD-100"),
            title=values.pop("title", "Repair pump"),
            site_name=values.pop("site_name", "Plant 1"),
            created_by=values.pop("created_by", self.dispatcher),
            assigned_technician=assignee,
            **values,
        )
