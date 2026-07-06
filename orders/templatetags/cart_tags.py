from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(str(key))


@register.filter
def sub(value, arg):
    try:
        return value - arg
    except (TypeError, ValueError):
        return None


@register.filter
def price_for_client(unit, user):
    """سعر الوحدة الفعلي حسب حالة العميل (جملة/قطاعي) — للاستخدام في المتجر."""
    if unit is None:
        return None
    client = user if getattr(user, 'is_authenticated', False) else None
    return unit.get_price_for_client(client)


def _client_of(user):
    return user if getattr(user, 'is_authenticated', False) else None


@register.filter
def units_for_client(product, user):
    """الوحدة (أو الوحدات) المفروض تظهر لهذا العميل — انظر Product.units_for_client."""
    if product is None:
        return []
    return product.units_for_client(_client_of(user))


@register.filter
def is_wholesale_user(user):
    """هل هذا المستخدم عميل جملة؟ — لتبسيط الشرط في التمبليت."""
    profile = getattr(user, 'client_profile', None)
    return bool(profile and profile.is_wholesale)
