import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "ينشئ حساب أدمن (role=ADMIN) لو مش موجود، أو يظبطه لو موجود. آمن يتنفذ أكتر من مرة."

    def add_arguments(self, parser):
        parser.add_argument('--username', default=os.environ.get('DJANGO_ADMIN_USERNAME', 'admin'))
        parser.add_argument('--email', default=os.environ.get('DJANGO_ADMIN_EMAIL', ''))
        parser.add_argument('--password', default=os.environ.get('DJANGO_ADMIN_PASSWORD'))

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        password = options['password']
        email = options['email']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )

        user.role = User.Role.ADMIN      # ده اللي بيخلي is_superuser=True تلقائيًا جوه save()
        user.status = User.Status.ACTIVE
        user.is_staff = True
        user.is_active = True

        if password:
            user.set_password(password)
        elif created:
            self.stdout.write(self.style.WARNING(
                "تحذير: يوزر جديد اتعمل من غير باسورد (محدّدتش --password ولا DJANGO_ADMIN_PASSWORD)."
            ))

        user.save()
        user.refresh_from_db()

        action = "اتعمل" if created else "اتحدّث"
        self.stdout.write(self.style.SUCCESS(
            f"الأدمن '{user.username}' {action} — role={user.role}, "
            f"is_superuser={user.is_superuser}, is_staff={user.is_staff}, is_active={user.is_active}"
        ))
