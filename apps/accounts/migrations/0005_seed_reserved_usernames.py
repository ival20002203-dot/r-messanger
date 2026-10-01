from django.db import migrations

def seed_reserved_usernames(apps,schema_editor):
    ReservedUsername=apps.get_model("accounts","ReservedUsername")
    try:
        from apps.accounts.reserved_catalog import BUILTIN_CATALOG
    except Exception:
        return
    batch=[]
    existing=set(ReservedUsername.objects.values_list("username",flat=True))
    for username,category in BUILTIN_CATALOG:
        if username in existing:
            ReservedUsername.objects.filter(username=username).update(
                active=True,category=category,source="builtin",
                note="Встроенный каталог Localgram v5",
            )
        else:
            batch.append(ReservedUsername(
                username=username,category=category,source="builtin",
                active=True,note="Встроенный каталог Localgram v5",
            ))
    if batch:
        ReservedUsername.objects.bulk_create(batch,batch_size=500)

def reverse_seed(apps,schema_editor):
    # Intentionally non-destructive: a migration rollback must not silently
    # remove identity policy records that administrators may already rely on.
    pass

class Migration(migrations.Migration):
    dependencies=[("accounts","0004_reserved_username")]
    operations=[migrations.RunPython(seed_reserved_usernames,reverse_seed)]
