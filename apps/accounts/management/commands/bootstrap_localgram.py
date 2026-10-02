import os

from django.core.management.base import BaseCommand
from apps.accounts.models import AppSetting, CorporateDomain, User


class Command(BaseCommand):
    help = "Bootstrap R-Mes configuration and private accounts."

    def handle(self, *args, **opts):
        # Разрешенные корпоративные домены
        for d in [
            x.strip().lower()
            for x in os.getenv("CORP_EMAIL_DOMAINS", "").split(",")
            if x.strip()
        ]:
            CorporateDomain.objects.get_or_create(
                domain=d,
                defaults={
                    "active": True,
                    "registration_enabled": True,
                },
            )

        AppSetting.objects.get_or_create(
            key="app_name",
            defaults={
                "value": "R-Mes",
                "description": "Название приложения",
            },
        )

        AppSetting.objects.get_or_create(
            key="monitoring_notice",
            defaults={
                "value": os.getenv(
                    "MONITORING_NOTICE",
                    "Коммуникации R-Mes журналируются и защищаются корпоративными политиками.",
                ),
                "description": "Уведомление сотрудникам",
            },
        )

        def create_or_update(
            email_key,
            password_key,
            name_key,
            default_name,
            role,
            is_staff=False,
            is_superuser=False,
        ):
            email = os.getenv(email_key, "").strip().lower()
            password = os.getenv(password_key, "")
            name = os.getenv(name_key, default_name).strip() or default_name

            if not email or not password:
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP {email_key}: email or password is empty"
                    )
                )
                return

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "display_name": name,
                    "role": role,
                    "email_verified": True,
                    "can_login": True,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                },
            )

            # ВАЖНО: пароль обновляется и для уже существующей учетной записи
            user.set_password(password)

            user.username = email
            user.display_name = name
            user.role = role
            user.email_verified = True
            user.can_login = True
            user.is_active = True
            user.is_suspended = False
            user.is_staff = is_staff
            user.is_superuser = is_superuser

            user.save()

            status = "CREATED" if created else "UPDATED"
            self.stdout.write(
                self.style.SUCCESS(f"{status}: {email}")
            )

        # Администратор
        create_or_update(
            "BOOTSTRAP_ADMIN_EMAIL",
            "BOOTSTRAP_ADMIN_PASSWORD",
            "BOOTSTRAP_ADMIN_NAME",
            "Admin",
            User.Role.DEVELOPER,
            True,
            True,
        )

        # Первый пользователь
        create_or_update(
            "FRIEND_EMAIL",
            "FRIEND_PASSWORD",
            "FRIEND_NAME",
            "Friend",
            User.Role.USER,
        )

        # Второй пользователь
        create_or_update(
            "FRIEND2_EMAIL",
            "FRIEND2_PASSWORD",
            "FRIEND2_NAME",
            "Friend2",
            User.Role.USER,
        )
