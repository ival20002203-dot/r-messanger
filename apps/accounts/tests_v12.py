from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse

from .models import User,UserPreference


class AppLockV12Tests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(email="v12@rmes.local",password="StrongPassword123!",email_verified=True)
        self.pref,_=UserPreference.objects.get_or_create(user=self.user)
        self.client.force_login(self.user)

    def test_enable_hashes_pin_and_manual_lock_requires_unlock(self):
        r=self.client.post(reverse("accounts:app_lock_settings"),{
            "enabled":"1",
            "current_password":"StrongPassword123!",
            "code":"2580",
            "code_confirm":"2580",
            "timeout_minutes":"5",
            "lock_on_start":"1",
        },HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code,200)
        self.pref.refresh_from_db()
        self.assertTrue(self.pref.app_lock_enabled)
        self.assertNotEqual(self.pref.app_lock_code_hash,"2580")
        self.assertTrue(check_password("2580",self.pref.app_lock_code_hash))

        r=self.client.post(reverse("accounts:app_lock_lock"),HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code,200)
        locked=self.client.get(reverse("chat:home"))
        self.assertEqual(locked.status_code,302)
        self.assertIn(reverse("accounts:app_lock"),locked.url)

        unlocked=self.client.post(reverse("accounts:app_lock"),{"code":"2580","next":reverse("chat:home")})
        self.assertEqual(unlocked.status_code,302)
        self.assertEqual(unlocked.url,reverse("chat:home"))

    def test_wrong_account_password_cannot_change_lock(self):
        r=self.client.post(reverse("accounts:app_lock_settings"),{
            "enabled":"1","current_password":"wrong","code":"1234","code_confirm":"1234","timeout_minutes":"5",
        },HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code,400)
        self.pref.refresh_from_db()
        self.assertFalse(self.pref.app_lock_enabled)
