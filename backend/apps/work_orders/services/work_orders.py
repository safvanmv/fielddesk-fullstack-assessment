import logging
import secrets
from contextlib import contextmanager

from django.db import IntegrityError, OperationalError, transaction

from apps.activity.services import record_change
from apps.notifications.services import enqueue_assignment_notification

from ..models import REFERENCE_CONSTRAINT, SCHEDULE_OVERLAP_CONSTRAINT, WorkOrder

AUDITED_FIELDS = (
    "title", "description", "priority", "status", "assigned_technician", "scheduled_start", "scheduled_end", "site_name",
)

REFERENCE_PREFIX = "FD-"
# No 0/O or 1/I, so references can be read aloud and retyped without ambiguity.
REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
REFERENCE_LENGTH = 8  # 32**8, about 1.1e12 combinations per organization
REFERENCE_ATTEMPTS = 5

DEADLOCK_SQLSTATE = "40P01"
DEADLOCK_ATTEMPTS = 2  # the first retry runs after the other write has committed

logger = logging.getLogger(__name__)


class ScheduleConflict(Exception):
    """The technician already has an active work order overlapping the requested window."""


def violated_constraint(exc):
    """Name of the PostgreSQL constraint behind an IntegrityError, if there is one."""
    return getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)


@contextmanager
def _schedule_conflicts_as_errors():
    try:
        yield
    except IntegrityError as exc:
        if violated_constraint(exc) == SCHEDULE_OVERLAP_CONSTRAINT:
            raise ScheduleConflict from exc
        raise


def generate_reference():
    return REFERENCE_PREFIX + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))


def _insert_with_unique_reference(**fields):
    """Insert a work order under a fresh random reference.

    Uniqueness is guaranteed by the (organization, reference) constraint, not by checking first:
    a colliding insert fails inside its own savepoint and is retried with a new reference, while
    the surrounding transaction carries on.
    """
    for attempt in range(1, REFERENCE_ATTEMPTS + 1):
        try:
            with transaction.atomic():
                return WorkOrder.objects.create(reference=generate_reference(), **fields)
        except IntegrityError as exc:
            if violated_constraint(exc) != REFERENCE_CONSTRAINT or attempt == REFERENCE_ATTEMPTS:
                raise


def _is_deadlock(exc):
    return getattr(exc.__cause__, "sqlstate", None) == DEADLOCK_SQLSTATE


def _retry_on_deadlock(write):
    """Run a self-contained transactional write, retrying it if PostgreSQL aborts it as a deadlock victim.

    The exclusion constraint is checked after a row is inserted, so two simultaneous overlapping
    writes can each wait on the other's uncommitted row. PostgreSQL aborts one of them, and at most
    one row ever commits. By the retry the other write has committed, so the overlap surfaces as an
    ordinary constraint violation (a 409) instead of an unhandled deadlock (a 500).
    """
    for attempt in range(1, DEADLOCK_ATTEMPTS + 1):
        try:
            return write()
        except OperationalError as exc:
            if not _is_deadlock(exc) or attempt == DEADLOCK_ATTEMPTS:
                raise
            logger.warning("work order write was a deadlock victim; retrying", extra={"attempts": attempt})


def create_work_order(*, organization, user, data):
    """Insert a work order and its audit entry atomically; notify the technician after commit."""
    def write():
        with _schedule_conflicts_as_errors(), transaction.atomic():
            order = _insert_with_unique_reference(organization=organization, created_by=user, **data)
            record_change(
                organization, user, "work_order.created", order,
                {"status": order.status, "assigned_technician": str(order.assigned_technician_id) if order.assigned_technician_id else None},
            )
            if order.assigned_technician_id:
                transaction.on_commit(lambda: enqueue_assignment_notification(order.pk), robust=True)
        return order

    return _retry_on_deadlock(write)


def update_work_order(*, order, user, data):
    """Apply validated changes atomically, bumping the assignment revision when the technician changes."""
    old_assignee = order.assigned_technician_id
    old_revision = order.assignment_revision
    changed = {}
    for field in AUDITED_FIELDS:
        if field in data:
            old = getattr(order, f"{field}_id", None) if field == "assigned_technician" else getattr(order, field)
            new = data[field]
            if field == "assigned_technician":
                new = getattr(new, "pk", None)
            if old != new:
                changed[field] = {"before": str(old), "after": str(new)}

    def write():
        # Derived only from values captured before the first attempt, so a retry applies the same change.
        with _schedule_conflicts_as_errors(), transaction.atomic():
            for field, value in data.items():
                setattr(order, field, value)
            reassigned = order.assigned_technician_id != old_assignee
            order.assignment_revision = old_revision + 1 if reassigned else old_revision
            order.save()
            if changed:
                record_change(order.organization, user, "work_order.updated", order, changed)
            if order.assigned_technician_id and reassigned:
                transaction.on_commit(lambda: enqueue_assignment_notification(order.pk), robust=True)
        return order

    return _retry_on_deadlock(write)
