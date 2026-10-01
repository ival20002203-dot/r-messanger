import csv
import json
import mimetypes
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.db import connection,transaction
from django.db.models import Count,Q,Sum
from django.http import HttpResponse,FileResponse,Http404,JsonResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import (
    ApiToken,AppSetting,CorporateDomain,DeviceSession,DeviceToken,IPAccessRule,LoginEvent,ReservedUsername,RoleProfile,User,UserBlock
)
from apps.accounts.reserved_catalog import BUILTIN_CATALOG,BUILTIN_MAP,CATEGORY_LABELS
from apps.accounts.presence import snapshot as presence_snapshot, presence_label, can_view_presence
from apps.accounts.rbac import CAPABILITIES,BUILTIN_ROLE_CAPABILITIES,capabilities_for
from apps.audit.models import AuditEvent
from apps.audit.services import audit
from apps.chat.models import (
    Attachment,ChatDeletionEvent,Conversation,ConversationMember,Message,MessageHiddenFor,CallRecord
)
from apps.moderation.models import ModerationCase,ModerationScanJob
from apps.securitycenter.models import AttachmentScanJob,DLPCase,SecurityIncident
from apps.operations.models import BackupVerification,ClientVersionPolicy,RateLimitEvent
from .decorators import control_required,developer_required
from .forms import DomainForm,IPRuleForm,UserAdminForm

def _reserved_username_next(request):
    value=(request.POST.get("next") or "").strip()
    return value if value.startswith("/control/usernames/") else "/control/usernames/"

@control_required()
def dashboard(request):
    now=timezone.now();today=timezone.localdate()
    user_count=User.objects.count()
    role_raw=dict(User.objects.values_list("role").annotate(c=Count("id")))
    role_rows=[]
    for value,label in User.Role.choices:
        count=role_raw.get(value,0)
        role_rows.append({"value":value,"label":label,"count":count,"pct":round((count/user_count*100),1) if user_count else 0})

    top_users=User.objects.annotate(message_count=Count("sent_messages")).order_by("-message_count","display_name")[:8]
    storage_bytes=Attachment.objects.aggregate(v=Sum("size"))["v"] or 0
    db_ok=redis_ok=True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1");cursor.fetchone()
    except Exception:
        db_ok=False
    try:
        cache.set("control-health","ok",10)
        redis_ok=cache.get("control-health")=="ok"
    except Exception:
        redis_ok=False

    dashboard_presence=presence_snapshot(User.objects.values_list("id",flat=True))
    return render(request,"control/dashboard.html",{
        "user_count":user_count,
        "online_count":sum(1 for online in dashboard_presence.values() if online),
        "suspended_count":User.objects.filter(is_suspended=True).count(),
        "conversation_count":Conversation.objects.count(),
        "active_chats_today":Conversation.objects.filter(updated_at__date=today).count(),
        "messages_today":Message.objects.filter(created_at__date=today).count(),
        "messages_hour":Message.objects.filter(created_at__gte=now-timedelta(hours=1)).count(),
        "files_today":Attachment.objects.filter(created_at__date=today).count(),
        "storage_bytes":storage_bytes,
        "failed_logins_today":LoginEvent.objects.filter(created_at__date=today,successful=False).count(),
        "failed_logins_hour":LoginEvent.objects.filter(created_at__gte=now-timedelta(hours=1),successful=False).count(),
        "deleted_messages":Message.objects.filter(is_deleted=True).count(),
        "deleted_chats":ChatDeletionEvent.objects.filter(action=ChatDeletionEvent.Action.DELETE).count(),
        "cleared_chats":ChatDeletionEvent.objects.filter(action=ChatDeletionEvent.Action.CLEAR).count(),
        "user_blocks":UserBlock.objects.count(),
        "recent_audit":AuditEvent.objects.select_related("actor")[:20],
        "top_users":top_users,
        "role_rows":role_rows,
        "db_ok":db_ok,"redis_ok":redis_ok,
        "reserved_username_count":ReservedUsername.objects.filter(active=True).count(),
        "username_conflicts":ReservedUsername.objects.filter(active=True,username__in=User.objects.exclude(handle__isnull=True).exclude(handle="").values_list("handle",flat=True)).count(),
        "moderation_pending":ModerationCase.objects.filter(status=ModerationCase.Status.PENDING).count(),
        "moderation_confirmed":ModerationCase.objects.filter(status__in=[ModerationCase.Status.CONFIRMED,ModerationCase.Status.ACTIONED]).count(),
        "moderation_queue":ModerationScanJob.objects.filter(status__in=[ModerationScanJob.Status.QUEUED,ModerationScanJob.Status.PROCESSING]).count(),
        "moderation_errors":ModerationScanJob.objects.filter(status=ModerationScanJob.Status.ERROR).count(),
        "moderation_worker_online":bool(cache.get("localgram:moderation_worker:alive")),
        "security_worker_online":bool(cache.get("localgram:security_worker:alive")),
        "dlp_open":DLPCase.objects.filter(status=DLPCase.Status.OPEN).count(),
        "malware_count":Attachment.objects.filter(scan_status="infected").count(),
        "security_scan_queue":AttachmentScanJob.objects.filter(status__in=[AttachmentScanJob.Status.QUEUED,AttachmentScanJob.Status.PROCESSING]).count(),
    })

@control_required(capability="users.view")
def users(request):
    q=request.GET.get("q","").strip()
    role=request.GET.get("role","").strip()
    status=request.GET.get("status","").strip()
    qs=User.objects.order_by("display_name","email")
    if q:
        uq=q.lstrip("@")
        qs=qs.filter(Q(email__icontains=uq)|Q(display_name__icontains=uq)|Q(handle__icontains=uq)|Q(role__icontains=uq))
    if role in dict(User.Role.choices):qs=qs.filter(role=role)
    if status=="blocked":qs=qs.filter(is_suspended=True)
    elif status=="active":qs=qs.filter(is_suspended=False,can_login=True,is_active=True)
    elif status=="login_off":qs=qs.filter(can_login=False)
    rows=list(qs[:1500])
    online_map=presence_snapshot([x.pk for x in rows])
    now=timezone.now()
    for item in rows:
        item.presence_hidden=not can_view_presence(request.user,item)
        item.presence_online=False if item.presence_hidden else bool(online_map.get(item.pk,False))
        item.presence_label=presence_label(request.user,item,now=now,online=item.presence_online)
    return render(request,"control/users.html",{
        "rows":rows,"q":q,"role_filter":role,"status_filter":status,"role_choices":User.Role.choices,
    })

@control_required(capability="users.view")
def user_detail(request,user_id):
    target=get_object_or_404(User,pk=user_id)
    before_custom_role_id=target.custom_role_id
    before_role=target.role
    form=UserAdminForm(request.POST or None,instance=target)
    if request.method=="POST" and request.user.has_capability("users.manage") and form.is_valid():
        if target.role in {User.Role.DEVELOPER,User.Role.SUPERADMIN} and not request.user.is_developer:
            messages.error(request,"Изменять developer/superadmin аккаунт может только developer.")
            return redirect("control:user_detail",user_id=target.pk)
        if form.cleaned_data.get("role") in {User.Role.DEVELOPER,User.Role.SUPERADMIN} and not request.user.is_developer:
            messages.error(request,"Назначать developer/superadmin может только developer.")
            return redirect("control:user_detail",user_id=target.pk)
        new_role=form.cleaned_data.get("role")
        if new_role!=before_role and not request.user.is_developer:
            actor_caps=capabilities_for(request.user)
            target_caps=set(BUILTIN_ROLE_CAPABILITIES.get(new_role,set()))
            if not target_caps.issubset(actor_caps):
                messages.error(request,"Нельзя назначить роль с правами выше ваших собственных.")
                return redirect("control:user_detail",user_id=target.pk)
        cleaned_custom=form.cleaned_data.get("custom_role")
        if (cleaned_custom.pk if cleaned_custom else None) != before_custom_role_id and not request.user.is_developer:
            messages.error(request,"Назначать кастомные RBAC-роли может только developer.")
            return redirect("control:user_detail",user_id=target.pk)
        before={k:getattr(target,k) for k in [
            "role","is_active","is_suspended","can_login","can_send_messages",
            "can_upload_files","can_create_groups","can_make_calls",
        ]}
        form.save()
        audit(request,"admin.user_update","User",str(target.pk),{"email":target.email,"before":before})
        messages.success(request,"Права и ограничения сохранены.")
        return redirect("control:user_detail",user_id=target.pk)

    tokens=target.api_tokens.order_by("-created_at")[:50]
    memberships=target.conversation_memberships.select_related("conversation").order_by("-conversation__updated_at")[:100]
    blocked_by=UserBlock.objects.filter(blocked=target).select_related("blocker")[:100]
    blocks=UserBlock.objects.filter(blocker=target).select_related("blocked")[:100]
    sent_count=target.sent_messages.count()
    deleted_sent=target.sent_messages.filter(is_deleted=True).count()
    login_rows=LoginEvent.objects.filter(user=target).order_by("-created_at")[:30]
    target.presence_hidden=not can_view_presence(request.user,target)
    target.presence_online=False if target.presence_hidden else bool(presence_snapshot([target.pk]).get(target.pk,False))
    target.presence_label=presence_label(request.user,target,online=target.presence_online)
    return render(request,"control/user_detail.html",{
        "target":target,"form":form,"tokens":tokens,"memberships":memberships,
        "blocked_by":blocked_by,"blocks":blocks,"sent_count":sent_count,
        "deleted_sent":deleted_sent,"login_rows":login_rows,
    })

