from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from orders.models import Order

from .services import PaymentProcessingError, PaymentService


@role_required("customer")
def payment_page(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.payments.filter(status="paid").exists():
        return redirect("order_detail", order_id=order.pk)

    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "")
        try:
            PaymentService.process(order, payment_method)
        except PaymentProcessingError as error:
            messages.error(request, str(error))
            return render(
                request,
                "payments/payment.html",
                {
                    "order": order,
                    "test_payment_enabled": settings.PAYMENT_PROVIDER == "mock",
                },
            )
        return redirect("order_detail", order_id=order.pk)

    return render(
        request,
        "payments/payment.html",
        {
            "order": order,
            "test_payment_enabled": settings.PAYMENT_PROVIDER == "mock",
        },
    )
