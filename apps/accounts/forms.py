import io
import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image,ImageOps,UnidentifiedImageError
from .models import ReservedUsername,User,UserPreference
from .utils import domain_allowed

class RegisterForm(forms.Form):
    email=forms.EmailField(label="Корпоративная почта")
    display_name=forms.CharField(label="Имя и фамилия",max_length=150)
    password1=forms.CharField(label="Пароль",widget=forms.PasswordInput)
    password2=forms.CharField(label="Повторите пароль",widget=forms.PasswordInput)
    accept_policy=forms.BooleanField(label="Я принимаю правила использования корпоративного мессенджера")

    def clean_email(self):
        email=self.cleaned_data["email"].lower().strip()
        if not domain_allowed(email):raise ValidationError("Регистрация разрешена только с корпоративного домена.")
        if User.objects.filter(email=email).exists():raise ValidationError("Аккаунт с этой почтой уже существует.")
        return email

    def clean(self):
        data=super().clean();p1,p2=data.get("password1"),data.get("password2")
        if p1 and p2 and p1!=p2:self.add_error("password2","Пароли не совпадают.")
        if p1:validate_password(p1)
        return data

class LoginForm(AuthenticationForm):
    username=forms.EmailField(label="Корпоративная почта")
    password=forms.CharField(label="Пароль",strip=False,widget=forms.PasswordInput)

class ProfileForm(forms.ModelForm):
    class Meta:
        model=User
        fields=["avatar","display_name","handle","bio","first_name","last_name"]
        widgets={
            "bio":forms.Textarea(attrs={"rows":3,"maxlength":220}),
            "avatar":forms.FileInput(attrs={"class":"avatar-file-input","accept":"image/*"}),
            "handle":forms.TextInput(attrs={"autocomplete":"off","spellcheck":"false","placeholder":"username"}),
        }
    def clean_handle(self):
        h=(self.cleaned_data.get("handle") or "").lower().strip().lstrip("@")
        if h and not re.fullmatch(r"[a-z0-9_]{4,32}",h):
            raise ValidationError("Username: 4–32 символа, только a-z, 0-9 и _.")
        current=(getattr(self.instance,"handle",None) or "").lower()
        assigned=ReservedUsername.objects.filter(assigned_to=self.instance,active=True).first() if getattr(self.instance,"pk",None) else None
        if assigned and h!=current:
            raise ValidationError("Этот username управляется владельцем системы и недоступен для изменения.")
        if h and h!=current and ReservedUsername.objects.filter(username=h,active=True).exists():
            raise ValidationError("Этот username уже занят.")
        return h or None
    def clean_avatar(self):
        f=self.cleaned_data.get("avatar")
        if not f:
            return f
        if hasattr(f,"size") and f.size>25*1024*1024:
            raise ValidationError("Фото профиля должно быть не больше 25 MB.")
        try:
            # HEIC/HEIF from iPhone is registered when pillow-heif is installed.
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except Exception:
                pass
            image=Image.open(f)
            image=ImageOps.exif_transpose(image)
            if getattr(image,"is_animated",False):
                image.seek(0)
            width,height=image.size
            if width<=0 or height<=0 or width*height>80_000_000:
                raise ValidationError("Слишком большое разрешение изображения.")
            # Normalize every accepted source format to WebP. This removes EXIF orientation
            # problems and makes avatars render consistently in Web/Desktop/Android.
            if image.mode not in {"RGB","RGBA"}:
                image=image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.thumbnail((1600,1600),Image.Resampling.LANCZOS)
            out=io.BytesIO()
            image.save(out,format="WEBP",quality=90,method=6)
            out.seek(0)
            return ContentFile(out.read(),name="avatar.webp")
        except ValidationError:
            raise
        except (UnidentifiedImageError,OSError,ValueError):
            raise ValidationError("Не удалось открыть изображение. Поддерживаются фото JPG, PNG, WEBP, GIF, BMP, TIFF и HEIC/HEIF.")

class PreferenceForm(forms.ModelForm):
    class Meta:
        model=UserPreference
        fields=[
            "theme","accent_color","chat_background","font_scale","animations_enabled",
            "desktop_notifications","notification_sound","show_message_preview","show_sender_name",
            "notify_direct_chats","notify_groups","notify_channels","suppress_active_chat_notifications",
            "enter_to_send","compact_mode","animated_emoji","auto_download_images","auto_download_files",
        ]
        widgets={
            "font_scale":forms.NumberInput(attrs={"type":"range","min":"85","max":"120","step":"5"}),
        }
    def clean_font_scale(self):
        value=int(self.cleaned_data.get("font_scale") or 100)
        return max(85,min(120,value))
