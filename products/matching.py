"""
أدوات مطابقة أسماء الأصناف — الهدف: منع تكرار الصنف في قاعدة البيانات
لمجرد اختلاف بسيط وشكلي في الاسم (مسافات زيادة، أرقام عربي/إنجليزي،
حروف متشابهة زي ا/أ/إ/آ أو ي/ى أو ه/ة)، مع ترك أي اختلاف حقيقي في الاسم
لمراجعة بشرية بدل ما يتم دمجه تلقائيًا.
"""
import re
from difflib import SequenceMatcher

_ARABIC_INDIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_DIACRITICS_RE = re.compile(r'[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]')
_WHITESPACE_RE = re.compile(r'\s+')

# خرائط توحيد الحروف المتشابهة شكليًا واللي بتختلف كتابةً من شخص للتاني
# لنفس الكلمة (مش بتغيّر معنى الكلمة، بس بتوحّد طريقة كتابتها للمقارنة فقط
# — الاسم الأصلي name_ar بيفضل زي ما اتكتب بالظبط، التطبيع ده لغرض
# المطابقة الداخلية بس).
_CHAR_MAP = str.maketrans({
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
    'ى': 'ي',
    'ة': 'ه',
    'ؤ': 'و',
    'ئ': 'ي',
})


def normalize_name(name: str) -> str:
    """
    تطبيع اسم الصنف لغرض المطابقة (مش للعرض): إزالة الفراغات الزيادة،
    توحيد الأرقام والحروف المتشابهة، وتحويل النص لحالة موحّدة.
    نفس الاسم بأشكال كتابة مختلفة هيرجع نفس الـ normalize_name بالظبط.
    """
    if not name:
        return ''
    text = str(name).strip()
    text = text.translate(_ARABIC_INDIC_DIGITS)
    text = _DIACRITICS_RE.sub('', text)
    text = text.translate(_CHAR_MAP)
    text = _WHITESPACE_RE.sub(' ', text)
    return text.strip().lower()


def similarity(a: str, b: str) -> float:
    """نسبة تشابه (0-1) بين نصّين مُطبَّعين مسبقًا."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_similar_products(name_key, candidates, threshold=0.82, limit=3):
    """
    بيدوّر بين قائمة منتجات (candidates — أي iterable فيه .name_key و .pk)
    عن أقرب الأسماء لـ name_key، ويرجّع أفضل `limit` نتيجة بنسبة تشابه
    >= threshold، مرتبة من الأعلى تشابهًا. مش بيدمج تلقائي — بس بيقترح.
    """
    scored = []
    for product in candidates:
        ratio = similarity(name_key, product.name_key)
        if ratio >= threshold:
            scored.append((product, round(ratio * 100)))
    scored.sort(key=lambda item: -item[1])
    return scored[:limit]
