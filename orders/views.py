from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from delivery.models import DeliveryAssignment, DeliveryPartnerProfile
from delivery.services import manually_assign_delivery_partner
from payments.models import Payment
from restaurant.models import MenuItem, Restaurant

from .models import MAX_CART_ITEM_QUANTITY, Cart, CartItem, Order
from .services import (
    CartCheckoutError,
    OrderTransitionError,
    compute_order_totals,
    create_order_from_cart,
    transition_restaurant_order,
)


@role_required("customer")
def cart_view(request):
    cart, _ = Cart.objects.prefetch_related(
        "items__menu_item__restaurant",
    ).get_or_create(user=request.user)
    first_item = cart.items.first()
    return render(
        request,
        "orders/cart.html",
        {
            "cart": cart,
            "restaurant": first_item.menu_item.restaurant if first_item else None,
            "totals": compute_order_totals(cart.total_price),
        },
    )


@role_required("customer")
@require_POST
def add_to_cart_view(request, menu_item_id):
    menu_item = get_object_or_404(
        MenuItem.objects.select_related("restaurant"),
        pk=menu_item_id,
        is_available=True,
        restaurant__status="approved",
        restaurant__is_active=True,
        restaurant__is_open=True,
    )
    decision = request.POST.get("decision")
    with transaction.atomic():
        cart, _ = Cart.objects.select_for_update().get_or_create(user=request.user)
        has_other_restaurant = cart.items.exclude(
            menu_item__restaurant=menu_item.restaurant,
        ).exists()
        if has_other_restaurant:
            if decision == "continue":
                messages.info(request, "Your existing cart was kept unchanged.")
                return redirect("cart")
            if decision == "clear":
                cart.items.all().delete()
            else:
                existing_item = cart.items.select_related(
                    "menu_item__restaurant",
                ).first()
                return render(
                    request,
                    "orders/cart_conflict.html",
                    {
                        "cart": cart,
                        "existing_restaurant": existing_item.menu_item.restaurant,
                        "menu_item": menu_item,
                    },
                    status=409,
                )
        elif decision:
            return HttpResponseBadRequest("Invalid cart decision.")

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=menu_item,
            defaults={"quantity": 1},
        )
        if not created:
            if cart_item.quantity >= MAX_CART_ITEM_QUANTITY:
                messages.error(
                    request,
                    f"You can add up to {MAX_CART_ITEM_QUANTITY} of this item.",
                )
                return redirect("cart")
            cart_item.quantity += 1
            cart_item.save(update_fields=["quantity"])
    return redirect("cart")


@role_required("customer")
@require_POST
def cart_item_update_view(request, item_id, action):
    cart_item = get_object_or_404(
        CartItem.objects.select_related("cart"),
        pk=item_id,
        cart__user=request.user,
    )
    if action == "increase":
        if cart_item.quantity >= MAX_CART_ITEM_QUANTITY:
            messages.error(
                request,
                f"You can add up to {MAX_CART_ITEM_QUANTITY} of this item.",
            )
        else:
            cart_item.quantity += 1
            cart_item.save(update_fields=["quantity"])
    elif action == "decrease":
        if cart_item.quantity == 1:
            cart_item.delete()
        else:
            cart_item.quantity -= 1
            cart_item.save(update_fields=["quantity"])
    elif action == "remove":
        cart_item.delete()
    else:
        return HttpResponseBadRequest("Invalid cart item action.")
    return redirect("cart")


@role_required("customer")
def checkout_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    if not cart.items.exists():
        return redirect("cart")
    from customer.models import CustomerAddress

    addresses = CustomerAddress.objects.filter(user=request.user)

    if request.method == "POST":
        try:
            order = create_order_from_cart(
                request.user,
                request.POST.get("delivery_address", ""),
                address_id=request.POST.get("address_id") or None,
            )
        except CartCheckoutError as error:
            messages.error(request, str(error))
            return render(
                request,
                "orders/checkout.html",
                {"cart": cart, "addresses": addresses},
            )
        return redirect("payment_page", order_id=order.pk)

    return render(request, "orders/checkout.html", {"cart": cart, "addresses": addresses})


@role_required("customer")
def order_detail_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("restaurant", "address").prefetch_related(
            "items__menu_item",
        ),
        pk=order_id,
        user=request.user,
    )
    return render(request, "orders/detail.html", {"order": order})


@role_required("customer")
def order_history_view(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "orders/history.html", {"orders": orders})


