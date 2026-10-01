from django.test import TestCase
from apps.accounts.models import User
from apps.chat.models import Conversation,ConversationMember,Message
from apps.securitycenter.models import DLPCase
from apps.securitycenter.services import scan_message_dlp

class DLPPolicyTests(TestCase):
    def test_dlp_is_monitor_only(self):
        user=User.objects.create_user(email="dlp@texnopark.uz",password="StrongPass123!",display_name="DLP User")
        conv=Conversation.objects.create(kind=Conversation.Kind.SAVED,title="Saved",created_by=user)
        ConversationMember.objects.create(conversation=conv,user=user,role=ConversationMember.Role.OWNER)
        msg=Message.objects.create(conversation=conv,sender=user,body="password=SuperSecret123")
        scan_message_dlp(msg)
        user.refresh_from_db()
        self.assertTrue(DLPCase.objects.filter(message=msg,rule="password_assignment").exists())
        self.assertFalse(user.is_suspended)
        self.assertTrue(user.can_login)
