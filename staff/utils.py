from django.http import HttpResponseRedirect
from django.urls import reverse


def list_qs(request):
    """
    querystring الحالي (page/q/category/low...) من الطلب — بنستخدمه عشان
    نقدر نحافظ على مكان المستخدم في القائمة (رقم الصفحة، البحث، الفلتر)
    وهو بيتنقل لصفحة تفاصيل/تعديل صنف ويرجع تاني، بدل ما يرجع دايمًا
    لصفحة 1 من غير أي فلتر (المشكلة اللي كانت موجودة قبل كده).
    """
    return request.GET.urlencode()


def url_with_qs(request, url_name, *args, **kwargs):
    """بيبني رابط لـ url_name مع نفس querystring الحالي (لو موجود)."""
    url = reverse(url_name, args=args, kwargs=kwargs)
    qs = list_qs(request)
    return f'{url}?{qs}' if qs else url


def redirect_with_qs(request, url_name, *args, **kwargs):
    """
    زي django.shortcuts.redirect، لكن بيحافظ على querystring الطلب الحالي
    (بيانات الفلتر/الصفحة) على الرابط الجديد. مستخدم بعد أي POST من صفحة
    تفاصيل/تعديل عنصر، عشان لو رجع المستخدم لنفس الصفحة تاني يفضل رابط
    "الرجوع للقائمة" شغال بنفس الصفحة/الفلتر اللي كان عليه.
    """
    return HttpResponseRedirect(url_with_qs(request, url_name, *args, **kwargs))
