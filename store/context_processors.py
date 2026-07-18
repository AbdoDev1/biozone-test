from products.new_arrivals import new_arrivals_queryset


def new_arrivals_count(request):
    """
    عدد أصناف "الوارد الجديد" — بيتحسب بس للعميل المسجّل دخوله (مش لأي زائر
    ومش للستاف، اللي أصلًا بيستخدموا staff/base.html المنفصل). استعلام
    count() على حقل مفهرس (new_arrival_at)، فتكلفته مهملة على كل صفحة.
    """
    user = getattr(request, 'user', None)
    if user and user.is_authenticated and user.role == 'CLIENT':
        return {'new_arrivals_count': new_arrivals_queryset().count()}
    return {}
