from django.test import TestCase
from apps.accounts.forms import PreferenceForm
from apps.accounts.models import User, UserPreference


class AppearancePreferenceTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(email="appearance@texnopark.uz",password="StrongPass123!",display_name="Appearance User")
        self.pref=UserPreference.objects.create(user=self.user)

    def test_personal_appearance_can_be_saved(self):
        form=PreferenceForm({
            "pref-theme":"tinted",
            "pref-accent_color":"violet",
            "pref-chat_background":"dots",
            "pref-font_scale":"110",
            "pref-animations_enabled":"on",
            "pref-desktop_notifications":"on",
            "pref-notification_sound":"on",
            "pref-show_message_preview":"on",
            "pref-enter_to_send":"on",
            "pref-animated_emoji":"on",
            "pref-auto_download_images":"on",
        },instance=self.pref,prefix="pref")
        self.assertTrue(form.is_valid(),form.errors)
        row=form.save()
        self.assertEqual(row.theme,"tinted")
        self.assertEqual(row.accent_color,"violet")
        self.assertEqual(row.chat_background,"dots")
        self.assertEqual(row.font_scale,110)

    def test_font_scale_is_clamped(self):
        form=PreferenceForm({
            "pref-theme":"dark",
            "pref-accent_color":"ocean",
            "pref-chat_background":"ocean",
            "pref-font_scale":"200",
        },instance=self.pref,prefix="pref")
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data["font_scale"],120)
