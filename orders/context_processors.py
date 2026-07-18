from .models import SiteConfig


def site_config(request):
    """
    بيحقن إعدادات الموقع (SiteConfig) في كل الصفحات — نفس فكرة
    notifications.context_processors.notifications — عشان templates زي
    كارت المنتج في المتجر تقدر تشوف site_config.show_discounted_prices
    من غير ما كل view يجيبها ويبعتها بنفسه.
    """
    return {'site_config': SiteConfig.get_solo()}
