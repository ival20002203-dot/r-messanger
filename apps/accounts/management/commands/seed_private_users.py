import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or reset private R-Messanger accounts"

    def handle(self, *args, **options):
        User = get_user_model()

        accounts = [
            ("BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_PASSWORD", "Admin", True),
            ("FRIEND_EMAIL", "FRIEND_PASSWORD", "Friend", False),
            ("FRIEND2_EMAIL", "FRIEND2_PASSWORD", "Friend2", False),
        ]

        for email_key, password_key, name, is_admin in accounts:
            email = os.getenv(email_key, "").strip().lower()
            password = os.getenv(password_key, "")

            if not email or not password:
                self.stdout.write(
                    self.style.WARNING(f"SKIP {email_key}: environment variable missing")
                )
                continue

            user = User.objects.filter(email__iexact=email).first()
            created = False

            if user is None:
                if is_admin:
                    user = User.objects.create_superuser(
                        email=email,
                        password=password,
                    )
                else:
                    user = User.objects.create_user(
                        email=email,
                        password=password,
                    )
                created = True
            else:
                user.set_password(password)

            if hasattr(user, "is_active"):
                user.is_active = True

            if hasattr(user, "can_login"):
                user.can_login = True

            if hasattr(user, "email_verified"):
                user.email_verified = True

            if hasattr(user, "is_staff"):
                user.is_staff = is_admin

            if hasattr(user, "is_superuser"):
                user.is_superuser = is_admin

            if hasattr(user, "display_name") and not user.display_name:
                user.display_name = name

            user.save()

            action = "CREATED" if created else "PASSWORD RESET"
            self.stdout.write(self.style.SUCCESS(f"{action}: {email}"))
