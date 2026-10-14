from .models import AuditLog, RealtimeEvent


def record_change(organization, actor, action, target, changes=None):
    AuditLog.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        target_type=target.__class__.__name__,
        target_id=str(target.pk),
        changes=changes or {},
    )
    RealtimeEvent.objects.create(
        organization=organization,
        event_type=action,
        data={"target_type": target.__class__.__name__, "target_id": str(target.pk)},
    )
