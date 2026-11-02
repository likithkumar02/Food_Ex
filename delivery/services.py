from math import asin, cos, radians, sin, sqrt
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notifications.services import notify_user
from location.models import LocationSetting
from orders.models import Order

from .models import (
    DeliveryAssignment,
    DeliveryAssignmentAttempt,
    DeliveryPartnerProfile,
)
from orders.services import record_order_status_event


ACTIVE_ASSIGNMENT_STATUSES = (
    "assigned",
    "accepted",
    "arrived_at_pickup",
    "picked_up",
    "on_the_way",
)


def _distance_to_restaurant(profile, restaurant):
    coordinates = (
        profile.latitude,
        profile.longitude,
        restaurant.latitude,
        restaurant.longitude,
    )
    if any(coordinate is None for coordinate in coordinates):
        return float("inf")

    partner_latitude, partner_longitude, restaurant_latitude, restaurant_longitude = (
        radians(float(coordinate)) for coordinate in coordinates
    )
    latitude_delta = restaurant_latitude - partner_latitude
    longitude_delta = restaurant_longitude - partner_longitude
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(partner_latitude)
        * cos(restaurant_latitude)
        * sin(longitude_delta / 2) ** 2
    )
    return 6371 * 2 * asin(sqrt(haversine))


def _notify_waiting_for_delivery(order):
    from notifications.models import Notification

    title = "Waiting for a delivery partner"
    message = (
        f"Order #{order.pk} is ready. No delivery partner is currently available; "
        "Food_Ex will retry as fresh partner locations arrive."
    )
    User = get_user_model()
    recipients = [(order.restaurant.owner, f"/orders/restaurant/orders/")]
    recipients.extend(
        (user, "/location/admin/")
        for user in User.objects.filter(
            Q(is_staff=True) | Q(role="admin"),
            is_active=True,
        ).exclude(pk=order.restaurant.owner_id)
    )
    for recipient, link in recipients:
        if not Notification.objects.filter(
            user=recipient,
            category="delivery",
            title=title,
            message=message,
            link=link,
        ).exists():
            notify_user(recipient, "delivery", title, message, link)


def _notify_assignment_failed(order):
    User = get_user_model()
    title = "Delivery partner search needs attention"
    message = (
        f"No delivery partner accepted Order #{order.pk} after the configured "
        "number of offers. Review the assignment history and retry if appropriate."
    )
    notifications = [
        (
            order.user,
            "We are still looking for a delivery partner",
            f"We could not assign a delivery partner to Order {order.code} yet.",
            f"/orders/orders/{order.pk}/",
        ),
        (
            order.restaurant.owner,
            title,
            message,
            "/orders/restaurant/orders/",
        ),
    ]
    notifications.extend(
        (
            user,
            title,
            message,
            f"/admin/orders/order/{order.pk}/change/",
        )
        for user in User.objects.filter(
            Q(is_staff=True) | Q(role="admin"),
            is_active=True,
        ).exclude(pk__in=(order.user_id, order.restaurant.owner_id))
    )
    for recipient, notification_title, notification_message, link in notifications:
        notify_user(
            recipient,
            "delivery",
            notification_title,
            notification_message,
            link,
        )


def _set_order_status(order, status, actor=None, reason=""):
    previous_status = order.status
    if previous_status == status:
        return
    order.status = status
    order.save(update_fields=["status", "updated_at"])
    record_order_status_event(order, previous_status, actor=actor, reason=reason)


def _expire_pending_offer(assignment, order, now):
    attempt = assignment.attempts.filter(
        status=DeliveryAssignmentAttempt.STATUS_OFFERED
    ).order_by("-offered_at").first()
    setting = LocationSetting.load()
    offered_at = attempt.offered_at if attempt else assignment.created_at
    if (now - offered_at).total_seconds() < setting.delivery_assignment_accept_timeout_seconds:
        return False

    if attempt:
        attempt.status = DeliveryAssignmentAttempt.STATUS_TIMED_OUT
        attempt.responded_at = now
        attempt.save(update_fields=["status", "responded_at"])
    DeliveryPartnerProfile.objects.filter(user=assignment.partner).update(
        is_available=True
    )
    assignment.status = DeliveryAssignment.STATUS_TIMED_OUT
    assignment.save(update_fields=["status", "updated_at"])
    _set_order_status(
        order,
        Order.STATUS_FINDING_PARTNER,
        reason="Delivery partner offer timed out.",
    )
    return True


