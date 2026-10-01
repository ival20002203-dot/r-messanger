from django import forms
from apps.accounts.models import User

class DirectChatForm(forms.Form):
    email=forms.CharField(label="Email или @username",max_length=254)
    def clean_email(self):
        value=self.cleaned_data["email"].lower().strip()
        if value.startswith("@"):
            user=User.objects.filter(handle=value.lstrip("@"),is_active=True,is_suspended=False).first()
        else:
            user=User.objects.filter(email=value,is_active=True,is_suspended=False).first()
        if not user:
            raise forms.ValidationError("Пользователь не найден.")
        return user.email

class GroupForm(forms.Form):
    title=forms.CharField(label="Название",max_length=180)
    kind=forms.ChoiceField(label="Тип",choices=[("group","Группа"),("channel","Канал")])
    description=forms.CharField(label="Описание",required=False,widget=forms.Textarea(attrs={"rows":3}))
    members=forms.CharField(label="Участники",required=False,help_text="Email через запятую",widget=forms.Textarea(attrs={"rows":3}))
