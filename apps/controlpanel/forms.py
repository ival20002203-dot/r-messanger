import ipaddress
from django import forms
from apps.accounts.models import CorporateDomain,IPAccessRule,User

class UserAdminForm(forms.ModelForm):
    class Meta:
        model=User
        fields=["display_name","role","custom_role","is_active","is_suspended","suspend_reason","can_login","can_send_messages","can_create_groups","can_upload_files","can_start_direct_chats","can_make_calls"]

class DomainForm(forms.ModelForm):
    class Meta:
        model=CorporateDomain
        fields=["domain","active","registration_enabled"]

class IPRuleForm(forms.ModelForm):
    class Meta:
        model=IPAccessRule
        fields=["network","action","note","active"]
    def clean_network(self):
        raw=self.cleaned_data["network"].strip()
        try:return str(ipaddress.ip_network(raw,strict=False))
        except ValueError:
            try:return str(ipaddress.ip_network(raw+"/32",strict=False))
            except ValueError:raise forms.ValidationError("Укажите IP или CIDR, например 10.10.0.0/16.")
