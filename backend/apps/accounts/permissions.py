from rest_framework.permissions import BasePermission


def membership_for(user):
    return getattr(user, "membership", None) if user.is_authenticated else None


class HasMembership(BasePermission):
    def has_permission(self, request, view):
        return membership_for(request.user) is not None


class OwnerOnly(HasMembership):
    def has_permission(self, request, view):
        membership = membership_for(request.user)
        return membership is not None and membership.role == "owner"
