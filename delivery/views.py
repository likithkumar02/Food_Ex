from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required

from .models import DeliveryAssignment, DeliveryPartnerProfile
from .services import (
    accept_assignment,
    advance_assignment,
    dispatch_ready_orders,
    refresh_partner_offers,
    reject_assignment,
)


@role_required("delivery_partner")
def delivery_dashboard_view(request):
    refresh_partner_offers(request.user)
    profile, _ = DeliveryPartnerProfile.objects.get_or_create(user=request.user)
    assignments = DeliveryAssignment.objects.filter(
        partner=request.user,
    ).select_related(
        "order__restaurant",
        "order__user__customer_profile",
    ).order_by("-created_at")
    return render(
        request,
        "delivery/dashboard.html",
        {"assignments": assignments, "partner_profile": profile},
    )


@role_required("delivery_partner")
def delivery_detail_view(request, assignment_id):
    assignment = get_object_or_404(
        DeliveryAssignment,
        pk=assignment_id,
        partner=request.user,
    )
    return render(request, "delivery/detail.html", {"assignment": assignment})


@role_required("delivery_partner")
def assign_delivery_view(request, order_id):
    assignment = get_object_or_404(
        DeliveryAssignment,
        order_id=order_id,
        partner=request.user,
    )
    return redirect("delivery_detail", assignment_id=assignment.pk)


@role_required("delivery_partner")
@require_POST
def delivery_availability_view(request):
    profile, _ = DeliveryPartnerProfile.objects.get_or_create(user=request.user)
    profile.is_online = request.POST.get("is_online") == "true"
    profile.save(update_fields=["is_online"])
    if profile.is_online:
        dispatch_ready_orders()
    return redirect("delivery_dashboard")


@role_required("delivery_partner")
@require_POST
def accept_delivery_view(request, assignment_id):
    assignment = get_object_or_404(
        DeliveryAssignment,
        pk=assignment_id,
        partner=request.user,
    )
    accept_assignment(request.user, assignment_id)
    return redirect("delivery_detail", assignment_id=assignment.pk)


@role_required("delivery_partner")
@require_POST
def reject_delivery_view(request, assignment_id):
    assignment = get_object_or_404(
        DeliveryAssignment,
        pk=assignment_id,
        partner=request.user,
    )
    reject_assignment(request.user, assignment_id, request.POST.get("reason", ""))
    return redirect("delivery_dashboard")


@role_required("delivery_partner")
@require_POST
def update_delivery_status_view(request, assignment_id, new_status):
    assignment = get_object_or_404(
        DeliveryAssignment,
        pk=assignment_id,
        partner=request.user,
    )
    updated = advance_assignment(request.user, assignment_id, new_status)
    if updated is None:
        return redirect("delivery_dashboard")

    if new_status == "delivered":
        return redirect("delivery_dashboard")
    return redirect("delivery_detail", assignment_id=assignment.pk)
