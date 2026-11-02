from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from orders.models import Order

from .models import RestaurantEarning, Settlement, quantize_money


@transaction.atomic
def record_order_earning(order):
    """Create (or refresh) the three-way payout split for a delivered order.

    Breakdown (always server-computed, never from the client):
      * Food subtotal after offer discount = order.subtotal
      * Commission% from DB (restaurant override or PlatformSetting default).
      * Restaurant payout = (food_subtotal + GST) - commission
      * Rider payout         = delivery_fee (fixed platform value)
      * Admin revenue        = commission + platform_fee
    """
    if order.status != Order.STATUS_DELIVERED:
        return None

    restaurant = order.restaurant
    food_subtotal = quantize_money(order.subtotal - order.discount_amount)
    if food_subtotal <= Decimal("0.00"):
        food_subtotal = quantize_money(order.subtotal)
    percent = restaurant.commission_rate
    commission = quantize_money(food_subtotal * percent / Decimal("100"))
    tax_amount = quantize_money(order.tax_amount)
    delivery_fee = quantize_money(order.delivery_fee)
    platform_fee = quantize_money(Decimal("0.00"))
    restaurant_amount = quantize_money((food_subtotal + tax_amount) - commission)
    rider_payout = delivery_fee

    earning, _ = RestaurantEarning.objects.update_or_create(
        order=order,
        defaults={
            "restaurant": restaurant,
            "order_amount": quantize_money(order.subtotal),
            "commission_percent": percent,
            "commission_amount": commission,
            "tax_amount": tax_amount,
            "delivery_fee": delivery_fee,
            "platform_fee": platform_fee,
            "restaurant_amount": restaurant_amount,
            "rider_payout": rider_payout,
            "status": "pending",
        },
    )
    return earning


@transaction.atomic
def cancel_order_earning(order):
    """Drop a pending earning when an order never completes."""
    updated = RestaurantEarning.objects.filter(
        order=order,
        status="pending",
    ).update(status="cancelled")
    return bool(updated)


def restaurant_earnings_queryset(restaurant):
    return RestaurantEarning.objects.filter(restaurant=restaurant).exclude(status="cancelled")


def earnings_summary(restaurant, today=None):
    """Return today / week / month / lifetime totals for a restaurant."""
    today = today or timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def total_between(start):
        result = restaurant_earnings_queryset(restaurant).filter(
            created_at__date__gte=start
        ).aggregate(
            gross=Sum("order_amount"),
            commission=Sum("commission_amount"),
            net=Sum("restaurant_amount"),
            orders=Count("id"),
        )
        return {
            "gross": quantize_money(result["gross"] or 0),
            "commission": quantize_money(result["commission"] or 0),
            "net": quantize_money(result["net"] or 0),
            "orders": result["orders"] or 0,
        }

    return {
        "today": total_between(today),
        "week": total_between(week_start),
        "month": total_between(month_start),
        "total": total_between(date(1970, 1, 1)),
    }


def payments_summary(restaurant):
    """Money picture used by both the earnings and payments screens."""
    from payments.models import Payment

    earnings = restaurant_earnings_queryset(restaurant)
    totals = earnings.aggregate(
        gross=Sum("order_amount"),
        commission=Sum("commission_amount"),
        net=Sum("restaurant_amount"),
    )
    settled = earnings.filter(status="settled").aggregate(net=Sum("restaurant_amount"))
    paid_settlements = Settlement.objects.filter(
        restaurant=restaurant,
        status="paid",
    ).aggregate(total=Sum("net_amount"))
    refunds = Payment.objects.filter(order__restaurant=restaurant).aggregate(
        total=Sum("refund_amount")
    )

    net_total = quantize_money(totals["net"] or 0)
    paid_total = quantize_money(paid_settlements["total"] or 0)
    return {
        "total_sales": quantize_money(totals["gross"] or 0),
        "total_commission": quantize_money(totals["commission"] or 0),
        "total_refunds": quantize_money(refunds["total"] or 0),
        "net_earnings": net_total,
        "settled_earnings": quantize_money(settled["net"] or 0),
        "pending_settlement": quantize_money(net_total - paid_total),
        "paid_settlement": paid_total,
    }


def restaurant_analytics(restaurant, days=30):
    """Aggregate the numbers the analytics page charts."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    orders = Order.objects.filter(restaurant=restaurant, created_at__date__gte=start)

    daily = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_orders = orders.filter(created_at__date=day)
        day_revenue = day_orders.exclude(status=Order.STATUS_REJECTED).aggregate(
            total=Sum("total_price")
        )["total"]
        daily.append({
            "date": day.isoformat(),
            "orders": day_orders.count(),
            "revenue": float(quantize_money(day_revenue or 0)),
        })

    top_items = (
        restaurant.order_items.exclude(order__status=Order.STATUS_REJECTED)
        .values("name")
        .annotate(orders=Count("id"), quantity=Sum("quantity"))
        .order_by("-quantity")[:8]
    )

    completed = orders.filter(status=Order.STATUS_DELIVERED).count()
    cancelled = orders.filter(status=Order.STATUS_CANCELLED).count()
    rejected = orders.filter(status=Order.STATUS_REJECTED).count()
    delivered_orders = orders.filter(status=Order.STATUS_DELIVERED)
    average_order_value = delivered_orders.aggregate(value=Avg("total_price"))["value"]

    return {
        "range_days": days,
        "orders": orders.count(),
        "completed": completed,
        "cancelled": cancelled,
        "rejected": rejected,
        "revenue": float(
            quantize_money(
                delivered_orders.aggregate(total=Sum("total_price"))["total"] or 0
            )
        ),
        "average_order_value": float(quantize_money(average_order_value or 0)),
        "average_rating": restaurant.average_rating,
        "daily": daily,
        "top_items": [
            {
                "name": item["name"],
                "orders": item["orders"],
                "quantity": item["quantity"] or 0,
            }
            for item in top_items
        ],
        "status_breakdown": [
            {"status": label, "count": count}
            for label, count in (
                ("delivered", completed),
                ("cancelled", cancelled),
                ("rejected", rejected),
                ("live", orders.exclude(status__in=Order.CLOSED_STATUSES).count()),
            )
        ],
    }
