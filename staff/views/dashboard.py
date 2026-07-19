from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from inventory.models import Inventory
from accounts.models import ClientProfile
from accounts.security import is_login_blocked, record_failed_login, reset_login_attempts
from orders.models import Order

# أول قدر أصناف بيتعرضوا في كارت "مخزون منخفض" بلوحة التحكم — الباقي
# يتشاف من صفحة المخزون كاملة (مرقّمة) عن طريق رابط "عرض الكل".
DASHBOARD_LOW_STOCK_LIMIT = 10


def staff_login(request):
    if request.user.is_authenticated:
        if request.user.role in ['ADMIN', 'WAREHOUSE']:
            return redirect('staff:dashboard')
        return redirect('store:home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # نفس حماية brute-force المستخدمة في بوابة العملاء (accounts/security.py).
        if is_login_blocked(request, username):
            messages.error(
                request,
                'محاولات دخول كتيرة فشلت. حاول تاني بعد ربع ساعة تقريبًا.'
            )
            return render(request, 'staff/login.html')

        user = authenticate(request, username=username, password=password)
        if user and user.role in ['ADMIN', 'WAREHOUSE']:
            reset_login_attempts(request, username)
            login(request, user)
            return redirect('staff:dashboard')
        else:
            # رسالة موحّدة (بيانات خاطئة) سواء كان اليوزرنيم مش موجود، الباسورد
            # غلط، أو حساب عميل حاول يدخل من هنا — عشان منسربش أي معلومة عن
            # وجود/نوع الحساب لحد بيجرّب يوزرنيمات عشوائي.
            record_failed_login(request, username)
            messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة.')

    return render(request, 'staff/login.html')


def staff_logout(request):
    # POST بس، بنفس منطق accounts:logout (تفصيل في accounts/views.py).
    if request.method != 'POST':
        return redirect('staff:dashboard')
    logout(request)
    return redirect('staff:login')

@login_required
def dashboard(request):
    if request.user.role not in ['ADMIN', 'WAREHOUSE']:
        return redirect('store:home')

    total_products = Inventory.objects.count()
    # الصفحة دي بتتفتح كتير جدًا يوميًا (كل ما موظف يسجّل دخول/يرجع للوحة
    # التحكم)، فمينفعش نجيب كل أصناف المخزون المنخفض من غير حد أقصى —
    # ده كان بيبطّئ الصفحة تدريجيًا مع نمو الكتالوج. بنعرض هنا أول
    # DASHBOARD_LOW_STOCK_LIMIT بس، والعدد الحقيقي بييجي من .count()
    # منفصل (مش من len() على queryset كامل)، ولو حابب تشوف الباقي فيه
    # رابط لصفحة المخزون كاملة (مرقّمة) فلترة "منخفض بس".
    low_stock_qs = Inventory.objects.select_related(
        'product'
    ).filter(quantity__lte=models.F('reserved') + models.F('min_quantity')).order_by('quantity')
    low_stock_count = low_stock_qs.count()
    low_stock = low_stock_qs[:DASHBOARD_LOW_STOCK_LIMIT]
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
        'low_stock_count': low_stock_count,
        'pending_clients': pending_clients,
        'recent_orders': recent_orders,
        'unopened_orders_count': unopened_orders_count,
        'active_orders_count': active_orders.count(),
    }
    return render(request, 'staff/dashboard.html', context)