@control_required(capability="users.manage")
@require_POST
def platform_toggle(request,user_id):
    target=get_object_or_404(User,pk=user_id)
    if target.role in {User.Role.DEVELOPER,User.Role.SUPERADMIN} and not request.user.is_developer:
        return HttpResponse("Developer/superadmin account cannot be blocked by this role.",status=403)
    target.is_suspended=not target.is_suspended
    target.can_login=not target.is_suspended
    if target.is_suspended and not target.suspend_reason:
        target.suspend_reason="Platform block by administrator"
    target.save(update_fields=["is_suspended","can_login","suspend_reason"])
    if target.is_suspended:
        for s in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                if str(s.get_decoded().get("_auth_user_id"))==str(target.pk):s.delete()
            except Exception:pass
        ApiToken.objects.filter(user=target,revoked_at__isnull=True).update(revoked_at=timezone.now())
    audit(request,"admin.platform_block" if target.is_suspended else "admin.platform_unblock","User",str(target.pk),{"email":target.email})
    messages.success(request,"Пользователь заблокирован на платформе." if target.is_suspended else "Пользователь разблокирован.")
    return redirect("control:user_detail",user_id=target.pk)

@control_required(capability="users.manage")
@require_POST
def revoke_sessions(request,user_id):
    target=get_object_or_404(User,pk=user_id);count=0
    for s in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            if str(s.get_decoded().get("_auth_user_id"))==str(target.pk):s.delete();count+=1
        except Exception:pass
    audit(request,"admin.sessions_revoke","User",str(target.pk),{"count":count,"email":target.email})
    messages.success(request,f"Веб-сессии отозваны: {count}.")
    return redirect("control:user_detail",user_id=target.pk)

@control_required(capability="users.manage")
@require_POST
def revoke_tokens(request,user_id):
    target=get_object_or_404(User,pk=user_id)
    count=ApiToken.objects.filter(user=target,revoked_at__isnull=True).update(revoked_at=timezone.now())
    audit(request,"admin.api_tokens_revoke","User",str(target.pk),{"count":count,"email":target.email})
    messages.success(request,f"API-токены отозваны: {count}.")
    return redirect("control:user_detail",user_id=target.pk)


