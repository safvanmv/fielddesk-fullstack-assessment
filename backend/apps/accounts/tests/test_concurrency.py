from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Organization
from apps.activity.models import AuditLog

User = get_user_model()


class OwnerConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Owner Org")
        self.owners = []
        for username in ("owner-a", "owner-b"):
            user = User.objects.create_user(username=username, password="password")
            Membership.objects.create(user=user, organization=self.org, role="owner")
            self.owners.append(user)

    def test_owners_demoting_each_other_simultaneously_leave_one_owner(self):
        barrier = Barrier(2)

        def demote(actor, target):
            try:
                client = APIClient()
                client.force_authenticate(actor)
                barrier.wait(timeout=10)
                response = client.patch(f"/api/users/{target.membership.pk}/", {"role": "dispatcher"}, format="json")
                return response.status_code
            finally:
                connection.close()

        owner_a, owner_b = self.owners
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(demote, [owner_a, owner_b], [owner_b, owner_a]))
        self.assertCountEqual(results, [200, 403])
        self.assertEqual(Membership.objects.filter(organization=self.org, role="owner").count(), 1)
        self.assertEqual(AuditLog.objects.filter(action="membership.updated").count(), 1)
