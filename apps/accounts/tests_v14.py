from django.test import TestCase
from django.utils import timezone
from .models import User
from .presence import can_view_presence, presence_label

class RMesPresencePrivacyTests(TestCase):
    def setUp(self):
        self.dev=User.objects.create_user(email="dev@example.com",password="x",role=User.Role.DEVELOPER)
        self.superadmin=User.objects.create_user(email="root@example.com",password="x",role=User.Role.SUPERADMIN,last_seen_at=timezone.now())
        self.admin=User.objects.create_user(email="admin@example.com",password="x",role=User.Role.INFRA_ADMIN,last_seen_at=timezone.now())
        self.user=User.objects.create_user(email="user@example.com",password="x",role=User.Role.USER,last_seen_at=timezone.now())
    def test_developer_can_view_everyone(self):
        self.assertTrue(can_view_presence(self.dev,self.user))
        self.assertTrue(can_view_presence(self.dev,self.admin))
        self.assertTrue(can_view_presence(self.dev,self.superadmin))
    def test_non_developer_cannot_view_superadmin_or_developer(self):
        self.assertFalse(can_view_presence(self.user,self.superadmin))
        self.assertFalse(can_view_presence(self.admin,self.superadmin))
        self.assertFalse(can_view_presence(self.user,self.dev))
        self.assertIn("скрыто",presence_label(self.user,self.superadmin,language="ru"))
