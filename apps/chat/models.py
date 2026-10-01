import hashlib, os, uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class Conversation(models.Model):
    class Kind(models.TextChoices):
        DIRECT="direct","Личный чат"
        GROUP="group","Группа"
        CHANNEL="channel","Канал"
        SAVED="saved","Сохранённые сообщения"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=10,choices=Kind.choices,default=Kind.DIRECT)
    title=models.CharField(max_length=180,blank=True)
    description=models.TextField(blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="created_conversations")
    only_admins_can_invite=models.BooleanField(default=False)
    only_admins_can_pin=models.BooleanField(default=True)
    is_archived=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True,db_index=True)
    pinned_message=models.ForeignKey("Message",null=True,blank=True,on_delete=models.SET_NULL,related_name="+")
    class Meta:ordering=["-updated_at"]
    def display_title_for(self,user):
        if self.kind!=self.Kind.DIRECT:return self.title or "Без названия"
        other=self.members.exclude(user=user).select_related("user").first()
        return str(other.user) if other else "Личный чат"
    def peer_for(self,user):
        if self.kind!=self.Kind.DIRECT:return None
        m=self.members.exclude(user=user).select_related("user").first()
        return m.user if m else None

class ConversationMember(models.Model):
    class Role(models.TextChoices):
        OWNER="owner","Владелец"
        ADMIN="admin","Администратор"
        MEMBER="member","Участник"
    class ChatTheme(models.TextChoices):
        DEFAULT="default","Классическая"
        OCEAN="ocean","Ocean"
        VIOLET="violet","Violet"
        EMERALD="emerald","Emerald"
        SUNSET="sunset","Sunset"
    class BackgroundStyle(models.TextChoices):
        CLASSIC="classic","Классический"
        DOTS="dots","Точки"
        GRID="grid","Сетка"
        CLEAN="clean","Чистый"
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="members")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="conversation_memberships")
    role=models.CharField(max_length=10,choices=Role.choices,default=Role.MEMBER)
    can_write=models.BooleanField(default=True)
    muted=models.BooleanField(default=False)
    is_archived=models.BooleanField(default=False)
    is_pinned=models.BooleanField(default=False)
    is_hidden=models.BooleanField(default=False)
    hidden_before_message_id=models.BigIntegerField(null=True,blank=True)
    muted_until=models.DateTimeField(null=True,blank=True)
    notifications_enabled=models.BooleanField(default=True)
    chat_theme=models.CharField(max_length=12,choices=ChatTheme.choices,default=ChatTheme.DEFAULT)
    background_style=models.CharField(max_length=12,choices=BackgroundStyle.choices,default=BackgroundStyle.CLASSIC)
    media_previews=models.BooleanField(default=True)
    last_read_message=models.ForeignKey("Message",null=True,blank=True,on_delete=models.SET_NULL,related_name="+")
    joined_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["conversation","user"],name="unique_conversation_member")]

class Message(models.Model):
    class Kind(models.TextChoices):
        TEXT="text","Текст"
        FILE="file","Файл"
        VOICE="voice","Голосовое"
        SYSTEM="system","Системное"
        STICKER="sticker","Стикер"
        POLL="poll","Опрос"
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="messages")
    sender=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="sent_messages")
    kind=models.CharField(max_length=12,choices=Kind.choices,default=Kind.TEXT)
    body=models.TextField(blank=True)
    client_message_id=models.CharField(max_length=64,blank=True,db_index=True)
    reply_to=models.ForeignKey("self",null=True,blank=True,on_delete=models.SET_NULL,related_name="replies")
    forwarded_from=models.ForeignKey("self",null=True,blank=True,on_delete=models.SET_NULL,related_name="forwards")
    sticker=models.ForeignKey("Sticker",null=True,blank=True,on_delete=models.SET_NULL,related_name="messages")
    poll=models.OneToOneField("Poll",null=True,blank=True,on_delete=models.SET_NULL,related_name="message")
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    edited_at=models.DateTimeField(null=True,blank=True)
    is_deleted=models.BooleanField(default=False)
    deleted_at=models.DateTimeField(null=True,blank=True)
    deleted_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="+")
    deletion_reason=models.CharField(max_length=255,blank=True)
    class Meta:
        ordering=["created_at"]
        indexes=[models.Index(fields=["conversation","created_at"])]
        constraints=[models.UniqueConstraint(fields=["sender","client_message_id"],condition=~models.Q(client_message_id=""),name="unique_sender_client_message_id")]
    def soft_delete(self,actor=None,reason=""):
        self.is_deleted=True;self.deleted_at=timezone.now();self.deleted_by=actor;self.deletion_reason=(reason or "")[:255]
        self.save(update_fields=["is_deleted","deleted_at","deleted_by","deletion_reason"])

class MessageRevision(models.Model):
    message=models.ForeignKey(Message,on_delete=models.CASCADE,related_name="revisions")
    editor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    old_body=models.TextField()
    new_body=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=["-created_at"]

