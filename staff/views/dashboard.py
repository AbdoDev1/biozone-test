from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from inventory.models import Inventory
from accounts.models import ClientProfile
from orders.models import Order


def staff_login(request):
    if request.user.is_authenticated:
        if request.user.role in ['ADMIN', 'WAREHOUSE']:
            return redirect('staff:dashboard')
        return redirect('store:home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            if user.role in ['ADMIN', 'WAREHOUSE']:
                login(request, user)
                return redirect('staff:dashboard')
            else:
                messages.error(request, 'يرجى تسجيل الدخول من صفحة العملاء.')
        else:
            messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة.')

    return render(request, 'staff/login.html')


def staff_logout(request):
    logout(request)
    return redirect('staff:login')

@login_required
def dashboard(request):
    if request.user.role not in ['ADMIN', 'WAREHOUSE']:
        return redirect('store:home')

    total_products = Inventory.objects.count()
    low_stock = Inventory.objects.select_related(
        'product'
    ).filter(quantity__lte=models.F('reserved') + models.F('min_quantity'))
    pending_clients = ClientProfile.objects.filter(user__status='PENDING').count()

    # الطلبات النشطة (لسه مش متسلّمة ولا مرفوضة) — دي اللي محتاجة انتباه الموظف.
    # الطلبات "لسه ماتفتحتش" هي اللي ما حدش من الموظفين فتح تفاصيلها لحد دلوقتي
    # (viewed_by_staff=False)، بغض النظر عن حالتها.
    active_orders = Order.objects.exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.REJECTED]
    )
    unopened_orders_count = active_orders.filter(viewed_by_staff=False).count()
    recent_orders = active_orders.select_related('client').order_by('-created_at')[:6]

    context = {
        'total_products': total_products,
        'low_stock': low_stock,
        'pending_clients': pending_clients,
        'recent_orders': recent_orders,
        'unopened_orders_count': unopened_orders_count,
        'active_orders_count': active_orders.count(),
    }
    return render(request, 'staff/dashboard.html', context)