@control_required(capability="policies.manage")
def reserved_usernames(request):
    import re

    if request.method=="POST":
        action=request.POST.get("action","")

        if action in {"assign","revoke_assignment"}:
            if not request.user.is_developer:
                messages.error(request,"Назначать защищённые имена может только разработчик.")
                return redirect("control:reserved_usernames")
            if action=="assign":
                username=ReservedUsername.normalize(request.POST.get("username"))
                identity=(request.POST.get("identity") or "").strip()
                if not re.fullmatch(r"[a-z0-9_]{4,32}",username or ""):
                    messages.error(request,"Username: 4–32 символа, только a-z, 0-9 и _.")
                    return redirect("control:reserved_usernames")
                lookup=Q(email__iexact=identity)|Q(handle__iexact=identity.lstrip("@"))
                if identity.isdigit():lookup|=Q(pk=int(identity))
                target=User.objects.filter(lookup).first()
                if not target:
                    messages.error(request,"Пользователь не найден. Укажите точный email, @username или ID.")
                    return redirect("control:reserved_usernames")
                occupied=User.objects.filter(handle__iexact=username).exclude(pk=target.pk).first()
                if occupied:
                    messages.error(request,f"@{username} уже принадлежит {occupied.email}.")
                    return redirect("control:reserved_usernames")
                with transaction.atomic():
                    obj,_=ReservedUsername.objects.select_for_update().get_or_create(
                        username=username,
                        defaults={"category":BUILTIN_MAP.get(username,ReservedUsername.Category.CUSTOM),"source":ReservedUsername.Source.CUSTOM,"created_by":request.user},
                    )
                    if obj.assigned_to_id and obj.assigned_to_id!=target.pk:
                        messages.error(request,f"@{username} уже назначен другому пользователю. Сначала отзовите его.")
                        return redirect("control:reserved_usernames")
                    old=ReservedUsername.objects.select_for_update().filter(assigned_to=target).exclude(pk=obj.pk).first()
                    if old:
                        old.assigned_to=None;old.assigned_by=None;old.assigned_at=None
                        old.save(update_fields=["assigned_to","assigned_by","assigned_at","updated_at"])
                    obj.active=True;obj.assigned_to=target;obj.assigned_by=request.user;obj.assigned_at=timezone.now()
                    obj.save(update_fields=["active","assigned_to","assigned_by","assigned_at","updated_at"])
                    target.handle=username;target.save(update_fields=["handle"])
                audit(request,"developer.reserved_username_assign","ReservedUsername",str(obj.pk),{"username":username,"user_id":target.pk,"email":target.email})
                messages.success(request,f"@{username} назначен пользователю {target.email}.")
                return redirect("control:reserved_usernames")
            obj=get_object_or_404(ReservedUsername,pk=request.POST.get("id"))
            target=obj.assigned_to
            if not target:
                messages.info(request,"Это имя никому не назначено.")
                return redirect(_reserved_username_next(request))
            with transaction.atomic():
                if (target.handle or "").lower()==obj.username:
                    target.handle=None;target.save(update_fields=["handle"])
                target_id=target.pk;target_email=target.email
                obj.assigned_to=None;obj.assigned_by=None;obj.assigned_at=None
                obj.save(update_fields=["assigned_to","assigned_by","assigned_at","updated_at"])
            audit(request,"developer.reserved_username_revoke","ReservedUsername",str(obj.pk),{"username":obj.username,"user_id":target_id,"email":target_email})
            messages.success(request,f"@{obj.username} отозван у {target_email}.")
            return redirect(_reserved_username_next(request))

        if action=="reserve_builtin":
            selected=set(request.POST.getlist("categories"))
            valid_categories=set(CATEGORY_LABELS)
            selected &= valid_categories
            if not selected:
                messages.error(request,"Выберите хотя бы одну категорию.")
                return redirect("control:reserved_usernames")
            created=updated=0
            for username,category in BUILTIN_CATALOG:
                if category not in selected:
                    continue
                obj,was_created=ReservedUsername.objects.get_or_create(
                    username=username,
                    defaults={
                        "category":category,
                        "source":ReservedUsername.Source.BUILTIN,
                        "active":True,
                        "note":"Встроенный каталог R-Mes",
                        "created_by":request.user,
                    },
                )
                if was_created:
                    created+=1
                else:
                    changed=False
                    if not obj.active:obj.active=True;changed=True
                    if obj.source!=ReservedUsername.Source.BUILTIN:obj.source=ReservedUsername.Source.BUILTIN;changed=True
                    if obj.category!=category:obj.category=category;changed=True
                    if changed:
                        obj.save(update_fields=["active","source","category","updated_at"])
                        updated+=1
            audit(request,"admin.reserved_usernames_builtin","ReservedUsername","bulk",{
                "categories":sorted(selected),"created":created,"updated":updated,
            })
            messages.success(request,f"Каталог применён: создано {created}, повторно включено/обновлено {updated}.")
            return redirect("control:reserved_usernames")

        if action=="import_custom":
            raw=request.POST.get("usernames","")
            category=request.POST.get("category",ReservedUsername.Category.CUSTOM)
            if category not in dict(ReservedUsername.Category.choices):
                category=ReservedUsername.Category.CUSTOM
            note=(request.POST.get("note") or "Ручной импорт")[:255]
            tokens=re.split(r"[\s,;]+",raw)
            created=updated=invalid=0
            seen=set()
            for token in tokens[:10000]:
                username=ReservedUsername.normalize(token)
                if not username or username in seen:
                    continue
                seen.add(username)
                if not re.fullmatch(r"[a-z0-9_]{4,32}",username):
                    invalid+=1
                    continue
                obj,was_created=ReservedUsername.objects.get_or_create(
                    username=username,
                    defaults={
                        "category":category,"source":ReservedUsername.Source.CUSTOM,
                        "active":True,"note":note,"created_by":request.user,
                    },
                )
                if was_created:
                    created+=1
                else:
                    obj.active=True
                    if obj.source==ReservedUsername.Source.CUSTOM:
                        obj.category=category
                        obj.note=note
                    obj.save(update_fields=["active","category","note","updated_at"])
                    updated+=1
            audit(request,"admin.reserved_usernames_import","ReservedUsername","bulk",{
                "created":created,"updated":updated,"invalid":invalid,"category":category,
            })
            messages.success(request,f"Импорт завершён: новых {created}, обновлено {updated}, пропущено {invalid}.")
            return redirect("control:reserved_usernames")

        if action=="reserve_one":
            username=ReservedUsername.normalize(request.POST.get("username"))
            category=BUILTIN_MAP.get(username,ReservedUsername.Category.CUSTOM)
            if re.fullmatch(r"[a-z0-9_]{4,32}",username or ""):
                obj,created=ReservedUsername.objects.get_or_create(
                    username=username,
                    defaults={
                        "category":category,
                        "source":ReservedUsername.Source.BUILTIN if username in BUILTIN_MAP else ReservedUsername.Source.CUSTOM,
                        "active":True,"created_by":request.user,
                    },
                )
                if not created and not obj.active:
                    obj.active=True;obj.save(update_fields=["active","updated_at"])
                audit(request,"admin.reserved_username_reserve","ReservedUsername",str(obj.pk),{"username":username})
                messages.success(request,f"@{username} зарезервирован.")
            return redirect(_reserved_username_next(request))

        if action=="toggle":
            obj=get_object_or_404(ReservedUsername,pk=request.POST.get("id"))
            if obj.assigned_to_id:
                messages.error(request,"Нельзя выключить назначенное имя. Сначала отзовите его у пользователя.")
                return redirect(_reserved_username_next(request))
            obj.active=not obj.active
            obj.save(update_fields=["active","updated_at"])
            audit(request,"admin.reserved_username_toggle","ReservedUsername",str(obj.pk),{
                "username":obj.username,"active":obj.active,
            })
            messages.success(request,f"@{obj.username}: резерв {'включён' if obj.active else 'выключен'}.")
            return redirect(_reserved_username_next(request))

        if action=="delete_custom":
            obj=get_object_or_404(ReservedUsername,pk=request.POST.get("id"))
            if obj.assigned_to_id:
                messages.error(request,"Нельзя удалить назначенное имя. Сначала отзовите его у пользователя.")
            elif obj.source!=ReservedUsername.Source.CUSTOM:
                messages.error(request,"Встроенную запись лучше выключить, а не удалять.")
            else:
                username=obj.username;obj.delete()
                audit(request,"admin.reserved_username_delete","ReservedUsername",str(request.POST.get("id")),{"username":username})
                messages.success(request,f"@{username} удалён из пользовательского резерва.")
            return redirect(_reserved_username_next(request))

        if action=="disable_category":
            category=request.POST.get("category","")
            if category in CATEGORY_LABELS:
                count=ReservedUsername.objects.filter(source=ReservedUsername.Source.BUILTIN,category=category,active=True,assigned_to__isnull=True).update(active=False)
                audit(request,"admin.reserved_usernames_disable_category","ReservedUsername","bulk",{"category":category,"count":count})
                messages.success(request,f"{CATEGORY_LABELS[category]}: резерв выключен для {count} записей.")
            return redirect("control:reserved_usernames")

    q=(request.GET.get("q") or "").strip().lower().lstrip("@")
    category_filter=(request.GET.get("category") or "").strip()
    state_filter=(request.GET.get("state") or "").strip()
    page_number=request.GET.get("page","1")

    reservations={x.username:x for x in ReservedUsername.objects.select_related("created_by","assigned_to","assigned_by").all()}
    users={x.handle:x for x in User.objects.exclude(handle__isnull=True).exclude(handle="").only("id","handle","display_name","email","role")}

    candidate_map={username:category for username,category in BUILTIN_CATALOG}
    for username,obj in reservations.items():
        if username not in candidate_map:
            candidate_map[username]=obj.category
    # Show every currently occupied @username even when it is outside the built-in catalog.
    for username in users:
        candidate_map.setdefault(username,ReservedUsername.Category.CUSTOM)
    # The search box also doubles as an availability checker for any syntactically valid handle.
    if q and re.fullmatch(r"[a-z0-9_]{4,32}",q):
        candidate_map.setdefault(q,ReservedUsername.Category.CUSTOM)

    rows=[]
    for username,category in candidate_map.items():
        res=reservations.get(username)
        occupant=users.get(username)
        if occupant:
            state="occupied"
        elif res and res.active:
            state="reserved"
        elif res and not res.active:
            state="inactive"
        else:
            state="free"
        source=res.source if res else (ReservedUsername.Source.BUILTIN if username in BUILTIN_MAP else ReservedUsername.Source.CUSTOM)
        row={
            "username":username,"category":category,"category_label":dict(ReservedUsername.Category.choices).get(category,CATEGORY_LABELS.get(category,category)),
            "reservation":res,"occupant":occupant,"state":state,"source":source,
            "is_builtin":username in BUILTIN_MAP,
            "is_reserved":bool(res and res.active),
        }
        if q:
            hay=" ".join([
                username,row["category_label"],occupant.display_name if occupant else "",
                occupant.email if occupant else "",res.note if res else "",
            ]).lower()
            if q not in hay:
                continue
        if category_filter and category!=category_filter:
            continue
        if state_filter and state!=state_filter:
            continue
        rows.append(row)

    state_order={"occupied":0,"reserved":1,"inactive":2,"free":3}
    rows.sort(key=lambda x:(state_order.get(x["state"],9),x["category_label"],x["username"]))

    builtin_names=set(BUILTIN_MAP)
    active_reserved=set(ReservedUsername.objects.filter(active=True).values_list("username",flat=True))
    occupied_names=set(users)
    builtin_occupied=len(builtin_names & occupied_names)
    builtin_reserved=len(builtin_names & active_reserved)
    builtin_free=len([x for x in builtin_names if x not in occupied_names and x not in active_reserved])
    conflicts=len(active_reserved & occupied_names)

    paginator=Paginator(rows,100)
    page_obj=paginator.get_page(page_number)

    category_stats=[]
    for key,label in CATEGORY_LABELS.items():
        names={u for u,c in BUILTIN_CATALOG if c==key}
        category_stats.append({
            "key":key,"label":label,"total":len(names),
            "reserved":len(names & active_reserved),
            "occupied":len(names & occupied_names),
        })

    return render(request,"control/reserved_usernames.html",{
        "page_obj":page_obj,"rows":page_obj.object_list,
        "q":q,"category_filter":category_filter,"state_filter":state_filter,
        "category_choices":ReservedUsername.Category.choices,
        "builtin_categories":CATEGORY_LABELS,
        "category_stats":category_stats,
        "builtin_total":len(builtin_names),"builtin_reserved":builtin_reserved,
        "builtin_occupied":builtin_occupied,"builtin_free":builtin_free,
        "conflicts":conflicts,
        "custom_count":ReservedUsername.objects.filter(source=ReservedUsername.Source.CUSTOM).count(),
        "assigned_rows":ReservedUsername.objects.filter(assigned_to__isnull=False).select_related("assigned_to","assigned_by").order_by("username"),
        "assigned_count":ReservedUsername.objects.filter(assigned_to__isnull=False).count(),
    })