@transaction.atomic
def assign_ready_order(order, force_retry=False):
    locked_order = (
        Order.objects.select_for_update()
        .select_related("restaurant")
        .get(pk=order.pk)
    )
    if locked_order.status not in (
        Order.STATUS_READY,
        Order.STATUS_FINDING_PARTNER,
        Order.STATUS_DELIVERY_ASSIGNED,
    ):
        return None

    assignment = DeliveryAssignment.objects.select_for_update().filter(
        order=locked_order
    ).first()
    now = timezone.now()
    if assignment and assignment.status == DeliveryAssignment.STATUS_ASSIGNED:
        if not _expire_pending_offer(assignment, locked_order, now):
            return assignment
    elif assignment and assignment.status in ACTIVE_ASSIGNMENT_STATUSES:
        return assignment

    _set_order_status(locked_order, Order.STATUS_FINDING_PARTNER)
    setting = LocationSetting.load()
    attempts = assignment.attempts.count() if assignment else 0
    if attempts >= setting.delivery_assignment_max_attempts and not force_retry:
        _set_order_status(
            locked_order,
            Order.STATUS_ASSIGNMENT_FAILED,
            reason="Maximum delivery partner offers reached.",
        )
        _notify_assignment_failed(locked_order)
        return None

    if (
        locked_order.restaurant.latitude is None
        or locked_order.restaurant.longitude is None
    ):
        _set_order_status(locked_order, Order.STATUS_FINDING_PARTNER)
        _notify_waiting_for_delivery(locked_order)
        return None

    profiles = list(
        DeliveryPartnerProfile.objects.select_for_update()
        .filter(
            is_online=True,
            is_available=True,
            user__role="delivery_partner",
            latitude__isnull=False,
            longitude__isnull=False,
            location_updated_at__gte=timezone.now() - timedelta(
                seconds=setting.partner_location_max_age_seconds
            ),
        )
    )
    busy_partners = set(
        DeliveryAssignment.objects.filter(
            status__in=ACTIVE_ASSIGNMENT_STATUSES
        ).values_list("partner_id", flat=True)
    )
    profiles = [profile for profile in profiles if profile.user_id not in busy_partners]
    tried_partner_ids = (
        assignment.attempts.values_list("partner_id", flat=True)
        if assignment and not force_retry
        else ()
    )
    profiles = [profile for profile in profiles if profile.user_id not in tried_partner_ids]
    search_radius_km = min(
        setting.delivery_assignment_initial_radius_km * (attempts + 1),
        setting.delivery_assignment_max_radius_km,
    )
    profiles = [
        profile
        for profile in profiles
        if _distance_to_restaurant(profile, locked_order.restaurant)
        <= search_radius_km
    ]

    if not profiles:
        _set_order_status(locked_order, Order.STATUS_FINDING_PARTNER)
        _notify_waiting_for_delivery(locked_order)
        return None

    selected_profile = min(
        profiles,
        key=lambda profile: (
            _distance_to_restaurant(profile, locked_order.restaurant),
            profile.pk,
        ),
    )
    selected_profile.is_available = False
    selected_profile.save(update_fields=["is_available"])

    if assignment:
        assignment.partner = selected_profile.user
        assignment.status = DeliveryAssignment.STATUS_ASSIGNED
        assignment.arrived_at_pickup_time = None
        assignment.pickup_time = None
        assignment.delivery_time = None
        assignment.save(
            update_fields=[
                "partner",
                "status",
                "arrived_at_pickup_time",
                "pickup_time",
                "delivery_time",
                "updated_at",
            ]
        )
    else:
        assignment = DeliveryAssignment.objects.create(
            order=locked_order,
            partner=selected_profile.user,
            status=DeliveryAssignment.STATUS_ASSIGNED,
        )

    DeliveryAssignmentAttempt.objects.create(
        assignment=assignment,
        partner=selected_profile.user,
    )
    _set_order_status(locked_order, Order.STATUS_DELIVERY_ASSIGNED)
    locked_order.delivery_assigned_at = now
    locked_order.save(update_fields=["status", "delivery_assigned_at", "updated_at"])

    notify_user(
        selected_profile.user,
        "delivery",
        "New delivery request",
        f"Order #{locked_order.pk} is ready for pickup.",
        f"/delivery/detail/{assignment.pk}/",
    )
    return assignment


