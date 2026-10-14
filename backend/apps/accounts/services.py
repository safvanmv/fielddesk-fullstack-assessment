from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.activity.services import record_change
from apps.common.errors import Conflict
from apps.work_orders.models import WorkOrder

from .models import Membership, Organization

User = get_user_model()

ACTIVE_WORK_ORDER_STATUSES = [WorkOrder.Status.OPEN, WorkOrder.Status.SCHEDULED, WorkOrder.Status.IN_PROGRESS]


def create_member(*, actor, username, email, password, role, active):
    """Create a user and their membership in the actor's organization, with an audit entry, atomically."""
    organization = actor.membership.organization
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=username, email=email, password=password, is_active=active)
            member = Membership.objects.create(user=user, organization=organization, role=role)
            record_change(organization, actor, "membership.created", member, {"role": role, "active": active})
    except IntegrityError:
        # The serializer checked the username, but a concurrent request can take it before this insert.
        raise ValidationError({"username": ["This username is already taken."]})
    return member


def change_member(*, actor, member, role=None, active=None):
    """Change another member's role and/or active state.

    Membership changes in an organization are serialized on its row lock. Under that lock the actor is
    re-checked: a concurrent request may have just demoted or deactivated them, and their own request
    must not then act with owner authority. Because the actor must be an active owner and cannot change
    themselves, every committed change leaves the organization with at least one active owner.
    """
    with transaction.atomic():
        organization = Organization.objects.select_for_update().get(pk=member.organization_id)
        if not Membership.objects.filter(
            user=actor, organization=organization, role=Membership.Role.OWNER, user__is_active=True,
        ).exists():
            raise PermissionDenied("Only active owners can manage users.")
        target = Membership.objects.select_for_update().select_related("user").get(pk=member.pk)

        changes = {}
        if role is not None and role != target.role:
            changes["role"] = {"before": target.role, "after": role}
        if active is not None and active != target.user.is_active:
            if not active and target.user.assigned_work_orders.filter(status__in=ACTIVE_WORK_ORDER_STATUSES).exists():
                raise Conflict("Reassign or close active work orders before deactivating this user.")
            changes["active"] = {"before": target.user.is_active, "after": active}

        if "role" in changes:
            target.role = role
            target.save(update_fields=["role"])
        if "active" in changes:
            target.user.is_active = active
            target.user.save(update_fields=["is_active"])
        if changes:
            record_change(organization, actor, "membership.updated", target, changes)
    return target
