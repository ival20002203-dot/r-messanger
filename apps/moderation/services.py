import hashlib
import logging
import re
import tempfile
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile,File
from django.db import transaction
from django.utils import timezone
from PIL import Image,ImageOps

from .models import ModerationCase,ModerationScanJob

log=logging.getLogger(__name__)

EXPLICIT_TEXT_TERMS={
    # English / common Internet terms
    "porn","porno","pornography","nsfw","nude","nudes","naked","xxx","hentai","erotic","erotica",
    "sex video","sex photo","onlyfans","nudes pack","adult video","adult photo",
    # Russian
    "порно","порнография","обнажен","обнажён","голая","голый","голые","эротика",
    "интим фото","интимное фото","интимные фото","интимка","нюдс","нюдсы","обнаженка","обнажёнка","секс видео","секс фото",
    # Uzbek / transliterations often seen in internal chat
    "yalangoch","yalang'och","porno video","porno foto","seks video","seks foto",
}
EXPLICIT_URL_HINTS=("porn","xxx","hentai","adult","nsfw","onlyfans")

EXPLICIT_NUDENET_LABELS={
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
}
SENSITIVE_COVERED_NUDENET_LABELS={
    "FEMALE_BREAST_COVERED",
    "FEMALE_GENITALIA_COVERED",
    "MALE_GENITALIA_COVERED",
    "ANUS_COVERED",
    "BUTTOCKS_COVERED",
}

_detector=None

def moderation_enabled():
    return bool(getattr(settings,"CONTENT_MODERATION_ENABLED",True))

def _normalize_text(value):
    return re.sub(r"\s+"," ",(value or "").lower()).strip()


POLICY_TEXT_TERMS={
    "sexual": set(EXPLICIT_TEXT_TERMS),
    "violence": {"kill him","kill her","murder","shooting","beheading","убить","убийство","расстрел","казнь","убью","взорвать человека"},
    "drugs": {"cocaine","heroin","methamphetamine","meth","fentanyl","кокаин","героин","метамфетамин","наркотики","закладка наркотиков","drug sale"},
    "hate": {"racial supremacy","ethnic cleansing","genocide advocacy","расовое превосходство","этническая чистка","призывы к геноциду"},
}
POLICY_RISK={"sexual":8,"violence":9,"drugs":7,"hate":10}

def _policy_matches(text):
    normalized=_normalize_text(text);out={}
    for category,terms in POLICY_TEXT_TERMS.items():
        hits=sorted({term for term in terms if term in normalized})
        if category=="sexual":
            urls=re.findall(r"https?://[^\s<>()]+",normalized)
            if any(any(hint in url for hint in EXPLICIT_URL_HINTS) for url in urls):hits.append("adult-link")
        if hits:out[category]=sorted(set(hits))
    return out

def _ocr_image(source):
    if not getattr(settings,"CONTENT_MODERATION_OCR_ENABLED",True):return ""
    try:
        import pytesseract
        img=Image.open(BytesIO(source) if isinstance(source,(bytes,bytearray)) else source)
        img=ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((1800,1800))
        return pytesseract.image_to_string(img,lang=getattr(settings,"CONTENT_MODERATION_OCR_LANG","eng+rus"))[:12000]
    except Exception:
        log.exception("OCR moderation failed");return ""

def _create_ocr_cases(sender,conversation,message,attachment,ocr_text,kind=ModerationCase.Kind.IMAGE):
    cases=[]
    for category,hits in _policy_matches(ocr_text).items():
        detector="ocr-policy-v1"
        if ModerationCase.objects.filter(message=message,attachment=attachment,detector=detector,policy_category=category,ocr_text=ocr_text[:12000]).exists():continue
        score=min(.95,.55+.07*len(hits))
        case=ModerationCase.objects.create(kind=kind,sender=sender,conversation=conversation,message=message,attachment=attachment,detector=detector,policy_category=category,risk_points=POLICY_RISK.get(category,5),score=score,labels=hits,reason=f"OCR обнаружил текстовые индикаторы категории {category}. Требуется ручная проверка.",text_snapshot=message.body if message else "",ocr_text=ocr_text[:12000])
        if attachment:_copy_evidence(case,attachment)
        case.save(update_fields=["evidence_file","evidence_sha256"]);cases.append(case)
    return cases

