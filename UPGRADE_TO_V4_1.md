# Localgram v4.0 → v4.1

v4.1 adds one new Accounts migration:

```text
accounts 0004_reserved_username
```

It does not delete or rewrite users, messages, files or chats.

## 1. Stop web

```powershell
cd "N:\VS CODE\localgram"
docker compose stop web
```

Do not run:

```powershell
docker compose down -v
```

## 2. Preserve

Keep your existing:

```text
.env
media\
backups\
```

and PostgreSQL Docker volume.

## 3. Replace project source with v4.1

Extract the new archive over:

```text
N:\VS CODE\localgram
```

Keep the existing `.env`.

## 4. Rebuild

```powershell
docker compose up -d --build
```

## 5. Verify

```powershell
docker compose ps -a
docker compose exec web python manage.py showmigrations accounts
```

Expected Accounts migrations:

```text
[X] 0001_initial
[X] 0002_localgram_v2
[X] 0003_localgram_v3
[X] 0004_reserved_username
```

Chat still includes:

```text
[X] 0004_localgram_v4
```

## 6. Open username protection

```text
http://127.0.0.1:8000/control/usernames/
```

You will see the built-in 2,334-name catalog.

Recommended first pass:
- System names
- Official / brand
- Roles / departments
- Security
- Services / infrastructure
- Service channels

Then inspect `Popular nicknames` and `Short / status` before reserving them, because these categories intentionally block many human-friendly handles.

## 7. Existing occupied names

If `@admin`, `@boss`, etc. already belongs to somebody, v4.1 **does not take it away**.

The page shows:

```text
OCCUPIED
```

and the current owner.

You may still click `Protect`; after that the current user keeps it, but once they change their username the protected name cannot be assigned to a different account.

## 8. Custom list

Paste usernames into the admin import box separated by:
- spaces;
- commas;
- semicolons;
- new lines.

Up to 10,000 tokens can be processed in one request.

## 9. Full built-in catalog

The project also contains:

```text
RESERVED_USERNAME_CATALOG.txt
```

and Control Center has a download button for the same list.
