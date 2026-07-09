def notifications(request):
    """
    بيحقن آخر الإشعارات + عدد الغير مقروء في كل الصفحات (زي request.user)
    عشان نقدر نعرض جرس الإشعارات في التوب بار من غير ما كل view يبعتها يدويًا.
    ده أول تحميل بس (السرعة) — التحديث الدوري بعد كده بيتم عن طريق
    notifications:bell_data (شوف bell.html) من غير أي refresh للصفحة.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    qs = user.notifications.all()[:8]
    return {
        'nav_notifications': qs,
        'nav_unread_count': user.notifications.filter(is_read=False).count(),
    }