def _text_matches(text):
    normalized=_normalize_text(text)
    matches=sorted({term for term in EXPLICIT_TEXT_TERMS if term in normalized})
    urls=re.findall(r"https?://[^\s<>()]+",normalized)
    for url in urls:
        if any(hint in url for hint in EXPLICIT_URL_HINTS):
            matches.append("adult-link")
            break
    return sorted(set(matches))

def moderate_text_message(message):
    if not moderation_enabled() or not getattr(settings,"CONTENT_MODERATION_TEXT_ENABLED",True):
        return None
    if not message or not message.body:return None
    created=[]
    for category,matches in _policy_matches(message.body).items():
        detector="text-policy-v2"
        existing=ModerationCase.objects.filter(message=message,detector=detector,policy_category=category,text_snapshot=message.body).first()
        if existing:
            created.append(existing);continue
        score=min(0.99,0.53+0.08*len(matches))
        created.append(ModerationCase.objects.create(
            kind=ModerationCase.Kind.TEXT,sender=message.sender,conversation=message.conversation,message=message,
            detector=detector,policy_category=category,risk_points=POLICY_RISK.get(category,5),score=score,labels=matches,
            reason=f"Текстовые индикаторы категории {category}. Требуется ручная проверка.",text_snapshot=message.body,
        ))
    return created[0] if created else None

def queue_attachment_scan(attachment):
    if not moderation_enabled() or not getattr(settings,"CONTENT_MODERATION_MEDIA_ENABLED",True):
        return None
    content_type=(attachment.content_type or "").lower()
    name=(attachment.original_name or "").lower()
    if not (
        content_type.startswith("image/") or content_type.startswith("video/") or
        Path(name).suffix.lower() in {".jpg",".jpeg",".png",".webp",".bmp",".gif",".mp4",".mov",".mkv",".avi",".webm"}
    ):
        return None
    job,_=ModerationScanJob.objects.get_or_create(attachment=attachment)
    if job.status==ModerationScanJob.Status.ERROR and job.attempts<3:
        job.status=ModerationScanJob.Status.QUEUED
        job.last_error=""
        job.save(update_fields=["status","last_error","updated_at"])
    return job


def queue_avatar_scan(user):
    if not moderation_enabled() or not getattr(settings,"CONTENT_MODERATION_MEDIA_ENABLED",True):
        return None
    if not user or not user.avatar:
        return None
    job,_=ModerationScanJob.objects.get_or_create(
        avatar_user=user,
        defaults={"source":ModerationScanJob.Source.AVATAR},
    )
    job.source=ModerationScanJob.Source.AVATAR
    job.attachment=None
    job.status=ModerationScanJob.Status.QUEUED
    job.attempts=0
    job.last_error=""
    job.finished_at=None
    job.started_at=None
    job.save(update_fields=["source","attachment","status","attempts","last_error","finished_at","started_at","updated_at"])
    return job

def _get_detector():
    global _detector
    if _detector is None:
        from nudenet import NudeDetector
        _detector=NudeDetector()
    return _detector

def _normalize_detection(item):
    raw=str(item.get("class","")).upper().replace(" ","_").replace("-","_")
    score=float(item.get("score",0.0) or 0.0)
    box=item.get("box")
    return {"class":raw,"score":score,"box":box}

def _flagged_detections(detections):
    threshold=float(getattr(settings,"CONTENT_MODERATION_THRESHOLD",0.30))
    covered_threshold=float(getattr(settings,"CONTENT_MODERATION_COVERED_THRESHOLD",0.50))
    normalized=[_normalize_detection(x) for x in detections or []]
    return [
        x for x in normalized
        if (x["class"] in EXPLICIT_NUDENET_LABELS and x["score"]>=threshold)
        or (x["class"] in SENSITIVE_COVERED_NUDENET_LABELS and x["score"]>=covered_threshold)
    ]

def _copy_evidence(case,attachment):
    if not attachment or not attachment.file:
        return
    try:
        attachment.file.open("rb")
        name=Path(attachment.original_name or attachment.file.name).name
        case.evidence_file.save(name,File(attachment.file),save=False)
        attachment.file.close()
        case.evidence_sha256=attachment.sha256 or ""
    except Exception:
        log.exception("Unable to copy moderation evidence for attachment %s",attachment.pk)