@control_required()
def reserved_usernames_catalog_txt(request):
    response=HttpResponse(content_type="text/plain; charset=utf-8")
    response["Content-Disposition"]='attachment; filename="rmes_reserved_username_catalog.txt"'
    response.write("# R-Mes built-in reserved username catalog\\n")
    response.write(f"# Total: {len(BUILTIN_CATALOG)}\\n\\n")
    current=None
    for username,category in BUILTIN_CATALOG:
        if category!=current:
            current=category
            response.write(f"\\n# {CATEGORY_LABELS.get(category,category)}\\n")
        response.write(f"@{username}\\n")
    return response

@control_required(capability="chat.audit")
def conversations(request):
    q=request.GET.get("q","").strip()
    kind=request.GET.get("kind","").strip()
    qs=Conversation.objects.annotate(member_count=Count("members",distinct=True),message_count=Count("messages",distinct=True)).order_by("-updated_at")
    if q:
        uq=q.lstrip("@")
        qs=qs.filter(
            Q(title__icontains=q)|Q(messages__body__icontains=q)|
            Q(members__user__email__icontains=uq)|Q(members__user__display_name__icontains=uq)|
            Q(members__user__handle__icontains=uq)
        ).distinct()
    if kind in dict(Conversation.Kind.choices):qs=qs.filter(kind=kind)
    return render(request,"control/conversations.html",{
        "rows":qs[:1200],"q":q,"kind_filter":kind,"kind_choices":Conversation.Kind.choices,
    })

@developer_required
def conversation_audit(request,conversation_id):
    conv=get_object_or_404(Conversation,pk=conversation_id);q=request.GET.get("q","").strip()
    qs=conv.messages.select_related("sender","deleted_by").prefetch_related("attachments","revisions","hidden_for__user").order_by("-created_at")
    if q:qs=qs.filter(Q(body__icontains=q)|Q(sender__email__icontains=q)|Q(sender__display_name__icontains=q))
    deletions=conv.deletion_events.select_related("actor")[:100]
    audit(request,"developer.chat_forensic_read","Conversation",str(conv.pk),{"query":q})
    return render(request,"control/conversation_audit.html",{
        "conversation":conv,"rows":qs[:3000],"q":q,"deletions":deletions,
    })

@developer_required
def forensics(request):
    q=request.GET.get("q","").strip()
    deleted=Message.objects.filter(is_deleted=True).select_related("sender","conversation","deleted_by").prefetch_related("revisions","attachments")
    hidden=MessageHiddenFor.objects.select_related("message__sender","message__conversation","user").order_by("-created_at")
    chat_deletions=ChatDeletionEvent.objects.select_related("conversation","actor").order_by("-created_at")
    if q:
        deleted=deleted.filter(Q(body__icontains=q)|Q(sender__email__icontains=q)|Q(conversation__title__icontains=q))
        hidden=hidden.filter(Q(message__body__icontains=q)|Q(user__email__icontains=q)|Q(message__sender__email__icontains=q))
        chat_deletions=chat_deletions.filter(Q(actor__email__icontains=q)|Q(conversation__title__icontains=q))
    audit(request,"developer.forensics_open","Forensics","global",{"query":q})
    return render(request,"control/forensics.html",{
        "deleted_rows":deleted[:1000],"hidden_rows":hidden[:1000],"chat_deletions":chat_deletions[:1000],"q":q,
    })


@developer_required
def moderation_queue(request):
    q=request.GET.get("q","").strip()
    status=request.GET.get("status","pending").strip()
    kind=request.GET.get("kind","").strip()
    qs=ModerationCase.objects.select_related(
        "sender","conversation","message","attachment","reviewed_by"
    ).order_by("-created_at")
    if q:
        uq=q.lstrip("@")
        qs=qs.filter(
            Q(sender__email__icontains=uq)|Q(sender__display_name__icontains=uq)|
            Q(sender__handle__icontains=uq)|Q(text_snapshot__icontains=q)|
            Q(reason__icontains=q)|Q(detector__icontains=q)
        )
    if status in dict(ModerationCase.Status.choices):
        qs=qs.filter(status=status)
    elif status=="all":
        pass
    else:
        status="pending";qs=qs.filter(status=ModerationCase.Status.PENDING)
    if kind in dict(ModerationCase.Kind.choices):
        qs=qs.filter(kind=kind)

    paginator=Paginator(qs,80)
    page=paginator.get_page(request.GET.get("page"))
    audit(request,"developer.moderation_queue_open","ModerationCase","queue",{
        "query":q,"status":status,"kind":kind,
    })
    active_jobs=ModerationScanJob.objects.filter(
        status__in=[ModerationScanJob.Status.QUEUED,ModerationScanJob.Status.PROCESSING]
    ).select_related("attachment__message__sender","attachment__message__conversation","avatar_user").order_by("queued_at")[:100]
    recent_jobs=ModerationScanJob.objects.select_related(
        "attachment__message__sender","attachment__message__conversation","avatar_user"
    ).annotate(case_count=Count("attachment__moderation_cases")).order_by("-queued_at")[:100]
    return render(request,"control/moderation_queue.html",{
        "page_obj":page,"rows":page.object_list,"q":q,"status_filter":status,"kind_filter":kind,
        "status_choices":ModerationCase.Status.choices,"kind_choices":ModerationCase.Kind.choices,
        "pending_count":ModerationCase.objects.filter(status=ModerationCase.Status.PENDING).count(),
        "confirmed_count":ModerationCase.objects.filter(status=ModerationCase.Status.CONFIRMED).count(),
        "actioned_count":ModerationCase.objects.filter(status=ModerationCase.Status.ACTIONED).count(),
        "dismissed_count":ModerationCase.objects.filter(status=ModerationCase.Status.DISMISSED).count(),
        "queue_count":ModerationScanJob.objects.filter(status__in=[ModerationScanJob.Status.QUEUED,ModerationScanJob.Status.PROCESSING]).count(),
        "error_count":ModerationScanJob.objects.filter(status=ModerationScanJob.Status.ERROR).count(),
        "worker_online":bool(cache.get("localgram:moderation_worker:alive")),
        "active_jobs":active_jobs,
        "recent_jobs":recent_jobs,
        "exposed_threshold":settings.CONTENT_MODERATION_THRESHOLD,
        "covered_threshold":getattr(settings,"CONTENT_MODERATION_COVERED_THRESHOLD",0.50),
        "video_frames":settings.CONTENT_MODERATION_VIDEO_FRAMES,
        "error_jobs":ModerationScanJob.objects.filter(status=ModerationScanJob.Status.ERROR).select_related(
            "attachment__message__sender","avatar_user"
        ).order_by("-updated_at")[:20],
    })


@developer_required
def moderation_live(request):
    import importlib.util
    jobs=(ModerationScanJob.objects.select_related(
        "attachment__message__sender","attachment__message__conversation","avatar_user"
    ).prefetch_related("attachment__moderation_cases").order_by("-queued_at")[:100])
    rows=[]
    for job in jobs:
        attachment=job.attachment
        sender=job.avatar_user or (attachment.message.sender if attachment and attachment.message else None)
        if attachment:
            cases=list(attachment.moderation_cases.all())
        elif job.avatar_user_id:
            # Avatar moderation cases have no Attachment foreign key; include
            # them explicitly so the live 18+ console can show the actual case.
            cases=list(ModerationCase.objects.filter(
                sender_id=job.avatar_user_id,detector="nudenet-avatar"
            ).order_by("-created_at")[:10])
        else:
            cases=[]
        if cases:result=f"СРАБОТАЛО: {len(cases)}"
        elif job.status==ModerationScanJob.Status.DONE:result="Нарушение не найдено"
        elif job.status==ModerationScanJob.Status.ERROR:result="Ошибка проверки"
        else:result="Проверяется"
        rows.append({
            "id":job.pk,"queued_at":timezone.localtime(job.queued_at).strftime("%d.%m.%Y %H:%M:%S"),
            "status":job.status,"status_label":job.get_status_display(),
            "sender":sender.email if sender else "—",
            "chat":(attachment.message.conversation.title or "Личный чат") if attachment else "Фото профиля",
            "filename":attachment.original_name if attachment else "Фото профиля",
            "case_count":len(cases),"case_url":f"/control/moderation/{cases[0].pk}/" if cases else "",
            "result":result,"error":job.last_error[:240] if job.last_error else "",
            "retry_url":f"/control/moderation/jobs/{job.pk}/retry/" if job.status==ModerationScanJob.Status.ERROR else "",
        })
    return JsonResponse({
        "ok":True,"server_time":timezone.now().isoformat(),"rows":rows,
        "worker_online":bool(cache.get("localgram:moderation_worker:alive")),
        "queue_count":ModerationScanJob.objects.filter(status__in=[ModerationScanJob.Status.QUEUED,ModerationScanJob.Status.PROCESSING]).count(),
        "error_count":ModerationScanJob.objects.filter(status=ModerationScanJob.Status.ERROR).count(),
        "pending_count":ModerationCase.objects.filter(status=ModerationCase.Status.PENDING).count(),
        "detector_available":importlib.util.find_spec("nudenet") is not None,
    })


