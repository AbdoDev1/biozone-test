from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import RegisterForm, LoginForm
from .models import User


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
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user:
                # موظف حاول يدخل من بوابة العملاء
                if user.role in ['ADMIN', 'WAREHOUSE']:
                    messages.error(request, 'يرجى تسجيل الدخول من صفحة دخول الموظفين.')
                    return render(request, 'accounts/login.html', {'form': form})

                if user.status == User.Status.PENDING:
                    messages.warning(request, 'حسابك في انتظار موافقة الإدارة.')
                    return redirect('accounts:pending')
                elif user.status == User.Status.REJECTED:
                    messages.error(request, 'تم رفض طلب تسجيلك.')
                else:
                    login(request, user)
                    return redirect('store:home')
            else:
                messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة.')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


def pending_view(request):
    return render(request, 'accounts/pending.html')


def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    if request.user.role in ['ADMIN', 'WAREHOUSE']:
        return redirect('staff:dashboard')

    from decimal import Decimal
    from accounting.models import AccountTransaction

    transactions = AccountTransaction.objects.filter(client=request.user).select_related('invoice')
    balance = AccountTransaction.balance_for(request.user)

    running = Decimal('0')
    statement = []
    for tx in transactions:
        running += tx.amount
        statement.append({'tx': tx, 'running_balance': running})
    statement.reverse()  # الأحدث فوق للعميل

    return render(request, 'accounts/dashboard.html', {
        'balance': balance,
        'balance_abs': abs(balance),
        'statement': statement,
    })
