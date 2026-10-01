CAPABILITIES={
    "control.view":"Открывать Control Center",
    "control.write":"Изменять системные настройки",
    "users.view":"Просматривать пользователей",
    "users.manage":"Изменять пользователей и ограничения",
    "security.view":"Просматривать Security Center",
    "security.manage":"Обрабатывать DLP/antivirus/device trust",
    "audit.view":"Просматривать аудит",
    "audit.export":"Экспортировать аудит",
    "chat.audit":"Просматривать метаданные чатов",
    "policies.manage":"Управлять доменами/IP/@username",
    "rbac.manage":"Управлять кастомными ролями",
    "backup.view":"Просматривать backup/restore проверки",
    "client_versions.manage":"Управлять версиями клиентов",
}

BUILTIN_ROLE_CAPABILITIES={
    "developer":set(CAPABILITIES),
    "superadmin":set(CAPABILITIES)-{"rbac.manage"},
    "infra_admin":{"control.view","control.write","users.view","users.manage","security.view","security.manage","audit.view","audit.export","chat.audit","policies.manage","backup.view","client_versions.manage"},
    "moderator":{"control.view","users.view","security.view","security.manage","audit.view","chat.audit"},
    "auditor":{"control.view","users.view","security.view","audit.view","audit.export","chat.audit","backup.view"},
    "user":set(),
}

def capabilities_for(user):
    if not user or not getattr(user,"is_authenticated",False):return set()
    if getattr(user,"role",None)=="developer":return set(CAPABILITIES)
    custom=getattr(user,"custom_role",None)
    if custom:
        if not custom.active:return set()
        return {x for x in (custom.permissions or []) if x in CAPABILITIES and x!="rbac.manage"}
    return set(BUILTIN_ROLE_CAPABILITIES.get(getattr(user,"role","user"),set()))
