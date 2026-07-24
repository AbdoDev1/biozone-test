from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# أيقونات جاهزة تتحدد بالاسم في {% btn icon="check" %} بدل كتابة SVG خام في كل تمبليت.
# نفس مسارات الـ SVG المستخدمة فعليًا في الطلبات (تأكيد/تسليم/طباعة) عشان الشكل يفضل موحّد.
ICONS = {
    'check': '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>',
    'truck': '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.091-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 00-10.026 0 1.106 1.106 0 00-.987 1.106v7.635m12-6.677v6.677m0 0h-12"/></svg>',
    'printer': '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M6.34 18H4.5A2.25 2.25 0 012.25 15.75V9.377c0-.996.61-1.89 1.534-2.256l.847-.336M17.66 18h1.84a2.25 2.25 0 002.25-2.25v-6.373c0-.996-.61-1.89-1.534-2.256l-4.94-1.96m-9.94 1.96l4.94-1.96m5 0v-.815a2.25 2.25 0 00-1.183-1.981l-1.5-.815a2.25 2.25 0 00-2.134 0l-1.5.815a2.25 2.25 0 00-1.183 1.98v.816m5 0h-5M6.34 18l.529 4.752c.062.559.53.983 1.09.983h8.084c.559 0 1.028-.424 1.09-.983L17.66 18M6.34 18h11.32"/></svg>',
}

# خرائط: قيمة الحالة -> اسم اللون. مركزية عشان أي حالة جديدة تتضاف مكان واحد بس.
BADGE_COLOR_MAPS = {
    'order_status': {
        'PENDING': 'yellow',
        'NEEDS_APPROVAL': 'orange',
        'CONFIRMED': 'green',
        'DELIVERED': 'blue',
        'REJECTED': 'red',
    },
    'movement_type': {
        'IN': 'green',
        'OUT': 'red',
        'OUT_RESERVED': 'rose',
        'RESERVE': 'yellow',
    },
    'tx_kind': {
        'INVOICE': 'blue',
        'PAYMENT': 'green',
        'ADJUSTMENT': 'orange',
    },
    'user_status': {
        'ACTIVE': 'green',
        'PENDING': 'yellow',
        'SUSPENDED': 'red',
    },
    'employee_role': {
        'ADMIN': 'purple',
        'STAFF': 'blue',
    },
}

COLOR_CLASSES = {
    'green': 'bg-green-100 text-green-700',
    'yellow': 'bg-yellow-100 text-yellow-700',
    'orange': 'bg-orange-100 text-orange-700',
    'red': 'bg-red-100 text-red-600',
    'rose': 'bg-rose-100 text-rose-700',
    'blue': 'bg-blue-100 text-blue-700',
    'purple': 'bg-purple-100 text-purple-700',
    'gray': 'bg-gray-100 text-gray-500',
}


@register.simple_tag
def status_badge(text, group=None, key=None, color=None, size='xs'):
    """
    شارة حالة موحدة الشكل. بتحدد اللون بطريقتين:
    - group + key: بيدوّر في BADGE_COLOR_MAPS (مثلاً group="order_status" key=order.status)
    - color: تحديد اللون يدوي مباشرة (لو الحالة مش في خريطة جاهزة)
    """
    if color is None:
        color = BADGE_COLOR_MAPS.get(group, {}).get(key, 'gray')
    classes = COLOR_CLASSES.get(color, COLOR_CLASSES['gray'])
    pad = 'px-2 py-0.5' if size == 'xs' else 'px-3 py-1'
    return format_html(
        '<span class="{} {} rounded-full text-xs font-semibold">{}</span>',
        classes, pad, text,
    )


BUTTON_VARIANTS = {
    'primary': 'bg-blue-600 hover:bg-blue-700 text-white',
    'secondary': 'bg-gray-100 hover:bg-gray-200 text-gray-700',
    'danger': 'bg-red-600 hover:bg-red-700 text-white',
    'success': 'bg-green-600 hover:bg-green-700 text-white',
    'warning': 'bg-orange-500 hover:bg-orange-600 text-white',
    'caution': 'bg-yellow-500 hover:bg-yellow-600 text-white',
}