def _sha256_field(field):
    h=hashlib.sha256()
    field.open("rb")
    try:
        for chunk in iter(lambda:field.read(1024*1024),b""):
            h.update(chunk)
    finally:
        field.close()
    return h.hexdigest()

def _copy_avatar_evidence(case,user,sha256):
    try:
        user.avatar.open("rb")
        name=Path(user.avatar.name).name
        case.evidence_file.save(name,File(user.avatar),save=False)
        user.avatar.close()
        case.evidence_sha256=sha256
    except Exception:
        log.exception("Unable to copy moderation avatar evidence for user %s",user.pk)

def _save_preview(case,image_source):
    try:
        if isinstance(image_source,(bytes,bytearray)):
            src=BytesIO(image_source)
        else:
            src=image_source
        img=Image.open(src)
        img=ImageOps.exif_transpose(img)
        img.thumbnail((960,960))
        if img.mode not in {"RGB","L"}:
            img=img.convert("RGB")
        elif img.mode=="L":
            img=img.convert("RGB")
        out=BytesIO()
        img.save(out,format="JPEG",quality=84,optimize=True)
        out.seek(0)
        case.evidence_preview.save(f"{case.pk}.jpg",ContentFile(out.read()),save=False)
    except Exception:
        log.exception("Unable to build moderation preview")

def _create_media_case(attachment,kind,detections,preview_source=None):
    flagged=_flagged_detections(detections)
    if not flagged:
        return None
    existing=ModerationCase.objects.filter(attachment=attachment,detector="nudenet-3").first()
    if existing:
        return existing
    max_score=max(x["score"] for x in flagged)
    labels=sorted(flagged,key=lambda x:x["score"],reverse=True)
    msg=attachment.message
    case=ModerationCase(
        kind=kind,
        sender=msg.sender,
        conversation=msg.conversation,
        message=msg,
        attachment=attachment,
        detector="nudenet-3",
        policy_category="sexual",risk_points=10,
        score=max_score,
        labels=labels,
        reason="Локальная модель обнаружила признаки обнажённого 18+ контента. Нужна ручная проверка перед санкциями.",
        text_snapshot=msg.body or "",
    )
    case.save()
    _copy_evidence(case,attachment)
    if preview_source is not None:
        _save_preview(case,preview_source)
    elif kind==ModerationCase.Kind.IMAGE:
        try:
            attachment.file.open("rb")
            _save_preview(case,attachment.file)
            attachment.file.close()
        except Exception:
            log.exception("Unable to create image preview")
    case.save(update_fields=["evidence_file","evidence_preview","evidence_sha256"])
    return case

def _field_to_temp_path(field,suffix=""):
    """Materialize a Django FileField locally for libraries that require a filesystem path."""
    import os,tempfile
    suffix=(suffix or Path(getattr(field,"name","")).suffix or ".bin")[:16]
    tmp=tempfile.NamedTemporaryFile(delete=False,suffix=suffix)
    try:
        field.open("rb")
        try:
            while True:
                chunk=field.read(1024*1024)
                if not chunk:break
                tmp.write(chunk)
        finally:
            field.close()
        tmp.close()
        return tmp.name
    except Exception:
        try:tmp.close()
        except Exception:pass
        try:os.unlink(tmp.name)
        except Exception:pass
        raise

def _detect_image_bytes(detector,data,suffix=".jpg"):
    """Run NudeNet on encoded image bytes using a temporary file.

    NudeNet 3.x expects a filesystem path; this keeps S3/MinIO and video-frame
    moderation reliable instead of passing raw bytes to detector.detect().
    """
    import os,tempfile
    tmp=tempfile.NamedTemporaryFile(delete=False,suffix=suffix)
    try:
        tmp.write(data);tmp.flush();tmp.close()
        return detector.detect(tmp.name)
    finally:
        try:tmp.close()
        except Exception:pass
        try:os.unlink(tmp.name)
        except OSError:pass

