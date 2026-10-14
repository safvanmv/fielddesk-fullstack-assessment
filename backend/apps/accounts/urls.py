from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    CurrentUserView,
    LoginView,
    LogoutView,
    MemberViewSet,
    OrganizationSettingsView,
    TechnicianListView,
    csrf,
)

router = SimpleRouter()
router.register("members", MemberViewSet, basename="member")
router.register("users", MemberViewSet, basename="user")

urlpatterns = [
    path("auth/csrf/", csrf, name="csrf"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("auth/logout/", LogoutView.as_view(), name="logout-legacy"),
    path("auth/me/", CurrentUserView.as_view(), name="current-user-legacy"),
    path("technicians/", TechnicianListView.as_view(), name="technicians"),
    path("organization/settings/", OrganizationSettingsView.as_view(), name="organization-settings"),
    path("", include(router.urls)),
]
