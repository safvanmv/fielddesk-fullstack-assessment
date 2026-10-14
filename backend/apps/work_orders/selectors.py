from django.db.models import Q

from apps.accounts.models import Membership
from apps.accounts.permissions import membership_for

from .models import WorkOrder

ORDERING_FIELDS = {"created_at", "-created_at", "scheduled_start", "-scheduled_start", "priority", "-priority", "title", "-title"}


def visible_work_orders(user):
    """Every work order the user may see: their organization's, narrowed to their own for technicians."""
    membership = membership_for(user)
    queryset = WorkOrder.objects.filter(organization=membership.organization).select_related("assigned_technician", "created_by")
    if membership.role == Membership.Role.TECHNICIAN:
        queryset = queryset.filter(assigned_technician=user)
    return queryset


def filter_work_orders(queryset, params):
    query = params.get("search", "").strip()
    if query:
        queryset = queryset.filter(
            Q(reference__icontains=query) | Q(title__icontains=query)
            | Q(description__icontains=query) | Q(site_name__icontains=query)
        )
    for key, field in (("status", "status"), ("priority", "priority")):
        value = params.get(key)
        if value:
            queryset = queryset.filter(**{field: value})
    technician = params.get("technician")
    if technician:
        queryset = queryset.filter(assigned_technician_id=technician)
    ordering = params.get("ordering", "-created_at")
    if ordering not in ORDERING_FIELDS:
        ordering = "-created_at"
    return queryset.order_by(ordering, "pk")


def scoped_orders(request):
    """The tenant- and role-scoped work orders for a request, with its list filters applied."""
    return filter_work_orders(visible_work_orders(request.user), request.query_params)
