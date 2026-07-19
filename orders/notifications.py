"""
منطق إشعارات الطلبات — اتفصل عن Order model (orders/models.py) عشان الموديل
يفضل مركّز على منطق دورة حياة الطلب نفسه (حجز، رفض، تسليم، ...)، ومنطق
"مين المفروض ياخد إشعار بإيه" يبقى في مكان واحد قابل للتوسّع لوحده من غير
ما يكبّر الموديل أكتر كل ما اتضافت حالة جديدة للطلب.

الدالتين هنا بتتنادوا من Order.save() بس (راجع orders/models.py)، وبتاخدوا
الطلب نفسه كـ parameter بدل ما يكونوا methods جوه الكلاس.
"""

from notifications.services import notify, notify_staff_with_perm
from notifications.models import Notification


def notify_new_order(order):
    """طلب جديد وصل — إشعار لكل موظف عنده صلاحية عرض الطلبات."""
    notify_staff_with_perm(
        'orders.view_order',
        kind=Notification.Kind.NEW_ORDER,
        title=f'طلب جديد #{order.pk}',
        message=f'وصل طلب جديد من العميل {order.client.username}.',
        url_name='staff:order_detail',
        url_kwargs={'pk': order.pk},
    )


def notify_status_change(order, actor):
    """
    تغيّرت حالة الطلب — بنبعت الإشعار المناسب حسب الحالة الجديدة:
    - NEEDS_APPROVAL: المخزن عدّل الطلب وعايز موافقة العميل → إشعار للعميل.
    - CONFIRMED: تم تأكيد الطلب → إشعار للعميل (إلا لو هو نفسه اللي أكده).
    - REJECTED: تم رفض الطلب → إشعار للعميل (إلا لو هو نفسه اللي رفضه).
    - DELIVERED: تم التسليم → إشعار للعميل.
    ولو صاحب الحدث هو العميل نفسه (وافق/رفض تعديل)، بنبعت إشعار
    للموظفين بدل ما نبعت للعميل حاجة هو عارفها أصلًا (حركة عميل).

    ملحوظة: order._old_status لسه بيحمل الحالة القديمة وقت النداء (Order.save
    بيحدّثها بعد ما يخلّص، راجع orders/models.py)، فبنستخدمها هنا مباشرة.
    """
    client_is_actor = actor is not None and getattr(actor, 'pk', None) == order.client_id

    if order.status == order.Status.NEEDS_APPROVAL:
        notify(
            order.client,
            kind=Notification.Kind.ORDER_NEEDS_APPROVAL,
            title=f'طلبك #{order.pk} يحتاج موافقتك',
            # عام ومحايد الاتجاه عمدًا (مش "نقص الكمية" دايمًا) — المخزن
            # ممكن يكون زوّد الكمية مش قللها بس. التفاصيل الدقيقة (صنف
            # بصنف، وأي اتجاه) موجودة في صفحة تفاصيل الطلب نفسها.
            message='المخزن عدّل كميات في طلبك، يرجى مراجعة التعديل والموافقة عليه أو رفضه.',
            url_name='orders:order_detail',
            url_kwargs={'pk': order.pk},
        )

    elif order.status == order.Status.CONFIRMED:
        if client_is_actor:
            notify_staff_with_perm(
                'orders.change_order',
                kind=Notification.Kind.CLIENT_APPROVED_AMENDMENT,
                title=f'العميل وافق على تعديل الطلب #{order.pk}',
                message=f'العميل {order.client.username} وافق على التعديل المقترح.',
                url_name='staff:order_detail',
                url_kwargs={'pk': order.pk},
                exclude_actor=actor,
            )
        else:
            notify(
                order.client,
                kind=Notification.Kind.ORDER_CONFIRMED,
                title=f'تم تأكيد طلبك #{order.pk}',
                message='تم تأكيد طلبك وجاري تجهيزه.',
                url_name='orders:order_detail',
                url_kwargs={'pk': order.pk},
                exclude_actor=actor,
            )

    elif order.status == order.Status.REJECTED:
        if client_is_actor:
            if order._old_status == order.Status.PENDING:
                # العميل ألغى طلبه بنفسه قبل ما حد من المخزن يراجعه أصلًا —
                # مش رفض تعديل مقترح، فالرسالة لازم توضّح الفرق.
                notify_staff_with_perm(
                    'orders.change_order',
                    kind=Notification.Kind.CLIENT_REJECTED_AMENDMENT,
                    title=f'العميل ألغى الطلب #{order.pk}',
                    message=f'العميل {order.client.username} ألغى طلبه بنفسه قبل المراجعة.',
                    url_name='staff:order_detail',
                    url_kwargs={'pk': order.pk},
                    exclude_actor=actor,
                )
            else:
                notify_staff_with_perm(
                    'orders.change_order',
                    kind=Notification.Kind.CLIENT_REJECTED_AMENDMENT,
                    title=f'العميل رفض تعديل الطلب #{order.pk}',
                    message=f'العميل {order.client.username} رفض التعديل المقترح.',
                    url_name='staff:order_detail',
                    url_kwargs={'pk': order.pk},
                    exclude_actor=actor,
                )
        else:
            notify(
                order.client,
                kind=Notification.Kind.ORDER_REJECTED,
                title=f'تم رفض طلبك #{order.pk}',
                message='نأسف، تم رفض طلبك. تواصل معانا لمزيد من التفاصيل.',
                url_name='orders:order_detail',
                url_kwargs={'pk': order.pk},
                exclude_actor=actor,
            )

    elif order.status == order.Status.DELIVERED:
        notify(
            order.client,
            kind=Notification.Kind.ORDER_DELIVERED,
            title=f'تم تسليم طلبك #{order.pk}',
            message='تم تسليم طلبك بنجاح. تقدر تشوف الفاتورة من صفحة الطلب.',
            url_name='orders:order_detail',
            url_kwargs={'pk': order.pk},
            exclude_actor=actor,
        )
