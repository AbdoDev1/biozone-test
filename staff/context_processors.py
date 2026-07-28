from django.urls import reverse

from .navigation import NAV_ITEMS


def staff_nav(request):
    """
    قائمة عناصر تنقل لوحة الموظف بعد تصفيتها حسب صلاحيات المستخدم الحالي
    — مصدر واحد يستخدمه كل من السايدبار (staff/base.html) وشبكة التطبيقات
    في الصفحة الرئيسية (staff/dashboard.html)، بدل ما كل واجهة تكرر نفس
    شروط الصلاحية بشكل منفصل (راجع staff/navigation.py لتعريف العناصر).

    بيتحسب بس لصفحات لوحة الموظف (namespace='staff') لمستخدم مسجّل دخوله
    — وإلا بيرجع dict فاضي من غير أي تكلفة إضافية على باقي الموقع (نفس
    أسلوب store.context_processors.new_arrivals_count).
    """
    resolver_match = request.resolver_match
    if not (resolver_match and resolver_match.namespace == 'staff'):
        return {}
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated):
        return {}

    url_name = resolver_match.url_name
    items = []
    for item in NAV_ITEMS:
        if item['admin_only'] and user.role != 'ADMIN':
            continue
        if item['perm'] and not user.has_perm(item['perm']):
            continue
        items.append({
            **item,
            'url': reverse(f"staff:{item['url_name']}"),
            'is_active': url_name in item['active_url_names'],
        })
    return {'staff_nav_items': items}
