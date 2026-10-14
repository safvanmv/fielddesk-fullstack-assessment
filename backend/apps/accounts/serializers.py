from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Membership

User = get_user_model()


class MembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "username", "email", "role", "active"]
        read_only_fields = ["id", "username", "email", "active"]


class _MemberResponseMixin:
    """Input serializers reply with the standard member representation."""

    def to_representation(self, instance):
        return MembershipSerializer(instance, context=self.context).data


class MemberCreateSerializer(_MemberResponseMixin, serializers.Serializer):
    """Shape of a new member. Uniqueness is re-enforced by the database when the user is inserted."""

    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    email = serializers.EmailField(max_length=254, allow_blank=True, default="")
    password = serializers.CharField(min_length=12, max_length=128, write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    active = serializers.BooleanField(default=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate(self, attrs):
        # Passing the prospective user lets the similarity validator compare against username and email.
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class MemberUpdateSerializer(_MemberResponseMixin, serializers.Serializer):
    """Owners may change another member's role and/or active state, and nothing else."""

    role = serializers.ChoiceField(choices=Membership.Role.choices, required=False)
    active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown or not attrs:
            raise serializers.ValidationError("Only role and active may be updated.")
        if self.instance.user_id == self.context["request"].user.pk:
            raise serializers.ValidationError("You cannot change your own role or active state.")
        return attrs
