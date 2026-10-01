import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.chat.models import Attachment,Conversation,ConversationMember,MessageHiddenFor
from apps.chat.services import (
    create_call_signal_event,create_message,delete_chat_for_user,
    delete_message_for_user,mark_read,message_payload,
)
from apps.chat.templatetags.chat_extras import receipt_mark


class RMesV137Tests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(email="user137@texnopark.uz",password="StrongPass123!",display_name="User")
        self.dev=User.objects.create_user(email="dev137@texnopark.uz",password="StrongPass123!",display_name="Developer",role=User.Role.DEVELOPER)
        self.conv=Conversation.objects.create(kind=Conversation.Kind.DIRECT,created_by=self.user)
        ConversationMember.objects.create(conversation=self.conv,user=self.user,role=ConversationMember.Role.OWNER)
        ConversationMember.objects.create(conversation=self.conv,user=self.dev)

    def test_receipt_changes_from_one_to_two_ticks_after_read(self):
        msg=create_message(self.user,self.conv,"receipt")
        self.assertEqual(receipt_mark(msg),"✓")
        payload=mark_read(self.dev,self.conv,msg,broadcast_realtime=False)
        msg.refresh_from_db()
        self.assertEqual(payload["message_id"],msg.pk)
        self.assertEqual(receipt_mark(msg),"✓✓")
        self.assertEqual(message_payload(msg)["receipts"]["read"],1)

    def test_clear_and_delete_keep_developer_copy(self):
        msg=create_message(self.user,self.conv,"retained")
        event=delete_chat_for_user(self.user,self.conv,for_everyone=True,clear_history=True)
        normal=ConversationMember.objects.get(conversation=self.conv,user=self.user)
        protected=ConversationMember.objects.get(conversation=self.conv,user=self.dev)
        self.assertEqual(event.action,"clear")
        self.assertEqual(normal.hidden_before_message_id,msg.pk)
        self.assertFalse(normal.is_hidden)
        self.assertIsNone(protected.hidden_before_message_id)
        result=delete_message_for_user(self.user,msg,"everyone")
        self.assertIn(self.dev.pk,result["protected_developer_ids"])
        self.assertTrue(MessageHiddenFor.objects.filter(message=msg,user=self.user).exists())
        self.assertFalse(MessageHiddenFor.objects.filter(message=msg,user=self.dev).exists())
        msg.refresh_from_db();self.assertFalse(msg.is_deleted)

    def test_public_delete_response_does_not_disclose_retention(self):
        self.client.force_login(self.user)
        response=self.client.post(reverse("chat:delete_conversation",args=[self.conv.pk]),{"scope":"everyone"})
        self.assertEqual(response.status_code,200)
        self.assertNotIn("protected",response.content.decode("utf-8").lower())

    def test_call_signal_is_audio_and_retry_is_idempotent(self):
        data={"call_id":"call-v137","media":"video","sdp":{"type":"offer","sdp":"test"}}
        first,payload,_=create_call_signal_event(self.user,self.conv.pk,"call_offer",data)
        second,payload2,_=create_call_signal_event(self.user,self.conv.pk,"call_offer",data)
        self.assertEqual(first.pk,second.pk)
        self.assertEqual(payload["media"],"audio")
        self.assertEqual(payload2["signal_id"],first.pk)

    def test_call_poll_cursor_does_not_steal_between_windows(self):
        row,_,_=create_call_signal_event(self.user,self.conv.pk,"call_offer",{"call_id":"cursor-call","sdp":{"type":"offer","sdp":"test"}})
        self.client.force_login(self.dev)
        url=reverse("chat:call_poll_api")
        first=self.client.get(url,{"after":"0","client_id":"window-a"}).json()
        second=self.client.get(url,{"after":"0","client_id":"window-b"}).json()
        self.assertEqual(first["events"][0]["signal_id"],row.pk)
        self.assertEqual(second["events"][0]["signal_id"],row.pk)
        self.assertEqual(self.client.get(url,{"after":str(row.pk)}).json()["events"],[])

    def test_private_attachment_supports_inline_and_range(self):
        with tempfile.TemporaryDirectory() as media_dir,override_settings(MEDIA_ROOT=Path(media_dir)):
            msg=create_message(self.user,self.conv,"photo")
            upload=SimpleUploadedFile("photo.jpg",b"0123456789",content_type="image/jpeg")
            attachment=Attachment.objects.create(message=msg,file=upload,original_name="photo.jpg",content_type="image/jpeg",size=10,scan_status="safe")
            payload=message_payload(msg)
            self.assertEqual(payload["attachments"][0]["url"],reverse("chat:attachment_content",args=[attachment.pk]))
            self.assertNotIn("/media/",payload["attachments"][0]["url"])
            self.client.force_login(self.user)
            response=self.client.get(reverse("chat:attachment_content",args=[attachment.pk]),HTTP_RANGE="bytes=2-5")
            self.assertEqual(response.status_code,206)
            self.assertEqual(response["Content-Range"],"bytes 2-5/10")
            self.assertEqual(b"".join(response.streaming_content),b"2345")

    def test_admin_routes_are_not_visible_to_regular_users(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("control:dashboard")).status_code,403)
        self.assertEqual(self.client.get(reverse("control:forensics")).status_code,403)