def scan_image_attachment(attachment):
    detector=_get_detector();data=None;temp_path=None
    suffix=Path(attachment.original_name or attachment.file.name).suffix or ".jpg"
    try:
        try:
            path=attachment.file.path
        except (NotImplementedError,AttributeError):
            path=temp_path=_field_to_temp_path(attachment.file,suffix)
        detections=detector.detect(path)
        try:data=Path(path).read_bytes()
        except Exception:data=None
        case=_create_media_case(attachment,ModerationCase.Kind.IMAGE,detections)
        if data:
            ocr=_ocr_image(data)
            if ocr:_create_ocr_cases(attachment.message.sender,attachment.message.conversation,attachment.message,attachment,ocr)
        return case
    finally:
        if temp_path:
            try:
                import os;os.unlink(temp_path)
            except OSError:pass

def scan_video_attachment(attachment):
    try:
        import cv2
    except Exception as exc:
        raise RuntimeError("OpenCV is unavailable for video frame scanning") from exc

    temp_path=None
    try:
        path=attachment.file.path
    except (NotImplementedError,AttributeError):
        import tempfile,os
        suffix=Path(attachment.original_name or attachment.file.name).suffix[:12]
        tmp=tempfile.NamedTemporaryFile(delete=False,suffix=suffix)
        attachment.file.open("rb")
        try:
            for chunk in iter(lambda:attachment.file.read(1024*1024),b""):tmp.write(chunk)
        finally:
            attachment.file.close();tmp.close()
        path=temp_path=tmp.name
    cap=cv2.VideoCapture(path)
    if not cap.isOpened():
        if temp_path:
            try:os.unlink(temp_path)
            except OSError:pass
        raise RuntimeError("Unable to open video")

    total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    requested=max(3,min(int(getattr(settings,"CONTENT_MODERATION_VIDEO_FRAMES",10)),30))
    if total>0:
        frame_indexes=sorted({int(i*(total-1)/(requested-1)) for i in range(requested)})
    else:
        frame_indexes=list(range(requested))

    detector=_get_detector()
    all_flagged=[]
    best_preview=None
    best_score=0.0
    video_ocr=[]
    max_ocr_frames=max(0,min(int(getattr(settings,"CONTENT_MODERATION_VIDEO_OCR_FRAMES",4)),8))

    try:
        for frame_no,idx in enumerate(frame_indexes):
            if total>0:
                cap.set(cv2.CAP_PROP_POS_FRAMES,idx)
            ok,frame=cap.read()
            if not ok:
                if total<=0:break
                continue
            ok,jpg=cv2.imencode(".jpg",frame,[int(cv2.IMWRITE_JPEG_QUALITY),88])
            if not ok:continue
            data=jpg.tobytes()
            if frame_no<max_ocr_frames:
                ocr=_ocr_image(data)
                if ocr:video_ocr.append(ocr)
            detections=_detect_image_bytes(detector,data,".jpg")
            flagged=_flagged_detections(detections)
            if flagged:
                all_flagged.extend(flagged)
                score=max(x["score"] for x in flagged)
                if score>best_score:
                    best_score=score
                    best_preview=data
    finally:
        cap.release()
        if temp_path:
            try:
                import os;os.unlink(temp_path)
            except OSError:pass

    if video_ocr:
        _create_ocr_cases(
            attachment.message.sender,attachment.message.conversation,
            attachment.message,attachment,"\n".join(video_ocr)[:12000],
            kind=ModerationCase.Kind.VIDEO,
        )
    if not all_flagged:
        return None
    return _create_media_case(attachment,ModerationCase.Kind.VIDEO,all_flagged,best_preview)


def scan_avatar_user(user):
    if not user.avatar:
        return None
    sha256=_sha256_field(user.avatar)
    existing=ModerationCase.objects.filter(
        sender=user,attachment__isnull=True,detector="nudenet-avatar",evidence_sha256=sha256
    ).first()
    if existing:
        return existing
    detector=_get_detector();temp_path=None
    try:
        try:path=user.avatar.path
        except (NotImplementedError,AttributeError):path=temp_path=_field_to_temp_path(user.avatar,Path(user.avatar.name).suffix or ".webp")
        detections=detector.detect(path)
    finally:
        if temp_path:
            try:
                import os;os.unlink(temp_path)
            except OSError:pass
    flagged=_flagged_detections(detections)
    if not flagged:
        return None
    labels=sorted(flagged,key=lambda x:x["score"],reverse=True)
    case=ModerationCase.objects.create(
        kind=ModerationCase.Kind.IMAGE,
        sender=user,
        detector="nudenet-avatar",policy_category="sexual",risk_points=10,
        score=max(x["score"] for x in flagged),
        labels=labels,
        reason="Локальная модель обнаружила признаки 18+ контента в фото профиля. Требуется ручная проверка.",
        evidence_sha256=sha256,
    )
    _copy_avatar_evidence(case,user,sha256)
    try:
        user.avatar.open("rb");_save_preview(case,user.avatar);user.avatar.close()
    except Exception:
        log.exception("Unable to create avatar moderation preview")
    case.save(update_fields=["evidence_file","evidence_preview","evidence_sha256"])
    return case