@developer_required
@require_POST
def moderation_self_test(request):
    """Actually initialize NudeNet and verify the worker heartbeat, not only imports."""
    try:
        from apps.moderation.services import _get_detector
        detector=_get_detector()
        detector_ready=detector is not None
        detector_error=""
    except Exception as exc:
        detector_ready=False
        detector_error=str(exc)[:400]
    worker_online=bool(cache.get("localgram:moderation_worker:alive"))
    audit(request,"developer.moderation_self_test","Moderation","engine",{
        "detector_ready":detector_ready,"worker_online":worker_online,
    })
    return JsonResponse({
        "ok":detector_ready and worker_online,
        "detector_ready":detector_ready,
        "worker_online":worker_online,
        "detail":"NudeNet и worker готовы." if detector_ready and worker_online else (detector_error or "Worker модерации не запущен."),
    },status=200 if detector_ready and worker_online else 503)


@developer_required
@require_POST
def moderation_job_retry(request,job_id):
    job=get_object_or_404(ModerationScanJob,pk=job_id)
    job.status=ModerationScanJob.Status.QUEUED
    job.attempts=0;job.last_error="";job.started_at=None;job.finished_at=None
    job.save(update_fields=["status","attempts","last_error","started_at","finished_at","updated_at"])
    audit(request,"developer.moderation_job_retry","ModerationScanJob",str(job.pk),{})
    return JsonResponse({"ok":True,"status":job.status})

@developer_required
def moderation_case(request,case_id):
    case=get_object_or_404(
        ModerationCase.objects.select_related(
            "sender","conversation","message","attachment","reviewed_by"
        ),
        pk=case_id,
    )
    audit(request,"developer.moderation_case_open","ModerationCase",str(case.pk),{
        "sender":case.sender.email if case.sender else None,
        "message_id":case.message_id,
    })
    sender_cases=ModerationCase.objects.filter(sender=case.sender) if case.sender_id else ModerationCase.objects.none()
    return render(request,"control/moderation_case.html",{"case":case,"sender_case_count":sender_cases.count(),"sender_confirmed_count":sender_cases.filter(status__in=[ModerationCase.Status.CONFIRMED,ModerationCase.Status.ACTIONED]).count(),"sender_risk_points":sender_cases.aggregate(v=Sum("risk_points"))["v"] or 0})


@developer_required
def moderation_evidence(request,case_id,kind):
    case=get_object_or_404(ModerationCase,pk=case_id)
    if kind=="preview":
        field=case.evidence_preview
        fallback_type="image/jpeg"
    elif kind=="file":
        field=case.evidence_file
        fallback_type="application/octet-stream"
    else:
        raise Http404
    if not field:
        raise Http404
    try:
        field.open("rb")
    except Exception:
        raise Http404
    content_type=mimetypes.guess_type(field.name)[0] or fallback_type
    download=request.GET.get("download")=="1"
    filename=field.name.rsplit("/",1)[-1]
    if kind=="file" or download:
        audit(request,"developer.moderation_evidence_read","ModerationCase",str(case.pk),{
            "kind":kind,"download":download,
        })
    return FileResponse(field,content_type=content_type,as_attachment=download,filename=filename)

@developer_required
@require_POST
def moderation_case_action(request,case_id):
    case=get_object_or_404(ModerationCase,pk=case_id)
    action=request.POST.get("action","")
    note=(request.POST.get("note") or "")[:4000]
    now=timezone.now()

    if action=="confirm":
        case.status=ModerationCase.Status.CONFIRMED
    elif action=="dismiss":
        case.status=ModerationCase.Status.DISMISSED
    elif action=="pending":
        case.status=ModerationCase.Status.PENDING
    elif action=="suspend":
        case.status=ModerationCase.Status.ACTIONED
        target=case.sender
        if target and not target.is_developer:
            target.is_suspended=True
            target.can_login=False
            target.suspend_reason=(f"Moderation case {case.pk}: {note or case.reason}")[:255]
            target.save(update_fields=["is_suspended","can_login","suspend_reason"])
            for session in Session.objects.filter(expire_date__gte=now):
                try:
                    if str(session.get_decoded().get("_auth_user_id"))==str(target.pk):
                        session.delete()
                except Exception:
                    pass
            ApiToken.objects.filter(user=target,revoked_at__isnull=True).update(revoked_at=now)
        elif target and target.is_developer:
            messages.error(request,"Developer-аккаунт нельзя автоматически заблокировать из moderation queue.")
            return redirect("control:moderation_case",case_id=case.pk)
    else:
        messages.error(request,"Неизвестное действие.")
        return redirect("control:moderation_case",case_id=case.pk)

    case.reviewed_by=request.user
    case.reviewed_at=now
    case.reviewer_note=note
    case.save(update_fields=["status","reviewed_by","reviewed_at","reviewer_note"])
    audit(request,"developer.moderation_case_action","ModerationCase",str(case.pk),{
        "action":action,"status":case.status,"sender_id":case.sender_id,
    })
    messages.success(request,"Решение по moderation case сохранено.")
    return redirect("control:moderation_case",case_id=case.pk)

AUDIT_CATEGORIES={
    "auth":("Авторизация",("auth.","login.","register.")),
    "chat":("Сообщения / чаты",("chat.","message.")),
    "profile":("Профиль",("profile.",)),
    "admin":("Администрирование",("admin.",)),
    "security":("Security / DLP",("security.","dlp.","antivirus.")),
    "moderation":("Moderation",("moderation.","developer.moderation")),
    "forensics":("Forensics",("developer.forensic","admin.chat_read")),
    "system":("Система",("system.",)),
}

def _audit_queryset(request):
    q=request.GET.get("q","").strip()
    category=request.GET.get("category","").strip()
    actor=request.GET.get("actor","").strip()
    object_type=request.GET.get("object_type","").strip()
    ip=request.GET.get("ip","").strip()
    date_from=request.GET.get("from","").strip()
    date_to=request.GET.get("to","").strip()
    qs=AuditEvent.objects.select_related("actor")
    if q:
        uq=q.lstrip("@")
        qs=qs.filter(
            Q(action__icontains=q)|Q(object_type__icontains=q)|Q(object_id__icontains=q)|
            Q(actor__email__icontains=uq)|Q(actor__display_name__icontains=uq)|
            Q(actor__handle__icontains=uq)|Q(ip_address__icontains=q)
        )
    if actor:
        ua=actor.lstrip("@")
        qs=qs.filter(Q(actor__email__icontains=ua)|Q(actor__display_name__icontains=ua)|Q(actor__handle__icontains=ua))
    if object_type:qs=qs.filter(object_type__iexact=object_type)
    if ip:qs=qs.filter(ip_address__icontains=ip)
    if date_from:qs=qs.filter(created_at__date__gte=date_from)
    if date_to:qs=qs.filter(created_at__date__lte=date_to)
    if category in AUDIT_CATEGORIES:
        prefixes=AUDIT_CATEGORIES[category][1]
        category_q=Q()
        for prefix in prefixes:category_q|=Q(action__istartswith=prefix)
        qs=qs.filter(category_q)
    return qs,{
        "q":q,"category_filter":category,"actor_filter":actor,"object_filter":object_type,
        "ip_filter":ip,"date_from":date_from,"date_to":date_to,
    }

