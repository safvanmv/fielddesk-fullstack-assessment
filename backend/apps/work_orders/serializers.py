from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Attachment, WorkOrder

User = get_user_model()


class TechnicianField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        membership = getattr(self.context["request"].user, "membership", None)
        if not membership:
            return User.objects.none()
        return User.objects.filter(
            membership__organization=membership.organization,
            membership__role="technician",
            is_active=True,
        )


class WorkOrderSerializer(serializers.ModelSerializer):
    assigned_technician = TechnicianField(required=False, allow_null=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = [
            "id", "reference", "title", "description", "priority", "status",
            "assigned_technician", "scheduled_start", "scheduled_end", "site_name",
            "created_by", "attachments", "created_at", "updated_at",
        ]
        # The server assigns the reference (see services.work_orders); a client-sent value is ignored.
        read_only_fields = ["id", "reference", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("scheduled_start", getattr(self.instance, "scheduled_start", None))
        end = attrs.get("scheduled_end", getattr(self.instance, "scheduled_end", None))
        if (start is None) != (end is None):
            raise serializers.ValidationError({"scheduled_end": "Start and end must both be supplied."})
        if start and end and start >= end:
            raise serializers.ValidationError({"scheduled_end": "End must be after start."})
        return attrs

    def get_attachments(self, obj):
        return [
            {"id": str(item.pk), "name": item.original_name, "size": item.size, "content_type": item.content_type}
            for item in obj.attachments.all()
        ]


class ProgressEventSerializer(serializers.Serializer):
    eventId = serializers.CharField(max_length=100)
    workOrderId = serializers.UUIDField()
    type = serializers.ChoiceField(choices=["status_changed", "note"])
    occurredAt = serializers.DateTimeField()
    payload = serializers.JSONField()

    def validate_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Payload must be an object.")
        event_type = self.initial_data.get("type")
        if event_type == "status_changed":
            status = value.get("status")
            if status not in ("in_progress", "completed"):
                raise serializers.ValidationError({"status": "Must be in_progress or completed."})
            if set(value) - {"status", "note"}:
                raise serializers.ValidationError("Unexpected payload fields.")
            if "note" in value and (not isinstance(value["note"], str) or len(value["note"]) > 2000):
                raise serializers.ValidationError({"note": "Must be text of at most 2000 characters."})
        elif event_type == "note":
            if not isinstance(value.get("note"), str) or not value["note"].strip() or len(value["note"]) > 2000:
                raise serializers.ValidationError({"note": "A non-empty note is required."})
            if set(value) != {"note"}:
                raise serializers.ValidationError("Note events accept only a note.")
        return value


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "original_name", "content_type", "size", "created_at"]
        read_only_fields = fields
