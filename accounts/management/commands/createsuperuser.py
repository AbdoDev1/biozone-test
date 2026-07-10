from django.contrib.auth.management.commands import createsuperuser as base
from django.contrib.auth import get_user_model


class Command(base.Command):
    help = "إنشاء سوبريوزر — بيظبط role=ADMIN تلقائيًا عشان is_superuser يتفعّل صح."

    def handle(self, *args, **options):
        super().handle(*args, **options)
        User = get_user_model()
        username_field = User.USERNAME_FIELD
        username = options.get(username_field)
        if username:
            user = User.objects.get(**{username_field: username})
            user.role = User.Role.ADMIN
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"تم ضبط role=ADMIN تلقائيًا للمستخدم '{username}'."
            ))
