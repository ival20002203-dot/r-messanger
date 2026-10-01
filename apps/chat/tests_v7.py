from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.utils import timezone
from apps.accounts.models import User
from apps.chat.models import Attachment,Conversation,ConversationMember,Message,Poll,PollOption,PollVote,ScheduledPost
from apps.chat.previews import build_preview
from apps.chat.services import create_message,delete_chat_for_user,process_due_scheduled_post

class MessagingV7Tests(TestCase):
    def setUp(self):
        self.a=User.objects.create_user(email="a@texnopark.uz",password="StrongPass123!",display_name="A")
        self.b=User.objects.create_user(email="b@texnopark.uz",password="StrongPass123!",display_name="B")
        self.conv=Conversation.objects.create(kind=Conversation.Kind.GROUP,title="Test",created_by=self.a)
        ConversationMember.objects.create(conversation=self.conv,user=self.a,role=ConversationMember.Role.OWNER)
        ConversationMember.objects.create(conversation=self.conv,user=self.b)

    def test_poll_vote_models(self):
        poll=Poll.objects.create(conversation=self.conv,created_by=self.a,question="When?")
        one=PollOption.objects.create(poll=poll,text="Friday",position=0)
        two=PollOption.objects.create(poll=poll,text="Saturday",position=1)
        msg=create_message(self.a,self.conv,poll.question,kind=Message.Kind.POLL,poll=poll)
        PollVote.objects.create(poll=poll,option=one,user=self.b)
        self.assertEqual(msg.poll_id,poll.pk)
        self.assertEqual(one.votes.count(),1)
        self.assertEqual(two.votes.count(),0)

    def test_scheduled_post_processor(self):
        channel=Conversation.objects.create(kind=Conversation.Kind.CHANNEL,title="News",created_by=self.a)
        ConversationMember.objects.create(conversation=channel,user=self.a,role=ConversationMember.Role.OWNER)
        row=ScheduledPost.objects.create(conversation=channel,created_by=self.a,body="Maintenance at 22:00",scheduled_for=timezone.now()-timedelta(seconds=1))
        done=process_due_scheduled_post()
        row.refresh_from_db()
        self.assertEqual(done.pk,row.pk)
        self.assertEqual(row.status,ScheduledPost.Status.SENT)
        self.assertIsNotNone(row.sent_message_id)

    def test_developer_copy_survives_delete_for_everyone(self):
        dev=User.objects.create_user(email="dev@texnopark.uz",password="StrongPass123!",display_name="Dev",role=User.Role.DEVELOPER)
        direct=Conversation.objects.create(kind=Conversation.Kind.DIRECT,created_by=self.a)
        normal=ConversationMember.objects.create(conversation=direct,user=self.a,role=ConversationMember.Role.OWNER)
        protected=ConversationMember.objects.create(conversation=direct,user=dev)
        create_message(self.a,direct,"retained")
        event=delete_chat_for_user(self.a,direct,for_everyone=True)
        protected.refresh_from_db();normal.refresh_from_db()
        self.assertFalse(protected.is_hidden)
        self.assertIn(dev.pk,event.protected_developer_ids)
        self.assertTrue(normal.is_hidden)

    def test_safe_text_attachment_preview(self):
        msg=create_message(self.a,self.conv,"file")
        f=SimpleUploadedFile("report.txt",b"hello localgram\nsecond line",content_type="text/plain")
        att=Attachment.objects.create(message=msg,file=f,original_name="report.txt",content_type="text/plain",size=f.size,scan_status="safe")
        preview=build_preview(att)
        self.assertEqual(preview["kind"],"text")
        self.assertIn("hello localgram",preview["text"])

    @override_settings(ANTI_SPAM_ENABLED=True,ANTI_SPAM_DUPLICATE_LIMIT=2,ANTI_SPAM_WINDOW_SECONDS=60,RATE_LIMIT_MESSAGES=100)
    def test_duplicate_spam_is_throttled(self):
        create_message(self.a,self.conv,"same message")
        create_message(self.a,self.conv,"same message")
        with self.assertRaises(PermissionError):create_message(self.a,self.conv,"same message")
