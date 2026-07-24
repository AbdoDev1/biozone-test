from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import RegisterForm, LoginForm
from .models import User
from .security import is_login_blocked, record_failed_login, reset_login_attempts


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            client = form.save()
            from notifications.services import notify_staff_with_perm
            from notifications.models import Notification
            notify_staff_with_perm(
                'accounts.change_clientprofile',
                kind=Notification.Kind.NEW_CLIENT_REGISTRATION,
                title='طلب تسجيل عميل جديد',
                message=f'العميل {client.username} قدّم طلب تسجيل وبانتظار المراجعة.',
                url_name='staff:clients',
            )
            messages.success(request, 'تم إرسال طلب التسجيل، انتظر موافقة الإدارة.')
            return redirect('accounts:pending')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    # لو موظف حاول يدخل من هنا نرفضه
    if request.user.is_authenticated:
        if request.user.role in ['ADMIN', 'WAREHOUSE']:
            return redirect('staff:dashboard')
        return redirect('store:home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']

            # حماية بسيطة ضد brute-force: بعد عدد محاولات فاشلة كبير على
            # نفس (IP + username) بنوقف قبول المحاولات مؤقتًا.
            if is_login_blocked(request, username):
                messages.error(
                    request,
                    'محاولات دخول كتيرة فشلت. حاول تاني بعد ربع ساعة تقريبًا.'
                )
                return render(request, 'accounts/login.html', {'form': form})

            user = authenticate(
                request,
                username=username,
                password=form.cleaned_data['password'],
            )
            if user:
                # موظف حاول يدخل من بوابة العملاء — رسالة عامة موحّدة
                # (نفس رسالة "بيانات خاطئة") عشان منسربش إن اليوزرنيم ده
                # حساب موظف لحد بيجرّب يوزرنيمات عشوائي. مفيش عقاب هنا
                # لأن الباسورد كان فعلًا صح.
                if user.role in ['ADMIN', 'WAREHOUSE']:
                    messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة.')
                    return render(request, 'accounts/login.html', {'form': form})

                if user.status == User.Status.PENDING:
                    reset_login_attempts(request, username)
                    messages.warning(request, 'حسابك في انتظار موافقة الإدارة.')
                    return redirect('accounts:pending')
                elif user.status == User.Status.REJECTED:
                    reset_login_attempts(request, username)
                    messages.error(request, 'تم رفض طلب تسجيلك.')
                else:
                    reset_login_attempts(request, username)
                    login(request, user)
                    return redirect('store:home')
            else:
                record_failed_login(request, username)
                messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة.')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    # تسجيل الخروج لازم يكون POST بس (مش GET) عشان رابط خارجي (زي <img>
    # أو <a> مخفي) مايقدرش "يسجّل خروج" المستخدم من غير رضاه.
    if request.method != 'POST':
        return redirect('store:home')
    logout(request)
    return redirect('home')


def pending_view(request):
    return render(request, 'accounts/pending.html')


ACCOUNT_STATEMENT_PAGE_SIZE = 30


ORDERS_TAB_PAGE_SIZE = 10


def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    if request.user.role in ['ADMIN', 'WAREHOUSE']:
        return redirect('staff:dashboard')

    from django.core.paginator import Paginator
    from django.contrib.auth import update_session_auth_hash
    from django.db.models import F, Sum, Window
    from accounting.models import AccountTransaction
    from orders.models import Order
    from .forms import ClientPasswordChangeForm

    # ---- تغيير كلمة المرور (تبويب الأمان) ----
    # فورم مستقل بيتبعت لنفس الصفحة؛ لو الطلب مش خاص بيه (تبويبات باقي
    # الصفحة) بنجهزه فاضي عادي عشان يتعرض في التبويب من غير أخطاء.
    password_form = ClientPasswordChangeForm(user=request.user)
    if request.method == 'POST' and request.POST.get('form') == 'password':
        password_form = ClientPasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # يمنع تسجيل الخروج التلقائي بعد التغيير
            messages.success(request, 'تم تغيير كلمة المرور بنجاح.')
            return redirect('accounts:dashboard')

    # ---- الرصيد التراكمي بعد كل حركة (كشف الحساب) ----
    # الرصيد التراكمي بعد كل حركة كان بيتحسب بالكامل في بايثون (بيجيب كل
    # حركات العميل من غير ترقيم صفحات ويلف عليها سطر بسطر) — ده كان بيبطّئ
    # الصفحة تدريجيًا مع الوقت لأي عميل قديم عنده آلاف الحركات.
    # الحل: نسيب قاعدة البيانات نفسها تحسب الرصيد التراكمي (window function
    # Sum بترتيب زمني) في نفس الاستعلام، وبعدين نرقّم الصفحات عادي — مفيش
    # تحميل لكل السجل في الذاكرة، والرصيد صحيح حتى في نص السجل القديم.
    transactions = AccountTransaction.objects.filter(
        client=request.user
    ).select_related('invoice').annotate(
        running_balance=Window(
            expression=Sum('amount'),
            order_by=[F('created_at').asc(), F('id').asc()],
        )
    ).order_by('-created_at', '-id')  # الأحدث فوق للعميل

    paginator = Paginator(transactions, ACCOUNT_STATEMENT_PAGE_SIZE)
    # ملحوظة: تبويب كشف الحساب بيستخدم باراميتر ?page مستقل (statement_page)
    # عشان مايتعارضش مع باراميتر صفحات تبويب الطلبات لو الاتنين اتفعّلوا
    # مع بعض في نفس الرابط.
    page_obj = paginator.get_page(request.GET.get('statement_page'))

    balance = AccountTransaction.balance_for(request.user)

    # ---- الطلبات (نظرة عامة + تبويب الطلبات) ----
    orders_qs = Order.objects.filter(client=request.user).prefetch_related('items').order_by('-created_at')
    recent_orders = orders_qs[:5]

    orders_paginator = Paginator(orders_qs, ORDERS_TAB_PAGE_SIZE)
    orders_page_obj = orders_paginator.get_page(request.GET.get('orders_page'))

    return render(request, 'accounts/dashboard.html', {
        'balance': balance,
        'balance_abs': abs(balance),
        'statement': page_obj,
        'page_obj': page_obj,
        'recent_orders': recent_orders,
        'orders_page_obj': orders_page_obj,
        'password_form': password_form,
    })