BUTTON_SIZES = {
    'sm': 'text-xs px-3 py-1.5',
    'md': 'text-sm px-4 py-2',
    'lg': 'font-semibold px-6 py-3',
}


@register.inclusion_tag('staff/components/button.html')
def btn(text, href=None, variant='primary', size='md', full_width=False,
        rounded='lg', type='button', icon=None, extra_classes='', onclick=None,
        extra_attrs=''):
    """
    زرار موحد الشكل. لو 'href' اتحدد بيتعمل <a>، غير كده <button>.
    variant: primary/secondary/danger/success — size: sm/md/lg
    icon: اسم من ICONS (زي "check"، "truck"، "printer") — مش SVG خام.
    onclick: كود JS بسيط (زي "window.print()") لو الزرار مش submit/رابط.
    extra_attrs: أي attributes إضافية خام تتحط على الـ <a>/<button> زي ما هي
                 (زي Alpine.js: @click="open = false"، x-show="..."، :disabled="...").
                 القيمة دي بتيجي من كود التمبليت (المطور) مش من مدخلات المستخدم،
                 فبتترندر من غير escaping — بنفس منطق onclick.
                 الاستخدام: {% btn "إلغاء" extra_attrs='@click="open = false"' %}
    """
    variant_classes = BUTTON_VARIANTS.get(variant, BUTTON_VARIANTS['primary'])
    size_classes = BUTTON_SIZES.get(size, BUTTON_SIZES['md'])
    rounded_class = f'rounded-{rounded}' if rounded else ''
    classes = f'{variant_classes} {size_classes} {rounded_class} transition inline-flex items-center justify-center gap-1.5 font-semibold {extra_classes}'
    if full_width:
        classes = f'w-full {classes}'
    icon_html = mark_safe(ICONS[icon]) if icon in ICONS else ''
    return {
        'text': text,
        'href': href,
        'classes': classes,
        'type': type,
        'icon': icon_html,
        'onclick': onclick,
        'extra_attrs': mark_safe(extra_attrs) if extra_attrs else '',
    }


@register.filter
def without_page(querydict):
    """
    بترجع نسخة urlencoded من QueryDict الفلاتر الحالية من غير مفتاح 'page' —
    عشان روابط الصفحات (pagination) في تقارير قسم reports تقدر تضيف page=N
    بتاعها من غير ما يتكرر المفتاح أو يتعارض مع رقم صفحة سابق في الرابط.
    الاستخدام: <a href="?{{ request.GET|without_page }}&page={{ n }}">
    """
    qd = querydict.copy()
    qd.pop('page', None)
    return qd.urlencode()


@register.simple_tag(takes_context=True)
def crumb(context, label, url_name=None, *url_args, url=None):
    """
    عنصر واحد في مسار التنقل (breadcrumbs). لو 'url_name' اتحدد بيتعمل رابط
    ومعاه سهم فاصل بعده؛ من غيره بيتعرض كنص الصفحة الحالية (آخر عنصر في المسار).
    الاستخدام: {% crumb "المخزون" "staff:inventory" %} ... {% crumb item.name %}

    لو 'url' اتحدد صراحة (رابط جاهز، ممكن يكون معاه querystring زي
    ?page=3&q=...) بيتستخدم زي ما هو من غير reverse — عشان روابط الرجوع
    اللي لازم تحافظ على رقم الصفحة/البحث بتاع القائمة اللي جاي منها
    المستخدم (شوف staff.utils.url_with_qs).
    """
    if url_name and url is None:
        try:
            from django.urls import reverse
            url = reverse(url_name, args=url_args) if url_args else reverse(url_name)
        except Exception:
            url = '#'
    if url:
        return format_html(
            '<a href="{}" class="hover:text-blue-600 hover:underline">{}</a>'
            '<svg class="w-3.5 h-3.5 inline-block mx-1 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5"/></svg>',
            url, label,
        )
    return format_html('<span class="text-gray-700 font-medium">{}</span>', label)
