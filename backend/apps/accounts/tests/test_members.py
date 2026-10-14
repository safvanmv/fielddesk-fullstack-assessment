from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.models import Membership
from apps.accounts.services import change_member
from apps.common.testing import TenantTestCase
from apps.work_orders.models import WorkOrder


class MemberManagementTests(TenantTestCase):
    def test_health_is_public_and_owner_can_manage_organization_members(self):
        self.assertEqual(APIClient().get("/api/health/").json(), {"status": "ok"})
        self.client.force_authenticate(self.owner)
        created = self.client.post("/api/members/", {
            "username": "new_tech", "email": "new@example.test",
            "password": "FieldDesk!2026-new", "role": "technician",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertNotIn("password", created.json())
        membership = Membership.objects.get(user__username="new_tech")
        self.assertEqual(membership.organization, self.org)
        changed = self.client.patch(f"/api/members/{membership.pk}/", {"role": "dispatcher"}, format="json")
        self.assertEqual(changed.status_code, 200)
        membership.refresh_from_db()
        self.assertEqual(membership.role, "dispatcher")
        self.assertTrue(membership.user.is_active)
        deactivated = self.client.patch(f"/api/users/{membership.pk}/", {"active": False}, format="json")
        self.assertEqual(deactivated.status_code, 200)
        membership.refresh_from_db()
        self.assertFalse(membership.user.is_active)
        audit = self.client.get("/api/audit/?limit=10")
        actions = {entry["action"] for entry in audit.json()}
        self.assertIn("membership.created", actions)
        self.assertIn("membership.updated", actions)

    def test_owner_can_manage_another_owner_but_not_self(self):
        second_owner = self.user("second-owner", self.org, "owner", "owner-password")
        second_membership = second_owner.membership
        self.client.force_authenticate(self.owner)
        allowed = self.client.patch(
            f"/api/users/{second_membership.pk}/", {"active": False}, format="json"
        )
        self.assertEqual(allowed.status_code, 200)
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.patch(f"/api/users/{self.owner.membership.pk}/", {"active": False}, format="json").status_code,
            400,
        )

    def test_only_owners_can_list_view_create_or_change_members(self):
        target = f"/api/users/{self.tech.membership.pk}/"
        for user in (self.dispatcher, self.tech):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get("/api/users/").status_code, 403)
            self.assertEqual(self.client.get(target).status_code, 403)
            self.assertEqual(self.client.patch(target, {"role": "owner"}, format="json").status_code, 403)
            self.assertEqual(self.client.post("/api/users/", {
                "username": "sneaky", "password": "FieldDesk!2026-x", "role": "owner",
            }, format="json").status_code, 403)
        self.tech.membership.refresh_from_db()
        self.assertEqual(self.tech.membership.role, "technician")

    def test_owner_sees_only_their_own_organization(self):
        self.client.force_authenticate(self.owner)
        listed = {member["username"] for member in self.client.get("/api/users/").json()}
        self.assertEqual(listed, {"owner", "dispatch", "tech"})
        foreign = f"/api/users/{self.other.membership.pk}/"
        self.assertEqual(self.client.get(foreign).status_code, 404)
        self.assertEqual(self.client.patch(foreign, {"active": False}, format="json").status_code, 404)
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_active)

    def test_member_creation_is_validated_per_field(self):
        self.client.force_authenticate(self.owner)
        valid = {"username": "new_user", "email": "new@example.test", "password": "FieldDesk!2026-new", "role": "dispatcher"}
        cases = [
            ("password", {"password": "short"}),
            ("password", {"password": "123456789012"}),  # long enough but entirely numeric
            ("role", {"role": "admin"}),
            ("username", {"username": "tech"}),  # already taken
            ("username", {"username": "has spaces"}),
            ("email", {"email": "not-an-email"}),
        ]
        for field, override in cases:
            response = self.client.post("/api/users/", {**valid, **override}, format="json")
            self.assertEqual(response.status_code, 400, override)
            self.assertIn(field, response.json()["error"]["details"], override)
        self.assertFalse(Membership.objects.filter(user__username="new_user").exists())

    def test_member_changes_are_limited_to_role_and_active(self):
        self.client.force_authenticate(self.owner)
        target = f"/api/users/{self.dispatcher.membership.pk}/"
        self.assertEqual(self.client.patch(target, {"username": "renamed"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(target, {}, format="json").status_code, 400)
        self.assertEqual(self.client.put(target, {"role": "owner"}, format="json").status_code, 405)

    def test_members_cannot_be_deleted(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f"/api/users/{self.dispatcher.membership.pk}/")
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Membership.objects.filter(pk=self.dispatcher.membership.pk).exists())

    def test_technician_with_active_work_orders_cannot_be_deactivated(self):
        order = self.order(assignee=self.tech)
        self.client.force_authenticate(self.owner)
        target = f"/api/users/{self.tech.membership.pk}/"
        blocked = self.client.patch(target, {"active": False}, format="json")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["error"]["code"], "conflict")
        self.tech.refresh_from_db()
        self.assertTrue(self.tech.is_active)
        WorkOrder.objects.filter(pk=order.pk).update(status=WorkOrder.Status.COMPLETED)
        self.assertEqual(self.client.patch(target, {"active": False}, format="json").status_code, 200)

    def test_service_rechecks_the_actor_under_the_lock(self):
        # The view's permission ran when the request started; by the time the lock is held the actor
        # may have been demoted by a concurrent request. The service must not trust that earlier check.
        with self.assertRaises(PermissionDenied):
            change_member(actor=self.dispatcher, member=self.tech.membership, role="owner")
        self.tech.membership.refresh_from_db()
        self.assertEqual(self.tech.membership.role, "technician")

    def test_demoted_owner_loses_member_management(self):
        second_owner = self.user("second-owner", self.org, "owner", "owner-password")
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.patch(f"/api/users/{second_owner.membership.pk}/", {"role": "dispatcher"}, format="json").status_code,
            200,
        )
        self.client.force_authenticate(second_owner)
        self.assertEqual(
            self.client.patch(f"/api/users/{self.owner.membership.pk}/", {"role": "dispatcher"}, format="json").status_code,
            403,
        )
