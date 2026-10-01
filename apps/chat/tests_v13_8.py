import time
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ReservedUsername, User
from apps.chat.models import Conversation, ConversationMember, MessageHiddenFor
from apps.chat.services import create_call_signal_event, create_message, delete_chat_for_user, delete_message_for_user, visible_messages_for
from apps.moderation.models import ModerationScanJob
from apps.moderation.services import _flagged_detections
from apps.accounts.presence import PRESENCE_CLOSE_GRACE_SECONDS, _state_key, is_online, presence_label, set_active


class RMesV138Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user(email="user138@texnopark.uz",password="StrongPass123!",display_name="User")
        self.dev=User.objects.create_user(email="dev138@texnopark.uz",password="StrongPass123!",display_name="Developer",role=User.Role.DEVELOPER)
        self.conv=Conversation.objects.create(kind=Conversation.Kind.DIRECT,created_by=self.user)
        ConversationMember.objects.create(conversation=self.conv,user=self.user,role=ConversationMember.Role.OWNER)
        ConversationMember.objects.create(conversation=self.conv,user=self.dev)
        self.msg=create_message(self.user,self.conv,"protected message",broadcast_realtime=False)

    def test_regular_user_cannot_remove_developer_copy(self):
        event=delete_chat_for_user(self.user,self.conv,scope="everyone",clear_history=True)
        self.assertEqual(event.affected_user_ids,[self.user.pk])
        self.assertIn(self.dev.pk,event.protected_developer_ids)
        self.assertTrue(visible_messages_for(self.dev,self.conv).filter(pk=self.msg.pk).exists())

    def test_developer_can_clear_self_peer_or_everyone(self):
        own=delete_chat_for_user(self.dev,self.conv,scope="self",clear_history=True)
        self.assertEqual(own.affected_user_ids,[self.dev.pk])
        self.assertFalse(visible_messages_for(self.dev,self.conv).filter(pk=self.msg.pk).exists())
        ConversationMember.objects.filter(conversation=self.conv).update(hidden_before_message_id=None,is_hidden=False)
        peer=delete_chat_for_user(self.dev,self.conv,scope="peer",clear_history=True)
        self.assertEqual(peer.affected_user_ids,[self.user.pk])
        self.assertTrue(visible_messages_for(self.dev,self.conv).filter(pk=self.msg.pk).exists())
        self.assertFalse(visible_messages_for(self.user,self.conv).filter(pk=self.msg.pk).exists())

    def test_developer_can_delete_message_only_for_peer_or_for_all(self):
        result=delete_message_for_user(self.dev,self.msg,scope="peer")
        self.assertEqual(result["hidden_for_user_ids"],[self.user.pk])
        self.assertFalse(MessageHiddenFor.objects.filter(message=self.msg,user=self.dev).exists())
        other=create_message(self.user,self.conv,"delete all",broadcast_realtime=False)
        result=delete_message_for_user(self.dev,other,scope="everyone")
        self.assertCountEqual(result["hidden_for_user_ids"],[self.user.pk,self.dev.pk])
        other.refresh_from_db();self.assertTrue(other.is_deleted)

    def test_ice_http_fallback_is_idempotent(self):
        data={"call_id":"ice-138","candidate":{"candidate":"candidate:1 1 UDP 1 10.0.0.2 5000 typ host"}}
        first,_,_=create_call_signal_event(self.user,self.conv.pk,"call_ice",data)
        second,_,_=create_call_signal_event(self.user,self.conv.pk,"call_ice",data)
        self.assertEqual(first.pk,second.pk)

    def test_strict_moderation_thresholds(self):
        flagged=_flagged_detections([
            {"class":"FEMALE_BREAST_EXPOSED","score":0.31},
            {"class":"FEMALE_GENITALIA_COVERED","score":0.51},
        ])
        self.assertEqual(len(flagged),2)

    def test_developer_assigns_and_revokes_reserved_username(self):
        self.client.force_login(self.dev)
        response=self.client.post(reverse("control:reserved_usernames"),{"action":"assign","username":"best_friend","identity":self.user.email})
        self.assertEqual(response.status_code,302)
        self.user.refresh_from_db();reservation=ReservedUsername.objects.get(username="best_friend")
        self.assertEqual(self.user.handle,"best_friend");self.assertEqual(reservation.assigned_to_id,self.user.pk)
        self.client.force_login(self.user)
        data=self.client.get(reverse("accounts:username_check"),{"username":"best_friend"}).json()
        self.assertNotIn("reserved",data);self.assertEqual(data["reason"],"Это ваш текущий username.")
        other=User.objects.create_user(email="other138@texnopark.uz",password="StrongPass123!",display_name="Other")
        self.client.force_login(other)
        data=self.client.get(reverse("accounts:username_check"),{"username":"best_friend"}).json()
        self.assertNotIn("reserved",data);self.assertEqual(data["reason"],"Этот username уже занят.")
        self.client.force_login(self.dev)
        self.client.post(reverse("control:reserved_usernames"),{"action":"revoke_assignment","id":reservation.pk})
        self.user.refresh_from_db();reservation.refresh_from_db()
        self.assertIsNone(self.user.handle);self.assertIsNone(reservation.assigned_to_id)

    def test_moderation_queue_shows_new_job_immediately(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.chat.models import Attachment
        attachment=Attachment.objects.create(message=self.msg,file=SimpleUploadedFile("photo.jpg",b"jpeg",content_type="image/jpeg"),original_name="photo.jpg",content_type="image/jpeg",size=4)
        ModerationScanJob.objects.create(attachment=attachment)
        self.client.force_login(self.dev)
        response=self.client.get(reverse("control:moderation_queue"))
        self.assertContains(response,"photo.jpg")
        self.assertContains(response,"Последние поступившие файлы")
        self.assertContains(response,"Что именно фиксирует контроль 18+")
        self.assertNotContains(response,"location.reload")

    def test_moderation_live_status_and_retry_are_developer_only(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.chat.models import Attachment
        attachment=Attachment.objects.create(
            message=self.msg,
            file=SimpleUploadedFile("instant.jpg",b"jpeg",content_type="image/jpeg"),
            original_name="instant.jpg",content_type="image/jpeg",size=4,
        )
        job=ModerationScanJob.objects.create(
            attachment=attachment,status=ModerationScanJob.Status.ERROR,
            attempts=6,last_error="model test error",
        )
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("control:moderation_live")).status_code,403)
        self.client.force_login(self.dev)
        response=self.client.get(reverse("control:moderation_live"))
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["rows"][0]["filename"],"instant.jpg")
        self.assertEqual(data["rows"][0]["status"],"error")
        self.assertTrue(data["rows"][0]["retry_url"])
        retry=self.client.post(reverse("control:moderation_job_retry",args=[job.pk]))
        self.assertEqual(retry.status_code,200)
        job.refresh_from_db()
        self.assertEqual(job.status,ModerationScanJob.Status.QUEUED)
        self.assertEqual(job.attempts,0)
        self.assertEqual(job.last_error,"")

    def test_server_timestamps_are_canonical_and_not_reused(self):
        first=create_message(self.user,self.conv,"first timestamp",broadcast_realtime=False)
        second=create_message(self.user,self.conv,"second timestamp",broadcast_realtime=False)
        base=timezone.now()-timedelta(minutes=2)
        type(first).objects.filter(pk=first.pk).update(created_at=base)
        type(second).objects.filter(pk=second.pk).update(created_at=base+timedelta(minutes=1))
        first.refresh_from_db();second.refresh_from_db()
        from apps.chat.services import message_payload
        one=message_payload(first);two=message_payload(second)
        self.assertEqual(two["created_at_ms"]-one["created_at_ms"],60000)
        self.assertIn("+00:00",one["created_at"])

    def test_payload_contains_server_local_clock_for_every_window(self):
        from apps.chat.services import message_payload
        instant=timezone.now()-timedelta(minutes=7)
        type(self.msg).objects.filter(pk=self.msg.pk).update(created_at=instant)
        self.msg.refresh_from_db()
        payload=message_payload(self.msg)
        self.assertEqual(payload["time_hm"],timezone.localtime(self.msg.created_at).strftime("%H:%M"))
        self.assertEqual(payload["created_at_local"],timezone.localtime(self.msg.created_at).isoformat())
        self.assertIsInstance(payload["created_at_ms"],int)

    def test_incoming_call_can_be_answered_and_polled(self):
        offer,_,_=create_call_signal_event(
            self.user,self.conv.pk,"call_offer",
            {"call_id":"accept-1381","sdp":{"type":"offer","sdp":"offer"}},
        )
        answer,payload,recipient=create_call_signal_event(
            self.dev,self.conv.pk,"call_answer",
            {"call_id":"accept-1381","sdp":{"type":"answer","sdp":"answer"}},
        )
        self.assertEqual(recipient,self.user.pk)
        self.assertEqual(payload["media"],"audio")
        self.client.force_login(self.user)
        data=self.client.get(reverse("chat:call_poll_api"),{"after":"0","client_id":"caller-window"}).json()
        answer_events=[event for event in data["events"] if event["type"]=="call_answer"]
        self.assertEqual(len(answer_events),1)
        self.assertEqual(answer_events[0]["signal_id"],answer.pk)
        self.assertGreater(answer.pk,offer.pk)

    def test_presence_keeps_multiple_windows_and_server_last_seen(self):
        first,_=set_active(self.user,"window-a",True)
        second,_=set_active(self.user,"window-b",True)
        self.assertTrue(first and second and is_online(self.user.pk))
        set_active(self.user,"window-a",False)
        self.assertTrue(is_online(self.user.pk))
        set_active(self.user,"window-b",False)
        # The final document has a short close grace so a full-page navigation
        # cannot flash offline between the old and new page.
        self.assertTrue(is_online(self.user.pk))
        cache.delete(_state_key(self.user.pk))
        self.assertFalse(is_online(self.user.pk))
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_seen_at)
        self.client.force_login(self.dev)
        response=self.client.get(reverse("chat:conversation",args=[self.conv.pk]))
        self.assertContains(response,"был(а)")

    def test_page_close_uses_grace_and_does_not_replace_real_last_seen(self):
        set_active(self.user,"document-a",True)
        online,changed=set_active(self.user,"document-a",False)
        self.assertTrue(online)
        self.assertFalse(changed)
        state=cache.get(_state_key(self.user.pk))
        self.assertIn("document-a",state)
        self.assertLessEqual(state["document-a"]-time.time(),PRESENCE_CLOSE_GRACE_SECONDS+1)
        self.user.refresh_from_db()
        closed_at=self.user.last_seen_at

        # Simulate the observer arriving after the close grace.  Expiration may
        # change only the aggregate online flag; it must not stamp all users
        # with the observer's current time.
        cache.delete(_state_key(self.user.pk))
        self.assertFalse(is_online(self.user.pk))
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_seen_at,closed_at)

    def test_presence_batch_keeps_each_employees_own_timestamp(self):
        other=User.objects.create_user(
            email="second-presence@texnopark.uz",password="StrongPass123!",display_name="Second"
        )
        first_seen=timezone.now()-timedelta(minutes=17)
        second_seen=timezone.now()-timedelta(minutes=3)
        User.objects.filter(pk=self.user.pk).update(last_seen_at=first_seen,presence_active=False)
        User.objects.filter(pk=other.pk).update(last_seen_at=second_seen,presence_active=False)
        self.client.force_login(self.dev)
        rows=self.client.get(
            reverse("accounts:presence_batch_api"),{"ids":f"{self.user.pk},{other.pk}"}
        ).json()["users"]
        self.assertEqual(rows[str(self.user.pk)]["last_seen_at_ms"],int(first_seen.timestamp()*1000))
        self.assertEqual(rows[str(other.pk)]["last_seen_at_ms"],int(second_seen.timestamp()*1000))
        self.assertNotEqual(rows[str(self.user.pk)]["label"],rows[str(other.pk)]["label"])

    def test_presence_uses_database_fallback_when_redis_is_down(self):
        cache_error=RuntimeError("redis unavailable")
        with patch.object(cache,"add",side_effect=cache_error), \
             patch.object(cache,"get",side_effect=cache_error), \
             patch.object(cache,"set",side_effect=cache_error), \
             patch.object(cache,"delete",side_effect=cache_error):
            online,_=set_active(self.user,"redis-down",True)
            self.assertTrue(online and is_online(self.user.pk))
            self.user.refresh_from_db()
            self.assertTrue(self.user.presence_active)
            offline,_=set_active(self.user,"redis-down",False)
            self.assertFalse(offline or is_online(self.user.pk))
            self.user.refresh_from_db()
        self.assertFalse(self.user.presence_active)

    def test_presence_batch_is_viewer_scoped_and_uses_one_snapshot(self):
        set_active(self.dev,"dev-window",True)
        self.client.force_login(self.user)
        hidden=self.client.get(
            reverse("accounts:presence_batch_api"),{"ids":str(self.dev.pk)}
        ).json()["users"][str(self.dev.pk)]
        self.assertTrue(hidden["hidden"])
        self.assertFalse(hidden["online"])
        self.assertIsNone(hidden["last_seen_at"])

        self.client.force_login(self.dev)
        visible=self.client.get(
            reverse("accounts:presence_batch_api"),{"ids":str(self.user.pk)}
        ).json()["users"][str(self.user.pk)]
        self.assertFalse(visible["hidden"])
        self.assertIn(visible["label"],{"в сети","был(а) только что","давно не был(а) в сети"})
        set_active(self.dev,"dev-window",False)

    def test_presence_label_can_use_the_snapshot_supplied_by_batch(self):
        now=timezone.now()
        self.user.last_seen_at=now-timedelta(minutes=5)
        self.assertEqual(presence_label(self.dev,self.user,now=now,online=True),"в сети")
        self.assertEqual(presence_label(self.dev,self.user,now=now,online=False),"был(а) 5 мин. назад")
