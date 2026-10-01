from django.contrib.auth.base_user import BaseUserManager
class UserManager(BaseUserManager):
    use_in_migrations = True
    def _create_user(self,email,password,**extra):
        if not email: raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email,username=email,**extra)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_user(self,email,password=None,**extra):
        extra.setdefault("is_staff",False); extra.setdefault("is_superuser",False)
        return self._create_user(email,password,**extra)
    def create_superuser(self,email,password=None,**extra):
        extra.setdefault("is_staff",True); extra.setdefault("is_superuser",True); extra.setdefault("role","superadmin")
        return self._create_user(email,password,**extra)