def _audit_category(action):
    action=action or ""
    for key,(label,prefixes) in AUDIT_CATEGORIES.items():
        if any(action.startswith(x) for x in prefixes):return key,label
    return "other","Другое"

def _audit_title(action):
    action=action or ""
    labels={
        "admin.user_update":"Изменены права пользователя",
        "admin.platform_block":"Пользователь заблокирован на платформе",
        "admin.platform_unblock":"Пользователь разблокирован",
        "admin.sessions_revoke":"Завершены web-сессии",
        "admin.api_tokens_revoke":"Отозваны API-токены",
        "chat.message_edit":"Сообщение изменено",
        "chat.message_delete":"Сообщение удалено",
        "chat.file_upload":"Загружен файл",
        "chat.personal_settings":"Изменены настройки чата",
        "profile.autosave":"Профиль сохранён",
        "profile.preferences_autosave":"Настройки профиля сохранены",
        "developer.moderation_case_open":"Открыт moderation case",
        "developer.moderation_case_action":"Принято решение moderation",
        "developer.moderation_evidence_read":"Открыт moderation evidence",
        "developer.moderation_queue_open":"Открыта очередь moderation",
    }
    return labels.get(action,action.replace("."," → ").replace("_"," ").strip().capitalize())

@control_required(capability="audit.view")
def audit_log(request):
    qs,filters=_audit_queryset(request)
    paginator=Paginator(qs,100)
    page=paginator.get_page(request.GET.get("page"))
    rows=[]
    for event in page.object_list:
        key,label=_audit_category(event.action)
        rows.append({
            "event":event,"category":key,"category_label":label,"title":_audit_title(event.action),
            "metadata_pretty":json.dumps(event.metadata or {},ensure_ascii=False,indent=2,default=str),
        })
    object_types=list(AuditEvent.objects.exclude(object_type="").values_list("object_type",flat=True).distinct().order_by("object_type")[:100])
    return render(request,"control/audit_log.html",{
        "rows":rows,"page_obj":page,"categories":[(k,v[0]) for k,v in AUDIT_CATEGORIES.items()],
        "object_types":object_types,**filters,
    })

@control_required(capability="audit.export")
def audit_export(request):
    qs,filters=_audit_queryset(request)
    response=HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"]=f'attachment; filename="rmes_audit_{timezone.localdate().isoformat()}.csv"'
    response.write("\ufeff")
    writer=csv.writer(response)
    writer.writerow(["time","category","actor","actor_email","ip","action","object_type","object_id","user_agent","metadata"])
    for event in qs.iterator(chunk_size=1000):
        key,label=_audit_category(event.action)
        writer.writerow([
            timezone.localtime(event.created_at).isoformat(),label,
            event.actor.display_name if event.actor else "system",
            event.actor.email if event.actor else "",
            event.ip_address or "",event.action,event.object_type,event.object_id,
            event.user_agent,json.dumps(event.metadata or {},ensure_ascii=False,default=str),
        ])
    audit(request,"admin.audit_export","AuditEvent","export",filters)
    return response

@control_required(capability="security.view")
def login_log(request):
    q=request.GET.get("q","").strip();result=request.GET.get("result","").strip()
    qs=LoginEvent.objects.select_related("user")
    if q:qs=qs.filter(Q(email__icontains=q)|Q(ip_address__icontains=q)|Q(reason__icontains=q)|Q(user_agent__icontains=q))
    if result=="success":qs=qs.filter(successful=True)
    elif result=="failed":qs=qs.filter(successful=False)
    return render(request,"control/login_log.html",{"rows":qs[:3000],"q":q,"result_filter":result})

@control_required(capability="policies.manage")
def domains(request):
    form=DomainForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        obj=form.save();audit(request,"admin.domain_create","CorporateDomain",str(obj.pk),{"domain":obj.domain});return redirect("control:domains")
    return render(request,"control/domains.html",{"rows":CorporateDomain.objects.order_by("domain"),"form":form})

@control_required(capability="policies.manage")
@require_POST
def domain_delete(request,domain_id):
    obj=get_object_or_404(CorporateDomain,pk=domain_id);name=obj.domain;obj.delete()
    audit(request,"admin.domain_delete","CorporateDomain",str(domain_id),{"domain":name});return redirect("control:domains")

@control_required(capability="policies.manage")
def ip_rules(request):
    form=IPRuleForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        obj=form.save(commit=False);obj.created_by=request.user;obj.save()
        audit(request,"admin.ip_rule_create","IPAccessRule",str(obj.pk),{"network":obj.network,"action":obj.action});return redirect("control:ip_rules")
    return render(request,"control/ip_rules.html",{"rows":IPAccessRule.objects.order_by("-created_at"),"form":form})

@control_required(capability="policies.manage")
@require_POST
def ip_delete(request,rule_id):
    obj=get_object_or_404(IPAccessRule,pk=rule_id);meta={"network":obj.network,"action":obj.action};obj.delete()
    audit(request,"admin.ip_rule_delete","IPAccessRule",str(rule_id),meta);return redirect("control:ip_rules")

@control_required(write=True)
def settings_view(request):
    keys=[
        ("app_name","Название приложения"),
        ("monitoring_notice","Текст уведомления о корпоративном мониторинге"),
        ("support_contact","Контакт внутренней поддержки"),
        ("company_name","Название компании"),
    ]
    rows=[]
    for key,desc in keys:
        obj,_=AppSetting.objects.get_or_create(key=key,defaults={"description":desc});rows.append(obj)
    if request.method=="POST":
        key=request.POST.get("key");obj=get_object_or_404(AppSetting,key=key)
        obj.value=request.POST.get("value","")[:10000];obj.updated_by=request.user;obj.save()
        audit(request,"admin.setting_update","AppSetting",key,{})
        return redirect("control:settings")
    return render(request,"control/settings.html",{
        "rows":rows,"smtp_host":settings.EMAIL_HOST,"smtp_port":settings.EMAIL_PORT,
        "smtp_user":settings.EMAIL_HOST_USER,"smtp_tls":settings.EMAIL_USE_TLS,
        "login_2fa":settings.LOGIN_EMAIL_2FA,"max_upload_mb":settings.MAX_UPLOAD_MB,
        "moderation_enabled":settings.CONTENT_MODERATION_ENABLED,
        "moderation_text_enabled":settings.CONTENT_MODERATION_TEXT_ENABLED,
        "moderation_media_enabled":settings.CONTENT_MODERATION_MEDIA_ENABLED,
        "moderation_threshold":settings.CONTENT_MODERATION_THRESHOLD,
        "moderation_notice":settings.CONTENT_MODERATION_POLICY_NOTICE,
    })

@control_required(write=True)
@require_POST
def smtp_test(request):
    recipient=(request.POST.get("recipient") or request.user.email).strip()
    try:
        send_mail("R-Messanger SMTP test","SMTP настроен правильно. Это тестовое письмо R-Messanger.",settings.DEFAULT_FROM_EMAIL,[recipient],fail_silently=False)
        audit(request,"admin.smtp_test","Email",recipient,{"host":settings.EMAIL_HOST})
        messages.success(request,f"Тестовое письмо отправлено на {recipient}.")
    except Exception as exc:
        audit(request,"admin.smtp_test_failed","Email",recipient,{"error":str(exc)[:500]})
        messages.error(request,f"SMTP ошибка: {exc}")
    return redirect("control:settings")

@developer_required
def export_messages(request):
    response=HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"]='attachment; filename="rmes_forensic_messages.csv"';response.write("\ufeff")
    wr=csv.writer(response)
    wr.writerow(["id","conversation_id","sender","kind","created_at","edited_at","deleted","deleted_by","body"])
    for m in Message.objects.select_related("sender","deleted_by").iterator(chunk_size=2000):
        wr.writerow([
            m.pk,m.conversation_id,m.sender.email if m.sender else "",m.kind,m.created_at.isoformat(),
            m.edited_at.isoformat() if m.edited_at else "",m.is_deleted,
            m.deleted_by.email if m.deleted_by else "",m.body,
        ])
    audit(request,"developer.messages_export","Message","all",{})
    return response

