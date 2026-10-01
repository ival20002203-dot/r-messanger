from django.test import TestCase
from apps.accounts.forms import ProfileForm
from apps.accounts.models import DeviceSession,DeviceToken,ReservedUsername,RoleProfile,User

class RBACAndIdentityTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(email="user@texnopark.uz",password="StrongPass123!",display_name="User")

    def test_custom_role_grants_only_selected_capabilities(self):
        role=RoleProfile.objects.create(name="Security Viewer",slug="security-viewer",permissions=["control.view","security.view"])
        self.user.custom_role=role;self.user.save(update_fields=["custom_role"])
        self.assertTrue(self.user.is_control_admin)
        self.assertTrue(self.user.has_capability("security.view"))
        self.assertFalse(self.user.can_modify_system)
        self.assertFalse(self.user.has_capability("rbac.manage"))

    def test_developer_keeps_absolute_boundary(self):
        self.user.role=User.Role.DEVELOPER;self.user.save(update_fields=["role"])
        self.assertTrue(self.user.has_capability("rbac.manage"))
        self.assertTrue(self.user.can_modify_system)

    def test_reserved_username_is_rejected(self):
        ReservedUsername.objects.update_or_create(username="adminx",defaults={"active":True})
        form=ProfileForm({"display_name":"User","handle":"adminx","bio":"","first_name":"","last_name":""},instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("handle",form.errors)

    def test_blocked_device_invalidates_native_access(self):
        device=DeviceSession.objects.create(user=self.user,device_id="test-device",trust_status=DeviceSession.Trust.BLOCKED)
        token,access,_refresh=DeviceToken.issue(self.user,device)
        self.assertIsNone(DeviceToken.authenticate_access(access))