def dispatch_ready_orders():
    ready_orders = Order.objects.filter(
        status__in=[
            Order.STATUS_READY,
            Order.STATUS_FINDING_PARTNER,
            Order.STATUS_DELIVERY_ASSIGNED,
        ],
    ).order_by("created_at")
    return [assign_ready_order(order) for order in ready_orders]


@transaction.atomic
def manually_assign_delivery_partner(order_id, partner_id, actor=None):
    order = (
        Order.objects.select_for_update()
        .select_related("restaurant")
        .filter(pk=order_id)
        .first()
    )
    if (
        order is None
        or actor is None
        or order.restaurant.owner_id != actor.pk
        or order.status not in (
        Order.STATUS_READY,
        Order.STATUS_FINDING_PARTNER,
        Order.STATUS_DELIVERY_ASSIGNED,
        Order.STATUS_ASSIGNMENT_FAILED,
        )
    ):
        return None

    assignment = DeliveryAssignment.objects.select_for_update().filter(
        order=order,
    ).first()
    if assignment and assignment.status in (
        DeliveryAssignment.STATUS_ACCEPTED,
        DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP,
        DeliveryAssignment.STATUS_PICKED_UP,
        DeliveryAssignment.STATUS_ON_THE_WAY,
    ):
        return None

    profile = (
        DeliveryPartnerProfile.objects.select_for_update()
        .filter(
            user_id=partner_id,
            user__role="delivery_partner",
            user__is_active=True,
            is_online=True,
            is_available=True,
        )
        .first()
    )
    if profile is None:
        return None

    busy_assignments = DeliveryAssignment.objects.filter(
        partner_id=partner_id,
        status__in=ACTIVE_ASSIGNMENT_STATUSES,
    )
    if assignment:
        busy_assignments = busy_assignments.exclude(pk=assignment.pk)
    if busy_assignments.exists():
        return None

    if assignment and assignment.status == DeliveryAssignment.STATUS_ASSIGNED:
        now = timezone.now()
        previous_partner = assignment.partner
        previous_attempt = assignment.attempts.filter(
            partner=previous_partner,
            status=DeliveryAssignmentAttempt.STATUS_OFFERED,
        ).order_by("-offered_at").first()
        if previous_attempt:
            previous_attempt.status = DeliveryAssignmentAttempt.STATUS_CANCELLED
            previous_attempt.responded_at = now
            previous_attempt.rejection_reason = "Replaced by a manual restaurant assignment."
            previous_attempt.save(
                update_fields=["status", "responded_at", "rejection_reason"]
            )
        DeliveryPartnerProfile.objects.filter(user=assignment.partner).update(
            is_available=True
        )
        notify_user(
            previous_partner,
            "delivery",
            "Delivery request reassigned",
            f"Order #{order.pk} was reassigned by the restaurant and is no longer assigned to you.",
            "/delivery/",
        )

    profile.is_available = False
    profile.save(update_fields=["is_available"])
    if assignment is None:
        assignment = DeliveryAssignment.objects.create(
            order=order,
            partner=profile.user,
            status=DeliveryAssignment.STATUS_ASSIGNED,
        )
    else:
        assignment.partner = profile.user
        assignment.status = DeliveryAssignment.STATUS_ASSIGNED
        assignment.arrived_at_pickup_time = None
        assignment.pickup_time = None
        assignment.delivery_time = None
        assignment.save(
            update_fields=[
                "partner",
                "status",
                "arrived_at_pickup_time",
                "pickup_time",
                "delivery_time",
                "updated_at",
            ]
        )

    DeliveryAssignmentAttempt.objects.create(
        assignment=assignment,
        partner=profile.user,
    )
    _set_order_status(
        order,
        Order.STATUS_DELIVERY_ASSIGNED,
        actor=actor,
        reason="Restaurant manually assigned a delivery partner.",
    )
    order.delivery_assigned_at = timezone.now()
    order.save(update_fields=["delivery_assigned_at", "updated_at"])
    notify_user(
        profile.user,
        "delivery",
        "New delivery request",
        f"Order #{order.pk} is ready for pickup. Please accept or reject the request.",
        f"/delivery/detail/{assignment.pk}/",
    )
    return assignment


def retry_delivery_assignment(order_id, actor=None):
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if order is None or order.status not in (
            Order.STATUS_FINDING_PARTNER,
            Order.STATUS_ASSIGNMENT_FAILED,
        ):
            return None
        _set_order_status(
            order,
            Order.STATUS_FINDING_PARTNER,
            actor=actor,
            reason="Delivery assignment manually retried.",
        )
        return assign_ready_order(order, force_retry=True)