@control_required(capability="security.view")
def security_center(request):
    now=timezone.now();since=now-timedelta(days=30)
    users=User.objects.filter(is_active=True)
    if not request.user.is_developer:users=users.exclude(role=User.Role.DEVELOPER)
    risk=[]
    severity_points={"low":1,"medium":3,"high":7,"critical":15}
    for u in users[:2000]:
        failed=LoginEvent.objects.filter(user=u,successful=False,created_at__gte=since).count()
        dlp=list(DLPCase.objects.filter(sender=u,status=DLPCase.Status.OPEN,created_at__gte=since).values_list("severity",flat=True))
        mod_qs=ModerationCase.objects.filter(sender=u,status__in=[ModerationCase.Status.CONFIRMED,ModerationCase.Status.ACTIONED],created_at__gte=since)
        mod_confirmed=mod_qs.count()
        mod_risk=mod_qs.aggregate(v=Sum("risk_points"))["v"] or 0
        malware=SecurityIncident.objects.filter(user=u,kind=SecurityIncident.Kind.MALWARE,created_at__gte=since).count()
        blocks=UserBlock.objects.filter(blocked=u).count()
        rate_events=RateLimitEvent.objects.filter(user=u,created_at__gte=since).count()
        suspicious_devices=DeviceSession.objects.filter(user=u,revoked_at__isnull=True,trust_status__in=[DeviceSession.Trust.SUSPICIOUS,DeviceSession.Trust.BLOCKED]).count()
        score=min(100,failed+sum(severity_points.get(x,2) for x in dlp)+mod_risk+malware*25+blocks*2+min(20,rate_events*2)+suspicious_devices*8)
        if score or u.is_suspended:risk.append({"user":u,"score":score,"failed":failed,"dlp":len(dlp),"moderation":mod_confirmed,"malware":malware,"blocks":blocks,"rate_events":rate_events,"suspicious_devices":suspicious_devices})
    risk.sort(key=lambda x:(-x["score"],x["user"].display_name))
    return render(request,"control/security_center.html",{
        "risk_rows":risk[:150],"dlp_open":DLPCase.objects.filter(status=DLPCase.Status.OPEN).count(),
        "dlp_critical":DLPCase.objects.filter(status=DLPCase.Status.OPEN,severity=DLPCase.Severity.CRITICAL).count(),
        "malware_count":Attachment.objects.filter(scan_status="infected").count(),
        "failed_logins_24h":LoginEvent.objects.filter(successful=False,created_at__gte=now-timedelta(hours=24)).count(),
        "new_devices_24h":(
            DeviceSession.objects.filter(created_at__gte=now-timedelta(hours=24))
            .exclude(user__role=User.Role.DEVELOPER).count()
            if not request.user.is_developer
            else DeviceSession.objects.filter(created_at__gte=now-timedelta(hours=24)).count()
        ),
        "security_worker_online":bool(cache.get("localgram:security_worker:alive")),
        "moderation_worker_online":bool(cache.get("localgram:moderation_worker:alive")),
        "scheduler_worker_online":bool(cache.get("localgram:scheduler_worker:alive")),
        "scan_queue":AttachmentScanJob.objects.filter(status__in=[AttachmentScanJob.Status.QUEUED,AttachmentScanJob.Status.PROCESSING]).count(),
        "rate_limit_24h":RateLimitEvent.objects.filter(created_at__gte=now-timedelta(hours=24)).count(),
        "suspicious_devices":(DeviceSession.objects.filter(revoked_at__isnull=True,trust_status__in=[DeviceSession.Trust.SUSPICIOUS,DeviceSession.Trust.BLOCKED]).exclude(user__role=User.Role.DEVELOPER).count() if not request.user.is_developer else DeviceSession.objects.filter(revoked_at__isnull=True,trust_status__in=[DeviceSession.Trust.SUSPICIOUS,DeviceSession.Trust.BLOCKED]).count()),
        "recent_rate_events":RateLimitEvent.objects.select_related("user")[:25],
        "last_backup_verification":BackupVerification.objects.first(),
        "recent_incidents":SecurityIncident.objects.select_related("user")[:30],
    })

@control_required(capability="security.view")
def dlp_cases(request):
    q=request.GET.get("q","").strip();status=request.GET.get("status","open");severity=request.GET.get("severity","")
    qs=DLPCase.objects.select_related("sender","conversation","message","attachment","reviewed_by")
    if q:
        uq=q.lstrip("@");qs=qs.filter(Q(sender__email__icontains=uq)|Q(sender__handle__icontains=uq)|Q(sender__display_name__icontains=uq)|Q(rule__icontains=q)|Q(excerpt__icontains=q))
    if status in dict(DLPCase.Status.choices):qs=qs.filter(status=status)
    elif status!="all":status="open";qs=qs.filter(status=DLPCase.Status.OPEN)
    if severity in dict(DLPCase.Severity.choices):qs=qs.filter(severity=severity)
    page=Paginator(qs,100).get_page(request.GET.get("page"))
    return render(request,"control/dlp_cases.html",{"rows":page.object_list,"page_obj":page,"q":q,"status_filter":status,"severity_filter":severity,"status_choices":DLPCase.Status.choices,"severity_choices":DLPCase.Severity.choices})

@control_required(capability="security.view")
def dlp_case_detail(request,case_id):
    case=get_object_or_404(DLPCase.objects.select_related("sender","conversation","message","attachment","reviewed_by"),pk=case_id)
    audit(request,"security.dlp_case_open","DLPCase",str(case.pk),{})
    return render(request,"control/dlp_case.html",{"case":case})

@control_required(capability="security.manage")
@require_POST
def dlp_case_action(request,case_id):
    case=get_object_or_404(DLPCase,pk=case_id);action=request.POST.get("action")
    if action=="review":case.status=DLPCase.Status.REVIEWED
    elif action=="dismiss":case.status=DLPCase.Status.DISMISSED
    elif action=="open":case.status=DLPCase.Status.OPEN
    else:return redirect("control:dlp_case_detail",case_id=case.pk)
    case.reviewed_by=request.user;case.reviewed_at=timezone.now();case.reviewer_note=(request.POST.get("note") or "")[:4000];case.save(update_fields=["status","reviewed_by","reviewed_at","reviewer_note"])
    audit(request,"security.dlp_case_action","DLPCase",str(case.pk),{"action":action})
    return redirect("control:dlp_case_detail",case_id=case.pk)

@control_required(capability="security.view")
def antivirus(request):
    q=request.GET.get("q","").strip();status=request.GET.get("status","infected")
    qs=Attachment.objects.select_related("message__sender","message__conversation").order_by("-scanned_at","-created_at")
    if status in {"pending","safe","infected","error"}:qs=qs.filter(scan_status=status)
    if q:qs=qs.filter(Q(original_name__icontains=q)|Q(sha256__icontains=q)|Q(scan_signature__icontains=q)|Q(message__sender__email__icontains=q))
    page=Paginator(qs,100).get_page(request.GET.get("page"))
    return render(request,"control/antivirus.html",{"rows":page.object_list,"page_obj":page,"q":q,"status_filter":status,"security_worker_online":bool(cache.get("localgram:security_worker:alive")),"queue":AttachmentScanJob.objects.filter(status__in=[AttachmentScanJob.Status.QUEUED,AttachmentScanJob.Status.PROCESSING]).count()})

@control_required(capability="security.view")
def device_sessions_admin(request):
    q=request.GET.get("q","").strip();qs=DeviceSession.objects.select_related("user").filter(revoked_at__isnull=True).order_by("-last_seen_at")
    if not request.user.is_developer:qs=qs.exclude(user__role=User.Role.DEVELOPER)
    if q:
        uq=q.lstrip("@");qs=qs.filter(Q(user__email__icontains=uq)|Q(user__handle__icontains=uq)|Q(user__display_name__icontains=uq)|Q(device_name__icontains=q)|Q(ip_address__icontains=q)|Q(platform__icontains=q))
    page=Paginator(qs,150).get_page(request.GET.get("page"))
    return render(request,"control/device_sessions.html",{"rows":page.object_list,"page_obj":page,"q":q})

@control_required(capability="security.manage")
@require_POST
def device_session_revoke_admin(request,device_id):
    qs=DeviceSession.objects.select_related("user").filter(pk=device_id,revoked_at__isnull=True)
    if not request.user.is_developer:qs=qs.exclude(user__role=User.Role.DEVELOPER)
    d=get_object_or_404(qs);now=timezone.now();d.revoked_at=now;d.is_current=False;d.save(update_fields=["revoked_at","is_current"]);DeviceToken.objects.filter(device=d,revoked_at__isnull=True).update(revoked_at=now)
    if d.session_key:Session.objects.filter(session_key=d.session_key).delete()
    audit(request,"security.admin_device_revoke","DeviceSession",str(d.pk),{"target_user":d.user_id})
    return redirect("control:device_sessions")