@role_required("restaurant_owner")
def restaurant_order_management_view(request):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    if not restaurant:
        return redirect("restaurant_management")

    orders = Order.objects.filter(restaurant=restaurant).select_related(
        "user",
        "delivery_assignment__partner",
        "delivery_assignment__partner__delivery_profile",
    ).prefetch_related(
        "items__menu_item",
    ).filter(
        Q(payments__status="paid")
        | Q(payments__status="pending", payments__payment_method="cod")
        | Q(status__in=(Order.STATUS_REJECTED, Order.STATUS_CANCELLED))
    ).distinct().order_by("-created_at")
    timeline_states = [
        Order.STATUS_PLACED,
        Order.STATUS_ACCEPTED,
        Order.STATUS_PREPARING,
        Order.STATUS_READY,
        Order.STATUS_FINDING_PARTNER,
        Order.STATUS_DELIVERY_ASSIGNED,
        Order.STATUS_ASSIGNMENT_FAILED,
        Order.STATUS_DELIVERY_PARTNER_ASSIGNED,
        Order.STATUS_ARRIVED_AT_PICKUP,
        Order.STATUS_PICKED_UP,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
        Order.STATUS_REJECTED,
    ]
    labels = dict(Order.STATUS_CHOICES)
    busy_partner_ids = DeliveryAssignment.objects.filter(
        status__in=(
            DeliveryAssignment.STATUS_ASSIGNED,
            DeliveryAssignment.STATUS_ACCEPTED,
            DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP,
            DeliveryAssignment.STATUS_PICKED_UP,
            DeliveryAssignment.STATUS_ON_THE_WAY,
        )
    ).values_list("partner_id", flat=True)
    delivery_partners = DeliveryPartnerProfile.objects.filter(
        is_online=True,
        is_available=True,
        user__is_active=True,
    ).exclude(user_id__in=busy_partner_ids).select_related("user").order_by(
        "user__username"
    )
    for order in orders:
        if order.status in (Order.STATUS_CANCELLED, Order.STATUS_REJECTED):
            current_index = timeline_states.index(order.status)
            completed_states = {Order.STATUS_PLACED}
        else:
            current_index = timeline_states.index(order.status) if order.status in timeline_states else -1
            completed_states = set(timeline_states[: current_index + 1])
        order.restaurant_timeline = [
            {
                "status": state,
                "label": labels[state],
                "complete": state in completed_states,
                "current": state == order.status,
            }
            for state in timeline_states
        ]
    return render(
        request,
        "orders/restaurant_management.html",
        {
            "orders": orders,
            "restaurant": restaurant,
            "rejection_reasons": Order.REJECTION_REASON_CHOICES,
            "delivery_partners": delivery_partners,
        },
    )


@role_required("restaurant_owner")
@require_POST
def order_assign_delivery_partner_view(request, order_id):
    try:
        partner_id = int(request.POST.get("partner_id"))
    except (TypeError, ValueError):
        messages.error(request, "Choose a delivery partner to assign.")
        return redirect("restaurant_order_management")

    assignment = manually_assign_delivery_partner(
        order_id,
        partner_id,
        actor=request.user,
    )
    if assignment is None:
        messages.error(
            request,
            "That order or delivery partner is no longer available. Refresh the page and try again.",
        )
    else:
        messages.success(
            request,
            f"Delivery request sent to {assignment.partner.get_full_name() or assignment.partner.username}. "
            "The partner must accept before collecting the order.",
        )
    return redirect("restaurant_order_management")


@role_required("restaurant_owner")
@require_POST
def order_accept_view(request, order_id):
    try:
        transition_restaurant_order(request.user, order_id, Order.STATUS_ACCEPTED)
    except OrderTransitionError:
        messages.error(request, "This order cannot be accepted before payment or because its status changed.")
    return redirect("restaurant_order_management")


@role_required("restaurant_owner")
@require_POST
def order_reject_view(request, order_id):
    try:
        transition_restaurant_order(
            request.user,
            order_id,
            Order.STATUS_REJECTED,
            rejection_reason=request.POST.get("rejection_reason", ""),
            rejection_note=request.POST.get("rejection_note", ""),
        )
    except OrderTransitionError as error:
        messages.error(request, str(error))
    return redirect("restaurant_order_management")


@role_required("restaurant_owner")
@require_POST
def order_cancel_view(request, order_id):
    try:
        transition_restaurant_order(request.user, order_id, Order.STATUS_CANCELLED)
    except OrderTransitionError as error:
        messages.error(request, str(error))
    return redirect("restaurant_order_management")


@role_required("restaurant_owner")
@require_POST
def order_preparing_view(request, order_id):
    try:
        transition_restaurant_order(request.user, order_id, "preparing")
    except OrderTransitionError:
        messages.error(request, "This order cannot move to preparation.")
    return redirect("restaurant_order_management")


@role_required("restaurant_owner")
@require_POST
def order_ready_view(request, order_id):
    try:
        transition_restaurant_order(request.user, order_id, "ready_for_pickup")
    except OrderTransitionError:
        messages.error(request, "This order cannot be marked ready.")
    return redirect("restaurant_order_management")
