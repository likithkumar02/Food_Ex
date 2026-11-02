from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .services import PaymentProcessingError, PaymentService


class OrderPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        if request.user.role != "customer":
            return Response({"detail": "Customer account required."}, status=403)
        order = get_object_or_404(Order, pk=order_id, user=request.user)
        if order.status == "cancelled":
            return Response({"detail": "Cancelled orders cannot be paid."}, status=400)
        try:
            payment = PaymentService.process(
                order,
                request.data.get("payment_method", ""),
            )
        except PaymentProcessingError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "payment_id": payment.pk,
                "status": payment.status,
                "payment_method": payment.payment_method,
                "transaction_id": payment.transaction_id,
            },
            status=status.HTTP_201_CREATED,
        )