@developer_required
def rbac_roles(request):
    from django.utils.text import slugify
    if request.method=="POST":
        action=request.POST.get("action","save")
        if action=="delete":
            row=get_object_or_404(RoleProfile,pk=request.POST.get("role_id"))
            if row.users.exists():
                messages.error(request,"Сначала сними эту роль с пользователей.")
            else:
                audit(request,"admin.rbac_delete","RoleProfile",str(row.pk),{"name":row.name});row.delete();messages.success(request,"Кастомная роль удалена.")
            return redirect("control:rbac_roles")
        role_id=request.POST.get("role_id")
        row=RoleProfile.objects.filter(pk=role_id).first() if role_id else RoleProfile()
        name=(request.POST.get("name") or "").strip()[:80]
        if not name:
            messages.error(request,"Укажи название роли.");return redirect("control:rbac_roles")
        row.name=name;row.slug=slugify(request.POST.get("slug") or name)[:80] or f"role-{timezone.now().timestamp():.0f}"
        requested=set(request.POST.getlist("permissions"))
        # developer-only boundaries never delegated to custom roles.
        requested.discard("rbac.manage")
        row.permissions=sorted(x for x in requested if x in CAPABILITIES)
        row.description=(request.POST.get("description") or "")[:255];row.active=request.POST.get("active")=="on";row.updated_by=request.user
        try:row.save()
        except Exception as exc:
            messages.error(request,f"Не удалось сохранить роль: {exc}");return redirect("control:rbac_roles")
        audit(request,"admin.rbac_save","RoleProfile",str(row.pk),{"permissions":row.permissions});messages.success(request,"RBAC-роль сохранена.")
        return redirect("control:rbac_roles")
    return render(request,"control/rbac_roles.html",{"roles":RoleProfile.objects.annotate(user_count=Count("users")),"capabilities":CAPABILITIES})

@control_required(capability="backup.view")
def backup_center(request):
    rows=BackupVerification.objects.select_related("created_by")[:100]
    last=rows[0] if rows else None
    return render(request,"control/backup_center.html",{"rows":rows,"last":last})

@developer_required
def client_versions(request):
    if request.method=="POST":
        platform=request.POST.get("platform")
        if platform not in dict(ClientVersionPolicy.Platform.choices):
            messages.error(request,"Неизвестная платформа.");return redirect("control:client_versions")
        row,_=ClientVersionPolicy.objects.get_or_create(platform=platform)
        row.latest_version=(request.POST.get("latest_version") or row.latest_version)[:32]
        row.minimum_version=(request.POST.get("minimum_version") or row.minimum_version)[:32]
        row.update_url=(request.POST.get("update_url") or "").strip()
        row.release_notes=(request.POST.get("release_notes") or "")[:12000]
        row.force_update=request.POST.get("force_update")=="on";row.enabled=request.POST.get("enabled")=="on";row.updated_by=request.user;row.save()
        audit(request,"admin.client_policy_update","ClientVersionPolicy",str(row.pk),{"platform":platform,"latest":row.latest_version,"minimum":row.minimum_version});messages.success(request,"Политика версии клиента сохранена.")
        return redirect("control:client_versions")
    policies={x.platform:x for x in ClientVersionPolicy.objects.all()}
    rows=[]
    for value,label in ClientVersionPolicy.Platform.choices:
        rows.append({"value":value,"label":label,"row":policies.get(value)})
    return render(request,"control/client_versions.html",{"rows":rows})

@control_required(capability="security.manage")
@require_POST
def device_trust_action(request,device_id):
    qs=DeviceSession.objects.select_related("user").filter(pk=device_id,revoked_at__isnull=True)
    if not request.user.is_developer:qs=qs.exclude(user__role=User.Role.DEVELOPER)
    device=get_object_or_404(qs)
    status=request.POST.get("status")
    if status not in dict(DeviceSession.Trust.choices):return HttpResponse("Invalid trust status",status=400)
    device.trust_status=status;device.trust_reason=(request.POST.get("reason") or "")[:255];device.save(update_fields=["trust_status","trust_reason"])
    if status==DeviceSession.Trust.BLOCKED:
        DeviceToken.objects.filter(device=device,revoked_at__isnull=True).update(revoked_at=timezone.now())
        if device.session_key:Session.objects.filter(session_key=device.session_key).delete()
    audit(request,"security.device_trust","DeviceSession",str(device.pk),{"status":status,"target_user":device.user_id})
    messages.success(request,"Device trust обновлён.")
    return redirect("control:device_sessions")

@control_required()
def infrastructure_status(request):
    now=timezone.now();db_ok=redis_ok=storage_ok=clamav_ok=False;db_version="";db_connections=None;clamav_version=""
    try:
        with connection.cursor() as cursor:
            cursor.execute("select version()");db_version=(cursor.fetchone() or [""])[0]
            if connection.vendor=="postgresql":
                cursor.execute("select count(*) from pg_stat_activity");db_connections=(cursor.fetchone() or [0])[0]
        db_ok=True
    except Exception as exc:db_version=str(exc)[:220]
    try:
        cache.set("infra:probe","ok",10);redis_ok=cache.get("infra:probe")=="ok"
    except Exception:pass
    try:
        storage_ok=default_storage.exists("__localgram_infra_probe_missing__") is False
    except Exception:storage_ok=False
    try:
        import clamd
        c=clamd.ClamdNetworkSocket(settings.CLAMAV_HOST,settings.CLAMAV_PORT,timeout=5);clamav_ok=c.ping()=="PONG";clamav_version=c.version() or ""
    except Exception:pass
    return render(request,"control/infrastructure_status.html",{
        "db_ok":db_ok,"db_version":db_version,"db_connections":db_connections,"redis_ok":redis_ok,"storage_ok":storage_ok,"clamav_ok":clamav_ok,"clamav_version":clamav_version,
        "security_worker":bool(cache.get("localgram:security_worker:alive")),"moderation_worker":bool(cache.get("localgram:moderation_worker:alive")),"scheduler_worker":bool(cache.get("localgram:scheduler_worker:alive")),
        "users_online":sum(1 for online in presence_snapshot(User.objects.values_list("id",flat=True)).values() if online),"messages_hour":Message.objects.filter(created_at__gte=now-timedelta(hours=1)).count(),
        "security_queue":AttachmentScanJob.objects.filter(status__in=["queued","processing"]).count(),"moderation_queue":ModerationScanJob.objects.filter(status__in=["queued","processing"]).count(),
        "storage_bytes":Attachment.objects.aggregate(v=Sum("size"))["v"] or 0,"last_backup":BackupVerification.objects.first(),
    })


@developer_required
def call_records_admin(request):
    q=(request.GET.get("q") or "").strip()
    status=(request.GET.get("status") or "").strip()
    qs=CallRecord.objects.select_related("caller","callee","conversation").order_by("-started_at")
    if q:
        qs=qs.filter(Q(call_id__icontains=q)|Q(caller__display_name__icontains=q)|Q(caller__email__icontains=q)|Q(callee__display_name__icontains=q)|Q(callee__email__icontains=q))
    if status in dict(CallRecord.Status.choices):qs=qs.filter(status=status)
    page=Paginator(qs,80).get_page(request.GET.get("page"))
    return render(request,"control/call_records.html",{"rows":page.object_list,"page_obj":page,"q":q,"status_filter":status,"status_choices":CallRecord.Status.choices})

@developer_required
def call_recording_content(request,record_id):
    row=get_object_or_404(CallRecord,pk=record_id)
    if not row.recording:raise Http404
    try:fh=row.recording.open("rb")
    except Exception:raise Http404
    audit(request,"control.call_recording_read","CallRecord",str(row.pk),{"call_id":row.call_id})
    response=FileResponse(fh,content_type=row.recording_content_type or "application/octet-stream")
    response["Content-Disposition"]=f'inline; filename="call-{row.call_id}.webm"'
    response["Cache-Control"]="private, no-store"
    return response
