from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError, transaction
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import mixins, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity.services import record_change

from .models import Membership
from .permissions import HasMembership, OwnerOnly, membership_for
from .serializers import MemberCreateSerializer, MembershipSerializer, MemberUpdateSerializer
from .services import change_member, create_member
from .throttles import LoginRateThrottle

User = get_user_model()


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    get_token(request._request)
    return Response(status=204)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        csrf_middleware = CsrfViewMiddleware(lambda http_request: None)
        csrf_middleware.process_request(request._request)
        csrf_failure = csrf_middleware.process_view(request._request, lambda http_request: None, (), {})
        if csrf_failure is not None:
            return Response({"detail": "CSRF verification failed."}, status=403)
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        if not isinstance(username, str) or not isinstance(password, str):
            return Response({"detail": "Invalid credentials."}, status=400)
        user = authenticate(request._request, username=username, password=password)
        if user is None or not hasattr(user, "membership"):
            return Response({"detail": "Invalid credentials."}, status=400)
        login(request._request, user)
        return Response({"user": current_user_data(user)})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=204)


class CurrentUserView(APIView):
    permission_classes = [HasMembership]

    def get(self, request):
        return Response(current_user_data(request.user))


def current_user_data(user):
    membership = membership_for(user)
    return {
        "id": str(user.pk),
        "username": user.get_username(),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": membership.role,
        "organization_name": membership.organization.name,
    }


class TechnicianListView(APIView):
    permission_classes = [HasMembership]

    def get(self, request):
        membership = membership_for(request.user)
        technicians = User.objects.filter(
            membership__organization=membership.organization,
            membership__role=Membership.Role.TECHNICIAN,
            is_active=True,
        ).order_by("username")
        return Response([{
            "id": user.pk,
            "username": user.get_username(),
            "email": user.email,
        } for user in technicians])


class OrganizationSettingsView(APIView):
    permission_classes = [HasMembership]

    @staticmethod
    def settings_data(organization):
        return {
            "id": organization.pk,
            "name": organization.name,
            "storage_limit_bytes": organization.storage_limit_bytes,
            "storage_used_bytes": organization.storage_used_bytes,
        }

    def get(self, request):
        return Response(self.settings_data(membership_for(request.user).organization))

    def patch(self, request):
        membership = membership_for(request.user)
        if membership.role != Membership.Role.OWNER:
            return Response({"detail": "Only owners can update organization settings."}, status=403)
        if not isinstance(request.data, dict) or not request.data:
            return Response({"detail": "Provide at least one setting to update."}, status=400)
        allowed = {"name", "storage_limit_bytes"}
        if set(request.data) - allowed:
            return Response({"detail": "Only name and storage_limit_bytes may be updated."}, status=400)
        try:
            with transaction.atomic():
                organization = type(membership.organization).objects.select_for_update().get(pk=membership.organization_id)
                before = {}
                after = {}
                if "name" in request.data:
                    name = request.data["name"]
                    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
                        return Response({"detail": "Name must contain between 1 and 120 characters."}, status=400)
                    if type(organization).objects.exclude(pk=organization.pk).filter(name=name.strip()).exists():
                        return Response({"detail": "An organization with this name already exists."}, status=400)
                    if name.strip() != organization.name:
                        before["name"] = organization.name
                        after["name"] = name.strip()
                        organization.name = name.strip()
                if "storage_limit_bytes" in request.data:
                    limit = request.data["storage_limit_bytes"]
                    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                        return Response({"detail": "storage_limit_bytes must be a non-negative integer."}, status=400)
                    used = organization.storage_used_bytes
                    if limit < used:
                        return Response({"detail": "Storage limit cannot be lower than current usage."}, status=400)
                    if limit != organization.storage_limit_bytes:
                        before["storage_limit_bytes"] = organization.storage_limit_bytes
                        after["storage_limit_bytes"] = limit
                        organization.storage_limit_bytes = limit
                if after:
                    organization.save(update_fields=list(after))
                    record_change(organization, request.user, "organization.settings_updated", organization,
                                  {key: {"before": before[key], "after": after[key]} for key in after})
                return Response(self.settings_data(organization))
        except IntegrityError:
            return Response({"detail": "Organization name is already in use."}, status=400)


class MemberViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Owner-only user management for the owner's organization.

    There is deliberately no DestroyModelMixin: users are deactivated, not deleted, because work orders,
    attachments and progress events reference them and audit entries must keep identifying the actor.
    """

    permission_classes = [OwnerOnly]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        organization = membership_for(self.request.user).organization
        return Membership.objects.filter(organization=organization).select_related("user").order_by("pk")

    def get_serializer_class(self):
        if self.action == "create":
            return MemberCreateSerializer
        if self.action == "partial_update":
            return MemberUpdateSerializer
        return MembershipSerializer

    def perform_create(self, serializer):
        serializer.instance = create_member(actor=self.request.user, **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = change_member(
            actor=self.request.user, member=serializer.instance, **serializer.validated_data,
        )
