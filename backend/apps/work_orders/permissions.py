from apps.accounts.permissions import HasMembership, membership_for


class WorkOrderRolePermission(HasMembership):
    def has_permission(self, request, view):
        membership = membership_for(request.user)
        if membership is None:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return membership.role in ("owner", "dispatcher")