def refresh_partner_offers(user):
    dispatch_ready_orders()


@transaction.atomic
def cancel_order_assignment(order, actor=None, reason=""):
    assignment = DeliveryAssignment.objects.select_for_update().filter(
        order=order,
        status__in=ACTIVE_ASSIGNMENT_STATUSES,
    ).first()
    if assignment is None:
        return None
    assignment.status = DeliveryAssignment.STATUS_CANCELLED
    assignment.save(update_fields=["status", "updated_at"])
    DeliveryPartnerProfile.objects.filter(user=assignment.partner).update(
        is_available=True
    )
    attempt = assignment.attempts.filter(
        partner=assignment.partner,
        status=DeliveryAssignmentAttempt.STATUS_OFFERED,
    ).order_by("-offered_at").first()
    if attempt:
        attempt.status = DeliveryAssignmentAttempt.STATUS_CANCELLED
        attempt.responded_at = timezone.now()
        attempt.rejection_reason = (reason or "Order cancelled.")[:255]
        attempt.save(
            update_fields=["status", "responded_at", "rejection_reason"]
        )
    notify_user(
        assignment.partner,
        "delivery",
        "Delivery assignment cancelled",
        f"Order #{order.pk} was cancelled and is no longer assigned to you.",
        "/delivery/",
    )
    return assignment


@transaction.atomic
def accept_assignment(user, assignment_id):
    assignment = DeliveryAssignment.objects.select_for_update().filter(
        pk=assignment_id,
        partner=user,
    ).first()
    if assignment is None or assignment.status != DeliveryAssignment.STATUS_ASSIGNED:
        return None
    order = Order.objects.select_for_update().get(pk=assignment.order_id)
    if order.status != Order.STATUS_DELIVERY_ASSIGNED:
        return None
    if _expire_pending_offer(assignment, order, timezone.now()):
        assign_ready_order(order)
        return None
    attempt = assignment.attempts.filter(
        partner=user,
        status=DeliveryAssignmentAttempt.STATUS_OFFERED,
    ).order_by("-offered_at").first()
    if attempt:
        attempt.status = DeliveryAssignmentAttempt.STATUS_ACCEPTED
        attempt.responded_at = timezone.now()
        attempt.save(update_fields=["status", "responded_at"])
    assignment.status = DeliveryAssignment.STATUS_ACCEPTED
    assignment.save(update_fields=["status", "updated_at"])

    now = timezone.now()
    _set_order_status(
        order,
        Order.STATUS_DELIVERY_PARTNER_ASSIGNED,
        actor=user,
    )
    order.delivery_partner_assigned_at = now
    order.save(update_fields=["status", "delivery_partner_assigned_at", "updated_at"])

    notify_user(
        order.user,
        "delivery",
        "Delivery partner assigned",
        f"Delivery partner {user.get_full_name() or user.username} has accepted Order {order.code}.",
        f"/orders/orders/{order.pk}/",
    )
    return assignment


@transaction.atomic
def reject_assignment(user, assignment_id, reason=""):
    assignment = DeliveryAssignment.objects.select_for_update().filter(
        pk=assignment_id,
        partner=user,
    ).first()
    if assignment is None or assignment.status != DeliveryAssignment.STATUS_ASSIGNED:
        return None
    attempt = assignment.attempts.filter(
        partner=user,
        status=DeliveryAssignmentAttempt.STATUS_OFFERED,
    ).order_by("-offered_at").first()
    if attempt:
        attempt.status = DeliveryAssignmentAttempt.STATUS_REJECTED
        attempt.responded_at = timezone.now()
        attempt.rejection_reason = (reason or "").strip()[:255]
        attempt.save(
            update_fields=["status", "responded_at", "rejection_reason"]
        )
    assignment.status = DeliveryAssignment.STATUS_REJECTED
    assignment.save(update_fields=["status", "updated_at"])
    DeliveryPartnerProfile.objects.filter(user=user).update(is_available=True)
    order = Order.objects.select_for_update().get(pk=assignment.order_id)
    _set_order_status(
        order,
        Order.STATUS_FINDING_PARTNER,
        actor=user,
        reason=reason,
    )
    assign_ready_order(order)
    return assignment