class MessageHiddenFor(models.Model):
    message=models.ForeignKey(Message,on_delete=models.CASCADE,related_name="hidden_for")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="hidden_messages")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["message","user"],name="unique_message_hidden_for")]

class ChatDeletionEvent(models.Model):
    class Action(models.TextChoices):
        DELETE="delete","Удаление чата"
        CLEAR="clear","Очистка истории"
    class Scope(models.TextChoices):
        SELF="self","Только у себя"
        PEER="peer","Только у собеседника"
        EVERYONE="everyone","У всех"
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="deletion_events")
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="chat_deletion_events")
    action=models.CharField(max_length=12,choices=Action.choices,default=Action.DELETE,db_index=True)
    scope=models.CharField(max_length=12,choices=Scope.choices)
    through_message_id=models.BigIntegerField(null=True,blank=True)
    affected_user_ids=models.JSONField(default=list,blank=True)
    protected_developer_ids=models.JSONField(default=list,blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:ordering=["-created_at"]

def attachment_path(instance,filename):
    ext=os.path.splitext(filename)[1][:12]
    return f"attachments/{instance.message.conversation_id}/{uuid.uuid4().hex}{ext}"

class Attachment(models.Model):
    message=models.ForeignKey(Message,on_delete=models.CASCADE,related_name="attachments")
    file=models.FileField(upload_to=attachment_path)
    original_name=models.CharField(max_length=255)
    content_type=models.CharField(max_length=120,blank=True)
    size=models.BigIntegerField(default=0)
    sha256=models.CharField(max_length=64,blank=True)
    scan_status=models.CharField(max_length=16,default="pending",db_index=True)
    scan_engine=models.CharField(max_length=64,blank=True)
    scan_signature=models.CharField(max_length=255,blank=True)
    scanned_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    @property
    def is_image(self):return self.content_type.startswith("image/")
    @property
    def is_audio(self):return self.content_type.startswith("audio/")
    @property
    def is_video(self):return self.content_type.startswith("video/")
    def calculate_hash(self):
        h=hashlib.sha256();self.file.seek(0)
        for chunk in self.file.chunks():h.update(chunk)
        self.file.seek(0);self.sha256=h.hexdigest();return self.sha256

class Reaction(models.Model):
    message=models.ForeignKey(Message,on_delete=models.CASCADE,related_name="reactions")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    emoji=models.CharField(max_length=16)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["message","user","emoji"],name="unique_message_user_emoji")]


class MessageMention(models.Model):
    message=models.ForeignKey(Message,on_delete=models.CASCADE,related_name="mentions")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="message_mentions")
    is_all=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["message","user"],name="unique_message_mention")]

class UserNotification(models.Model):
    class Kind(models.TextChoices):
        MENTION="mention","Упоминание"
        REPLY="reply","Ответ"
        REACTION="reaction","Реакция"
        SYSTEM="system","Системное"
        STICKER="sticker","Стикер"
        POLL="poll","Опрос"
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="notifications")
    kind=models.CharField(max_length=16,choices=Kind.choices,default=Kind.SYSTEM,db_index=True)
    message=models.ForeignKey(Message,null=True,blank=True,on_delete=models.CASCADE,related_name="notifications")
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="notification_actions")
    title=models.CharField(max_length=180,blank=True)
    body=models.CharField(max_length=500,blank=True)
    read_at=models.DateTimeField(null=True,blank=True,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:ordering=["-created_at"]


class CallSignalEvent(models.Model):
    class EventType(models.TextChoices):
        OFFER="call_offer","Offer"
        ANSWER="call_answer","Answer"
        ICE="call_ice","ICE"
        END="call_end","End"
        REJECT="call_reject","Reject"
        BUSY="call_busy","Busy"
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="incoming_call_signals")
    sender=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="outgoing_call_signals")
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="call_signals")
    call_id=models.CharField(max_length=96,db_index=True)
    event_type=models.CharField(max_length=16,choices=EventType.choices,db_index=True)
    payload=models.JSONField(default=dict,blank=True)
    consumed_at=models.DateTimeField(null=True,blank=True,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:
        ordering=["id"]
        indexes=[models.Index(fields=["recipient","consumed_at","id"]),models.Index(fields=["call_id","created_at"])]
        constraints=[models.UniqueConstraint(fields=["recipient","sender","call_id","event_type"],condition=~models.Q(event_type="call_ice"),name="unique_non_ice_call_signal")]

def call_recording_path(instance,filename):
    ext=os.path.splitext(filename)[1][:12] or ".webm"
    return f"call_recordings/{timezone.now():%Y/%m/%d}/{instance.call_id}-{uuid.uuid4().hex}{ext}"

class CallRecord(models.Model):
    class Status(models.TextChoices):
        RINGING="ringing","Вызов"
        CONNECTED="connected","Соединён"
        ENDED="ended","Завершён"
        REJECTED="rejected","Отклонён"
        MISSED="missed","Пропущен"
        BUSY="busy","Занято"
        FAILED="failed","Ошибка"
    call_id=models.CharField(max_length=96,unique=True,db_index=True)
    conversation=models.ForeignKey(Conversation,null=True,blank=True,on_delete=models.SET_NULL,related_name="call_records")
    caller=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="calls_started")
    callee=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="calls_received")
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.RINGING,db_index=True)
    started_at=models.DateTimeField(default=timezone.now,db_index=True)
    connected_at=models.DateTimeField(null=True,blank=True)
    ended_at=models.DateTimeField(null=True,blank=True,db_index=True)
    duration_seconds=models.PositiveIntegerField(default=0)
    end_reason=models.CharField(max_length=80,blank=True)
    recording=models.FileField(upload_to=call_recording_path,blank=True)
    recording_content_type=models.CharField(max_length=120,blank=True)
    recording_size=models.BigIntegerField(default=0)
    recording_sha256=models.CharField(max_length=64,blank=True)
    recording_uploaded_at=models.DateTimeField(null=True,blank=True)
    admin_only=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=["-started_at"]
        indexes=[models.Index(fields=["status","started_at"]),models.Index(fields=["caller","started_at"]),models.Index(fields=["callee","started_at"])]

