from decimal import Decimal, ROUND_HALF_UP

from num2words import num2words


def _words(n):
    """رقم صحيح -> كلمات عربية، بصياغة معتادة في الفواتير (بدون فراغ بعد 'و')."""
    if n == 0:
        return 'صفر'
    return num2words(n, lang='ar').replace(' و ', ' و')


def amount_to_arabic_words(amount):
    """
    يحوّل مبلغ (جنيه.قرش) لصيغة عربية مكتوبة زي اللي بتتكتب على الفواتير الورقية:
    'فقط واحد وأربعون ألفاً ومئتان وتسعة عشر جنيهاً وأربعون قرشاً لا غير'
    """
    amount = Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    pounds = int(amount)
    piastres = int((amount - pounds) * 100)

    parts = ['فقط']
    parts.append(f'{_words(pounds)} جنيهاً' if pounds or not piastres else '')
    if piastres:
        parts.append(f'و{_words(piastres)} قرشاً')
    parts.append('لا غير')

    return ' '.join(p for p in parts if p)