@transaction.atomic
def advance_assignment(user, assignment_id, new_status):
    assignment = DeliveryAssignment.objects.select_for_update().filter(
        pk=assignment_id,
        partner=user,
    ).first()
    valid_transitions = {
        DeliveryAssignment.STATUS_ACCEPTED: {
            DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP: Order.STATUS_ARRIVED_AT_PICKUP,
        },
        DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP: {
            DeliveryAssignment.STATUS_PICKED_UP: Order.STATUS_PICKED_UP,
        },
        DeliveryAssignment.STATUS_PICKED_UP: {
            DeliveryAssignment.STATUS_ON_THE_WAY: Order.STATUS_OUT_FOR_DELIVERY,
        },
        DeliveryAssignment.STATUS_ON_THE_WAY: {
            DeliveryAssignment.STATUS_DELIVERED: Order.STATUS_DELIVERED,
        },
    }
    allowed = valid_transitions.get(assignment.status, {}) if assignment else {}
    target_order_status = allowed.get(new_status)
    if target_order_status is None:
        return None

    order = Order.objects.select_for_update().select_related(
        "restaurant__owner"
    ).get(pk=assignment.order_id)
    required_order_status = {
        DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP: (
            Order.STATUS_DELIVERY_PARTNER_ASSIGNED
        ),
        DeliveryAssignment.STATUS_PICKED_UP: Order.STATUS_ARRIVED_AT_PICKUP,
        DeliveryAssignment.STATUS_ON_THE_WAY: Order.STATUS_PICKED_UP,
        DeliveryAssignment.STATUS_DELIVERED: Order.STATUS_OUT_FOR_DELIVERY,
    }[new_status]
    if order.status != required_order_status:
        return None

    assignment.status = new_status
    fields = ["status", "updated_at"]
    now = timezone.now()
    if new_status == DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP:
        assignment.arrived_at_pickup_time = now
        fields.append("arrived_at_pickup_time")
    elif new_status == DeliveryAssignment.STATUS_PICKED_UP:
        assignment.pickup_time = now
        fields.append("pickup_time")
    elif new_status == DeliveryAssignment.STATUS_DELIVERED:
        assignment.delivery_time = now
        fields.append("delivery_time")
    assignment.save(update_fields=fields)

    _set_order_status(order, target_order_status, actor=user)
    order_fields = ["status", "updated_at"]
    if target_order_status == Order.STATUS_ARRIVED_AT_PICKUP:
        order.arrived_at_pickup_at = now
        order_fields.append("arrived_at_pickup_at")
    elif target_order_status == Order.STATUS_PICKED_UP:
        order.picked_up_at = now
        order_fields.append("picked_up_at")
    elif target_order_status == Order.STATUS_DELIVERED:
        order.delivered_at = now
        order.closed_at = now
        order_fields.extend(["delivered_at", "closed_at"])
    order.save(update_fields=order_fields)

    status_messages = {
        DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP: (
            "Partner arrived at restaurant",
            "The delivery partner has arrived at the restaurant.",
        ),
        DeliveryAssignment.STATUS_PICKED_UP: (
            "Order picked up",
            "The delivery partner picked up your order.",
        ),
        DeliveryAssignment.STATUS_ON_THE_WAY: (
            "Order on the way",
            "Your order is on the way to you.",
        ),
        DeliveryAssignment.STATUS_DELIVERED: (
            "Order delivered",
            "Your order was marked delivered.",
        ),
    }
    title, message = status_messages[new_status]
    notify_user(
        order.user,
        "delivery",
        title,
        f"{message} Order {order.code}.",
        f"/orders/orders/{order.pk}/",
    )
    if new_status == DeliveryAssignment.STATUS_ARRIVED_AT_PICKUP:
        notify_user(
            order.restaurant.owner,
            "delivery",
            "Delivery partner arrived",
            f"Delivery partner has arrived to collect Order #{order.pk}.",
            "/orders/restaurant/orders/",
        )
    elif new_status == DeliveryAssignment.STATUS_DELIVERED:
        from restaurant.services import record_order_earning

        _settle_cash_on_delivery(order)
        record_order_earning(order)
        profile = DeliveryPartnerProfile.objects.select_for_update().filter(user=user).first()
        if profile:
            profile.is_available = True
            profile.save(update_fields=["is_available"])
            if profile.is_online:
                dispatch_ready_orders()
    return assignment


def _settle_cash_on_delivery(order):
    """Mark a pending COD payment as collected once the order is delivered."""
    from payments.models import Payment

    Payment.objects.filter(
        order=order,
        payment_method="cod",
        status=Payment.STATUS_PENDING,
    ).update(status=Payment.STATUS_PAID)
