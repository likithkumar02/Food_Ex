from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurant.models import MenuItem

from .models import (
    MAX_CART_ITEM_QUANTITY,
    Cart,
    CartItem,
    Order,
    OrderStatusEvent,
)
from .serializers import OrderCreateSerializer, OrderSerializer
from .services import (
    CartCheckoutError,
    compute_order_totals,
    create_order_from_cart,
    resolve_offer,
)


def customer_only(request):
    return request.user.role == "customer"


def cart_payload(cart):
    items = [
        {
            "id": item.pk,
            "menu_item_id": item.menu_item_id,
            "name": item.menu_item.name,
            "restaurant": item.menu_item.restaurant.name,
            "restaurant_id": item.menu_item.restaurant_id,
            "quantity": item.quantity,
            "unit_price": item.menu_item.price,
            "subtotal": item.subtotal,
        }
        for item in cart.items.select_related("menu_item__restaurant")
    ]
    return {
        "items": items,
        "total_items": cart.total_items,
        "subtotal": cart.total_price,
    }


class CartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not customer_only(request):
            return Response({"detail": "Customer account required."}, status=403)
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(cart_payload(cart))

    def post(self, request):
        if not customer_only(request):
            return Response({"detail": "Customer account required."}, status=403)
        try:
            menu_item_id = int(request.data.get("menu_item_id"))
            quantity = int(request.data.get("quantity", 1))
        except (TypeError, ValueError):
            return Response({"detail": "Valid menu_item_id and quantity are required."}, status=400)
        if quantity < 1 or quantity > MAX_CART_ITEM_QUANTITY:
            return Response(
                {"detail": f"Quantity must be between 1 and {MAX_CART_ITEM_QUANTITY}."},
                status=400,
            )

        item = get_object_or_404(
            MenuItem.objects.select_related("restaurant"),
            pk=menu_item_id,
            is_available=True,
            restaurant__status="approved",
            restaurant__is_active=True,
            restaurant__is_open=True,
        )
        with transaction.atomic():
            cart, _ = Cart.objects.select_for_update().get_or_create(user=request.user)
            if cart.items.exclude(menu_item__restaurant=item.restaurant).exists():
                return Response(
                    {"detail": "A cart can contain items from one restaurant at a time."},
                    status=status.HTTP_409_CONFLICT,
                )
            cart_item, created = CartItem.objects.select_for_update().get_or_create(
                cart=cart,
                menu_item=item,
                defaults={"quantity": quantity},
            )
            if not created:
                if cart_item.quantity + quantity > MAX_CART_ITEM_QUANTITY:
                    return Response(
                        {"detail": f"Maximum quantity per item is {MAX_CART_ITEM_QUANTITY}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                cart_item.quantity += quantity
                cart_item.save(update_fields=["quantity"])
        return Response({"id": cart_item.pk, "quantity": cart_item.quantity}, status=201)


class CartItemAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _item(self, request, item_id):
        if not customer_only(request):
            return None
        return CartItem.objects.filter(pk=item_id, cart__user=request.user).first()

    def patch(self, request, item_id):
        item = self._item(request, item_id)
        if item is None:
            return Response({"detail": "Cart item not found."}, status=404)
        try:
            quantity = int(request.data.get("quantity"))
        except (TypeError, ValueError):
            return Response({"detail": "A valid quantity is required."}, status=400)
        if quantity < 1 or quantity > MAX_CART_ITEM_QUANTITY:
            return Response(
                {"detail": f"Quantity must be between 1 and {MAX_CART_ITEM_QUANTITY}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return Response({"id": item.pk, "quantity": item.quantity, "subtotal": item.subtotal})

    def delete(self, request, item_id):
        item = self._item(request, item_id)
        if item is None:
            return Response({"detail": "Cart item not found."}, status=404)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutSummaryAPIView(APIView):
    """Server-computed bill preview so the client never calculates money."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not customer_only(request):
            return Response({"detail": "Customer account required."}, status=403)
        cart, _ = Cart.objects.get_or_create(user=request.user)
        subtotal = cart.total_price
        offer_code = request.query_params.get("offer_code", "")
        first_item = cart.items.select_related("menu_item__restaurant").first()
        restaurant = first_item.menu_item.restaurant if first_item else None

        offer = None
        error = ""
        if offer_code and restaurant:
            try:
                offer = resolve_offer(restaurant, offer_code, subtotal)
            except CartCheckoutError as exc:
                error = str(exc)

        totals = compute_order_totals(subtotal, offer)
        return Response({
            "subtotal": totals["subtotal"],
            "discount_amount": totals["discount_amount"],
            "tax_amount": totals["tax_amount"],
            "delivery_fee": totals["delivery_fee"],
            "total_price": totals["total_price"],
            "offer": offer.name if offer else None,
            "offer_error": error,
        })


class OrderListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not customer_only(request):
            return Response({"detail": "Customer account required."}, status=403)
        orders = (
            Order.objects.filter(user=request.user)
            .select_related("restaurant")
            .prefetch_related("items")
        )
        return Response(OrderSerializer(orders, many=True).data)

    def post(self, request):
        if not customer_only(request):
            return Response({"detail": "Customer account required."}, status=403)
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            order = create_order_from_cart(
                request.user,
                serializer.validated_data["delivery_address"],
                serializer.validated_data.get("delivery_latitude"),
                serializer.validated_data.get("delivery_longitude"),
                serializer.validated_data.get("offer_code") or None,
                address_id=serializer.validated_data.get("address_id"),
            )
        except CartCheckoutError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        if not customer_only(request):
            return Response({"detail": "Customer account required."}, status=403)
        order = get_object_or_404(
            Order.objects.select_related("restaurant").prefetch_related("items"),
            pk=order_id,
            user=request.user,
        )
        return Response(OrderSerializer(order).data)


ORDER_TIMELINE = [
    Order.STATUS_PLACED,
    Order.STATUS_ACCEPTED,
    Order.STATUS_PREPARING,
    Order.STATUS_READY,
    Order.STATUS_FINDING_PARTNER,
    Order.STATUS_DELIVERY_ASSIGNED,
    Order.STATUS_DELIVERY_PARTNER_ASSIGNED,
    Order.STATUS_ARRIVED_AT_PICKUP,
    Order.STATUS_PICKED_UP,
    Order.STATUS_OUT_FOR_DELIVERY,
    Order.STATUS_DELIVERED,
]


class OrderStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        if not customer_only(request):
            return Response({"detail": "Customer account required."}, status=403)
        order = get_object_or_404(Order, pk=order_id, user=request.user)
        if order.status in (
            Order.STATUS_READY,
            Order.STATUS_FINDING_PARTNER,
            Order.STATUS_DELIVERY_ASSIGNED,
        ):
            from delivery.services import assign_ready_order

            assign_ready_order(order)
        order = get_object_or_404(
            Order.objects.select_related("restaurant"),
            pk=order_id,
            user=request.user,
        )
        assignment = getattr(order, "delivery_assignment", None)
        location = None
        partner = None
        if assignment:
            partner = assignment.partner.get_full_name() or assignment.partner.username
            latest_location = assignment.locations.first()
            if (
                latest_location
                and order.status in (
                    Order.STATUS_DELIVERY_PARTNER_ASSIGNED,
                    Order.STATUS_ARRIVED_AT_PICKUP,
                    Order.STATUS_PICKED_UP,
                    Order.STATUS_OUT_FOR_DELIVERY,
                )
            ):
                location = {
                    "latitude": latest_location.latitude,
                    "longitude": latest_location.longitude,
                    "recorded_at": latest_location.recorded_at,
                }

        states = ORDER_TIMELINE
        if order.status in (Order.STATUS_CANCELLED, Order.STATUS_REJECTED):
            states = [Order.STATUS_PLACED, order.status]
        elif order.status == Order.STATUS_ASSIGNMENT_FAILED:
            states = [
                *ORDER_TIMELINE[:ORDER_TIMELINE.index(Order.STATUS_DELIVERY_ASSIGNED) + 1],
                Order.STATUS_ASSIGNMENT_FAILED,
            ]
        current_index = states.index(order.status) if order.status in states else -1
        labels = dict(Order.STATUS_CHOICES)
        status_events = {}
        for event in OrderStatusEvent.objects.filter(order=order).order_by("created_at", "pk"):
            status_events[event.to_status] = event.created_at
        timestamps = {
            Order.STATUS_PLACED: order.created_at,
            Order.STATUS_ACCEPTED: order.accepted_at,
            Order.STATUS_PREPARING: order.preparing_at,
            Order.STATUS_READY: order.ready_at,
            Order.STATUS_DELIVERY_ASSIGNED: order.delivery_assigned_at,
            Order.STATUS_DELIVERY_PARTNER_ASSIGNED: order.delivery_partner_assigned_at,
            Order.STATUS_ARRIVED_AT_PICKUP: order.arrived_at_pickup_at,
            Order.STATUS_PICKED_UP: order.picked_up_at,
            Order.STATUS_DELIVERED: order.delivered_at,
        }
        return Response({
            "order_id": order.pk,
            "code": order.code,
            "status": order.status,
            "status_display": order.get_status_display(),
            "restaurant": order.restaurant.name,
            "delivery_partner": partner,
            "delivery_location": location,
            "timeline": [
                {
                    "status": state,
                    "label": labels.get(state, state),
                    "complete": index <= current_index,
                    "current": index == current_index,
                    "timestamp": (
                        status_events.get(state) or timestamps.get(state)
                    ).isoformat()
                    if status_events.get(state) or timestamps.get(state)
                    else None,
                }
                for index, state in enumerate(states)
            ],
        })
