from django.conf import settings
from django.db import models
class AuditEvent(models.Model):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    action=models.CharField(max_length=120,db_index=True)
    object_type=models.CharField(max_length=120,blank=True,db_index=True)
    object_id=models.CharField(max_length=120,blank=True,db_index=True)
    ip_address=models.GenericIPAddressField(null=True,blank=True)
    user_agent=models.TextField(blank=True)
    metadata=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:
        ordering=["-created_at"]
        indexes=[models.Index(fields=["action","created_at"]),models.Index(fields=["object_type","object_id","created_at"])]
