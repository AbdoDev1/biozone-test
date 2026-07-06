from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404

from .models import Invoice


def _is_staff(user):
    return user.is_authenticated and user.role in ['ADMIN', 'WAREHOUSE']


@login_required
def invoice_print(request, pk):
    """
    عرض الفاتورة بشكل مبسّط جاهز للطباعة (زرار Print بيستخدم window.print()).
    الستاف يشوف أي فاتورة، والعميل يشوف بس فواتيره هو.
    """
    invoice = get_object_or_404(
        Invoice.objects.select_related('order', 'order__client').prefetch_related('items'),
        pk=pk,
    )

    if not _is_staff(request.user) and invoice.order.client_id != request.user.id:
        raise PermissionDenied('مينفعش تشوف فاتورة عميل تاني.')

    return render(request, 'invoices/print.html', {'invoice': invoice})
