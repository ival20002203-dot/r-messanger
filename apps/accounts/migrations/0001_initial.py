import apps.accounts.managers
import django.contrib.auth.validators
import django.utils.timezone
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[("auth","0012_alter_user_first_name_max_length")]
    operations=[
        migrations.CreateModel(
            name="User",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("password",models.CharField(max_length=128,verbose_name="password")),
                ("last_login",models.DateTimeField(blank=True,null=True,verbose_name="last login")),
                ("is_superuser",models.BooleanField(default=False,help_text="Designates that this user has all permissions without explicitly assigning them.",verbose_name="superuser status")),
                ("username",models.CharField(error_messages={"unique":"A user with that username already exists."},help_text="Required. 150 characters or fewer.",max_length=150,unique=True,validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],verbose_name="username")),
                ("first_name",models.CharField(blank=True,max_length=150,verbose_name="first name")),
                ("last_name",models.CharField(blank=True,max_length=150,verbose_name="last name")),
                ("email",models.EmailField(max_length=254,unique=True)),
                ("is_staff",models.BooleanField(default=False,help_text="Designates whether the user can log into this admin site.",verbose_name="staff status")),
                ("is_active",models.BooleanField(default=True,help_text="Designates whether this user should be treated as active.",verbose_name="active")),
                ("date_joined",models.DateTimeField(default=django.utils.timezone.now,verbose_name="date joined")),
                ("display_name",models.CharField(blank=True,max_length=150)),
                ("role",models.CharField(choices=[("superadmin","Суперадминистратор"),("infra_admin","Администратор инфраструктуры"),("moderator","Модератор"),("auditor","Аудитор"),("user","Пользователь")],default="user",max_length=20)),
                ("is_suspended",models.BooleanField(default=False)),("suspend_reason",models.CharField(blank=True,max_length=255)),
                ("can_login",models.BooleanField(default=True)),("can_send_messages",models.BooleanField(default=True)),
                ("can_create_groups",models.BooleanField(default=True)),("can_upload_files",models.BooleanField(default=True)),
                ("can_start_direct_chats",models.BooleanField(default=True)),("last_seen_at",models.DateTimeField(blank=True,null=True)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("groups",models.ManyToManyField(blank=True,help_text="The groups this user belongs to.",related_name="user_set",related_query_name="user",to="auth.group",verbose_name="groups")),
                ("user_permissions",models.ManyToManyField(blank=True,help_text="Specific permissions for this user.",related_name="user_set",related_query_name="user",to="auth.permission",verbose_name="user permissions")),
            ],
            options={"abstract":False},managers=[("objects",apps.accounts.managers.UserManager())],
        ),
        migrations.CreateModel(name="CorporateDomain",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("domain",models.CharField(max_length=190,unique=True)),("active",models.BooleanField(default=True)),
            ("registration_enabled",models.BooleanField(default=True)),("created_at",models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.CreateModel(name="EmailVerification",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("email",models.EmailField(db_index=True,max_length=254)),("code_hash",models.CharField(max_length=64)),
            ("expires_at",models.DateTimeField()),("attempts",models.PositiveSmallIntegerField(default=0)),
            ("used_at",models.DateTimeField(blank=True,null=True)),("created_at",models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.CreateModel(name="ApiToken",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("name",models.CharField(default="mobile",max_length=100)),("token_hash",models.CharField(max_length=64,unique=True)),
            ("prefix",models.CharField(db_index=True,max_length=12)),("created_at",models.DateTimeField(auto_now_add=True)),
            ("last_used_at",models.DateTimeField(blank=True,null=True)),("revoked_at",models.DateTimeField(blank=True,null=True)),
            ("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="api_tokens",to="accounts.user")),
        ]),
        migrations.CreateModel(name="LoginEvent",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("email",models.EmailField(blank=True,max_length=254)),("ip_address",models.GenericIPAddressField(blank=True,null=True)),
            ("user_agent",models.TextField(blank=True)),("successful",models.BooleanField(default=False)),
            ("reason",models.CharField(blank=True,max_length=255)),("created_at",models.DateTimeField(auto_now_add=True)),
            ("user",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to="accounts.user")),
        ],options={"ordering":["-created_at"]}),
        migrations.CreateModel(name="IPAccessRule",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("address",models.GenericIPAddressField(unique=True)),
            ("action",models.CharField(choices=[("allow","Разрешить"),("deny","Запретить")],default="deny",max_length=10)),
            ("note",models.CharField(blank=True,max_length=255)),("active",models.BooleanField(default=True)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to="accounts.user")),
        ]),
        migrations.CreateModel(name="AppSetting",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("key",models.CharField(max_length=120,unique=True)),("value",models.TextField(blank=True)),
            ("description",models.CharField(blank=True,max_length=255)),("updated_at",models.DateTimeField(auto_now=True)),
            ("updated_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to="accounts.user")),
        ]),
        migrations.AddIndex(model_name="loginevent",index=models.Index(fields=["created_at"],name="accounts_lo_created_b2babb_idx")),
        migrations.AddIndex(model_name="loginevent",index=models.Index(fields=["email","created_at"],name="accounts_lo_email_21ddac_idx")),
    ]
