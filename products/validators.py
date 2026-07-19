from django.core.exceptions import ValidationError

# دجانجو مفيهوش حد افتراضي لحجم ملف مرفوع (FileExtensionValidator بيتحقق من
# الامتداد بس، مش الحجم) — فأي صورة كبيرة جدًا (حتى لو .jpg سليمة) كانت
# بتتقبل عادي وتتكتب على القرص من غير أي رفض. الـ validator ده بيحط سقف
# واضح لصور المنتجات/الأقسام.
MAX_IMAGE_SIZE_MB = 5


def validate_image_size(file):
    max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(
            f'حجم الصورة أكبر من الحد المسموح ({MAX_IMAGE_SIZE_MB} ميجا).'
        )