def process_job(job):
    if job.source==ModerationScanJob.Source.AVATAR or job.avatar_user_id:
        return scan_avatar_user(job.avatar_user)
    attachment=job.attachment
    if not attachment:
        return None
    content_type=(attachment.content_type or "").lower()
    suffix=Path(attachment.original_name or "").suffix.lower()
    if content_type.startswith("image/") or suffix in {".jpg",".jpeg",".png",".webp",".bmp",".gif"}:
        return scan_image_attachment(attachment)
    if content_type.startswith("video/") or suffix in {".mp4",".mov",".mkv",".avi",".webm"}:
        return scan_video_attachment(attachment)
    return None

def recover_stale_jobs(stale_seconds=180):
    from datetime import timedelta
    from apps.chat.models import Attachment
    cutoff=timezone.now()-timedelta(seconds=max(60,int(stale_seconds)))
    reset=0;created=0
    for job in ModerationScanJob.objects.filter(status=ModerationScanJob.Status.PROCESSING,updated_at__lt=cutoff):
        job.status=ModerationScanJob.Status.QUEUED;job.started_at=None;job.finished_at=None;job.last_error="stale moderation job automatically requeued"
        job.save(update_fields=["status","started_at","finished_at","last_error","updated_at"]);reset+=1
    if moderation_enabled() and getattr(settings,"CONTENT_MODERATION_MEDIA_ENABLED",True):
        media_ext=(".jpg",".jpeg",".png",".webp",".bmp",".gif",".mp4",".mov",".mkv",".avi",".webm")
        for a in Attachment.objects.iterator(chunk_size=200):
            ct=(a.content_type or "").lower();name=(a.original_name or "").lower()
            if not (ct.startswith("image/") or ct.startswith("video/") or name.endswith(media_ext)):continue
            job=ModerationScanJob.objects.filter(attachment=a).first()
            if not job:
                if queue_attachment_scan(a):created+=1
            elif job.status==ModerationScanJob.Status.ERROR and job.updated_at<cutoff:
                job.status=ModerationScanJob.Status.QUEUED;job.attempts=0;job.last_error="";job.started_at=None;job.finished_at=None
                job.save(update_fields=["status","attempts","last_error","started_at","finished_at","updated_at"]);reset+=1
    return reset,created

def claim_next_job():
    with transaction.atomic():
        job=(ModerationScanJob.objects.select_for_update(skip_locked=True)
             .select_related("attachment__message__sender","attachment__message__conversation","avatar_user")
             .filter(status=ModerationScanJob.Status.QUEUED)
             .order_by("queued_at")
             .first())
        if not job:
            return None
        job.status=ModerationScanJob.Status.PROCESSING
        job.started_at=timezone.now()
        job.attempts+=1
        job.save(update_fields=["status","started_at","attempts","updated_at"])
        return job

def run_one_job():
    job=claim_next_job()
    if not job:
        return False
    try:
        process_job(job)
        job.status=ModerationScanJob.Status.DONE
        job.finished_at=timezone.now()
        job.last_error=""
        job.save(update_fields=["status","finished_at","last_error","updated_at"])
    except Exception as exc:
        log.exception("Moderation scan failed for job %s",job.pk)
        job.last_error=str(exc)[:4000]
        job.finished_at=timezone.now()
        # Model warm-up / MinIO reads can fail transiently after a restart.
        # Retry long enough for a presentation/server boot instead of silently losing 18+ jobs.
        job.status=ModerationScanJob.Status.QUEUED if job.attempts<6 else ModerationScanJob.Status.ERROR
        job.save(update_fields=["status","finished_at","last_error","updated_at"])
    return True
