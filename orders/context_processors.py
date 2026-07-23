from .models import SiteConfig


def site_config(request):
    """
    بيحقن إعدادات الموقع (SiteConfig) في كل الصفحات — نفس فكرة
    notifications.context_processors.notifications — عشان templates زي
    كارت المنتج في المتجر تقدر تشوف site_config.show_discounted_prices
    من غير ما كل view يجيبها ويبعتها بنفسه.
    """
    return {'site_config': SiteConfig.get_solo()}


def cart_count(request):
    """
    عدد أصناف السلة النشطة — بعد ما بقت السلة متخزنة في الداتابيز (مش
    السيشن)، الـ badge في الـ navbar (base.html) محتاج المصدر ده بدل
    ما كان بياخد request.session.cart|length على طول. بيتحسب بس للعميل
    المسجّل دخوله (نفس شرط new_arrivals_count).
    """
    user = getattr(request, 'user', None)
    if user and user.is_authenticated and user.role == 'CLIENT':
        from .cart import Cart
        return {'cart_count': len(Cart(request))}
    return {}