class MessageReceipt(models.Model):
    message=models.ForeignKey(Message,on_delete=models.CASCADE,related_name="receipts")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="message_receipts")
    delivered_at=models.DateTimeField(null=True,blank=True,db_index=True)
    read_at=models.DateTimeField(null=True,blank=True,db_index=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["message","user"],name="unique_message_receipt")]
        indexes=[models.Index(fields=["user","read_at"])]

class MessagePin(models.Model):
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="pins")
    message=models.ForeignKey(Message,on_delete=models.CASCADE,related_name="pin_records")
    pinned_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="message_pins")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at"]
        constraints=[models.UniqueConstraint(fields=["conversation","message"],name="unique_conversation_message_pin")]

class ChatFolder(models.Model):
    class SmartType(models.TextChoices):
        CUSTOM="custom","Пользовательская"
        ALL="all","Все"
        DIRECT="direct","Личные"
        GROUPS="groups","Группы"
        CHANNELS="channels","Каналы"
        UNREAD="unread","Непрочитанные"
        ARCHIVED="archived","Архив"
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="chat_folders")
    name=models.CharField(max_length=40)
    smart_type=models.CharField(max_length=16,choices=SmartType.choices,default=SmartType.CUSTOM)
    position=models.PositiveSmallIntegerField(default=0)
    include_muted=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=["position","id"]

class ChatFolderConversation(models.Model):
    folder=models.ForeignKey(ChatFolder,on_delete=models.CASCADE,related_name="chat_links")
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="folder_links")
    class Meta:
        constraints=[models.UniqueConstraint(fields=["folder","conversation"],name="unique_folder_conversation")]

class StickerPack(models.Model):
    name=models.CharField(max_length=80)
    slug=models.SlugField(max_length=80,unique=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="sticker_packs")
    active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)

class Sticker(models.Model):
    pack=models.ForeignKey(StickerPack,on_delete=models.CASCADE,related_name="stickers")
    emoji=models.CharField(max_length=16,blank=True)
    title=models.CharField(max_length=80,blank=True)
    image=models.ImageField(upload_to="stickers/%Y/%m/")
    is_custom_emoji=models.BooleanField(default=False)
    active=models.BooleanField(default=True)
    position=models.PositiveSmallIntegerField(default=0)
    class Meta:ordering=["position","id"]


class Poll(models.Model):
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="polls")
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="created_polls")
    question=models.CharField(max_length=300)
    anonymous=models.BooleanField(default=False)
    multiple_choice=models.BooleanField(default=False)
    closes_at=models.DateTimeField(null=True,blank=True,db_index=True)
    closed_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    @property
    def is_closed(self):return bool(self.closed_at or (self.closes_at and timezone.now()>=self.closes_at))

class PollOption(models.Model):
    poll=models.ForeignKey(Poll,on_delete=models.CASCADE,related_name="options")
    text=models.CharField(max_length=200)
    position=models.PositiveSmallIntegerField(default=0)
    class Meta:ordering=["position","id"]

class PollVote(models.Model):
    poll=models.ForeignKey(Poll,on_delete=models.CASCADE,related_name="votes")
    option=models.ForeignKey(PollOption,on_delete=models.CASCADE,related_name="votes")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="poll_votes")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["option","user"],name="unique_poll_option_user_vote")]

class ScheduledPost(models.Model):
    class Status(models.TextChoices):
        SCHEDULED="scheduled","Запланировано"
        SENT="sent","Отправлено"
        CANCELLED="cancelled","Отменено"
        ERROR="error","Ошибка"
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name="scheduled_posts")
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name="scheduled_posts")
    body=models.TextField()
    silent=models.BooleanField(default=False)
    scheduled_for=models.DateTimeField(db_index=True)
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.SCHEDULED,db_index=True)
    sent_message=models.ForeignKey(Message,null=True,blank=True,on_delete=models.SET_NULL,related_name="scheduled_source")
    last_error=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:ordering=["scheduled_for"]
