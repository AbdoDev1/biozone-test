from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

__all__ = ['client_required']


def client_required(view_func):
    """
    بوابة موحّدة لكل عمليات السلة والطلبات: لازم المستخدم يكون مسجّل دخول،
    ودوره CLIENT، وحالته ACTIVE. استخدام decorator واحد بدل تكرار نفس
    الفحص يدويًا في كل دالة يمنع نسيانه بالغلط في دالة جديدة مستقبلًا
    (زي ما حصل مع cart_update/remove/plus/minus).
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'CLIENT' or request.user.status != 'ACTIVE':
            messages.error(request, 'ليست لديك صلاحية للوصول إلى هذه الصفحة.')
            return redirect('store:home')
        return view_func(request, *args, **kwargs)
    return wrapper
