from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.views.generic.base import RedirectView
from store.views import store_home

def healthz(request):
    """
    فحص خفيف لحالة container الـ web — بيرجع 200 بس لو Django فعليًا
    قادر يستقبل طلبات (مش بس الـ process بدأ). مقصود إنه من غير أي
    اعتماد على قاعدة البيانات، عشان يفرّق بين "web جاهز" و"db مش جاهزة"
    (الانتظار على الداتابيز أصلًا متكفّل بيه entrypoint.sh قبل ما gunicorn يشتغل).
    """
    return HttpResponse('ok')

def home(request):
    # الصفحة الرئيسية (/) هي "Biozone" نفسها — بتعرض محتوى المتجر مباشرة
    # (استدعاء الفيو نفسه، مش إعادة توجيه) عشان تبقى صفحة حقيقية قابلة
    # للفهرسة من جوجل مستقبلًا (تهيئة لـ SEO). لو عايز تفتح /store/ بنفسك
    # لسه شغالة برضو (نفس الفيو)، بس الدومين الرئيسي دلوقتي بيعرض المحتوى
    # فورًا من غير أي redirect.
    if request.user.is_authenticated and request.user.role in ['ADMIN', 'WAREHOUSE']:
        return redirect('staff:dashboard')
    return store_home(request)

class LegacyCatalogRedirect(RedirectView):
    """تحويل دائم (301) لأي رابط قديم كان بادئ بـ /catalog/ إلى /store/
    المكافئ له، حفاظًا على أي روابط محفوظة عند العملاء أو مفهرسة في جوجل
    من قبل إعادة التسمية."""
    permanent = True
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        subpath = kwargs.get('subpath', '')
        return f'/store/{subpath}'

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('staff/', include('staff.urls')),
    path('store/', include('store.urls')),
    path('catalog/', LegacyCatalogRedirect.as_view()),
    path('catalog/<path:subpath>', LegacyCatalogRedirect.as_view()),
    path('', include('orders.urls')),
    path('invoices/', include('invoices.urls')),
    path('notifications/', include('notifications.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
    except ImportError:
        pass
