# Localgram v6 Native / Mobile API

Base URL:

```text
https://localgram.company.local/api/v1/
```

WebSocket:

```text
wss://localgram.company.local/ws/chat/<conversation_uuid>/?access_token=<ACCESS_TOKEN>
```

## Authentication

### Password login

```http
POST /api/v1/auth/token/
Content-Type: application/json
```

```json
{
  "email": "user@texnopark.uz",
  "password": "...",
  "device_id": "ios-7E97...",
  "device_name": "Rauf iPhone",
  "platform": "ios",
  "push_token": ""
}
```

If login email 2FA is disabled, response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 1800,
  "device_id": 12,
  "user": {}
}
```

If email 2FA is enabled:

```json
{
  "two_factor_required": true,
  "challenge_id": 123,
  "email": "user@texnopark.uz"
}
```

Then:

```http
POST /api/v1/auth/token/verify/
```

with the challenge ID and email OTP.

### Refresh

```http
POST /api/v1/auth/refresh/
Content-Type: application/json
```

```json
{"refresh_token":"..."}
```

Access token lifetime is controlled by:

```env
ACCESS_TOKEN_MINUTES=30
REFRESH_TOKEN_DAYS=30
```

Refresh rotates credentials.

### Authorization

All authenticated requests:

```http
Authorization: Bearer <access_token>
```

## Offline-safe message sending

Native clients should create a UUID/ULID locally and send it as `client_id`.

```http
POST /api/v1/conversations/<uuid>/messages/
```

```json
{
  "body": "Hello",
  "client_id": "01J5K4P8GFA8V..."
}
```

`sender + client_message_id` is unique in PostgreSQL. Retrying the same queued message after reconnect returns the existing message instead of creating a duplicate.

Recommended native workflow:

```text
local SQLite/Realm queue
        ↓
generate client_id
        ↓
POST message
        ↓
network fails → retain queue item
        ↓
reconnect
        ↓
retry same client_id
        ↓
server idempotency
```

## Devices

```http
GET /api/v1/devices/
PATCH /api/v1/devices/<id>/
DELETE /api/v1/devices/<id>/
```

Update push token:

```json
{"push_token":"native-provider-token","device_name":"Work iPhone"}
```

Developer device sessions are protected from non-developer administrative session views.

## Users

```http
GET /api/v1/users/?q=@rauf
POST /api/v1/direct/
```

Direct chat can be opened with user ID, email, or `@username`.

## Conversations

```http
GET /api/v1/conversations/
GET /api/v1/saved/
```

## Messages

```http
GET  /api/v1/conversations/<uuid>/messages/?before=<message_id>
POST /api/v1/conversations/<uuid>/messages/
POST /api/v1/messages/<id>/react/
POST /api/v1/messages/<id>/delete/
POST /api/v1/conversations/<uuid>/delete/
GET  /api/v1/messages/<id>/receipts/
```

Receipts provide `delivered_at` and `read_at`. Non-developer viewers never receive developer receipt/session identity from admin/session interfaces.

## Uploads

```http
POST /api/v1/conversations/<uuid>/upload/
Authorization: Bearer ...
Content-Type: multipart/form-data
```

Fields:

```text
file
body
client_id
voice=1
```

Response initially may contain:

```json
{"scan_status":"pending"}
```

The file does not receive a normal download URL until ClamAV marks it `safe`.

Pipeline:

```text
upload
  → MinIO
  → pending
  → Security worker
  → ClamAV
  → DLP inspection
  → safe / infected / error
  → WebSocket message_updated
```

## Notifications

```http
GET  /api/v1/notifications/
POST /api/v1/notifications/
```

POST marks all current notifications as read.

Kinds:
- mention
- reply
- reaction
- system
- sticker

## Folders

```http
GET  /api/v1/folders/
POST /api/v1/folders/
PATCH /api/v1/folders/<id>/
DELETE /api/v1/folders/<id>/
```

Smart types:
- all
- direct
- groups
- channels
- unread
- archived
- custom

## Stickers / custom emoji

```http
GET  /api/v1/stickers/
POST /api/v1/conversations/<uuid>/sticker/
```

```json
{"sticker_id":42,"client_id":"..."}
```

## WebSocket events

Existing web/native chat socket handles:
- message
- message_updated
- message_deleted
- reaction
- typing
- read
- presence
- call_offer
- call_answer
- call_ice
- call_end
- call_reject

Native authentication can be provided through:

```text
?access_token=<token>
```

## Security recommendations for native apps

- store refresh tokens in iOS Keychain / Android Keystore;
- keep access tokens only in protected app storage/memory;
- rotate refresh tokens through `/auth/refresh/`;
- revoke the DeviceSession on logout;
- never log raw access/refresh tokens;
- persist outgoing messages with `client_id`;
- treat attachment URL as temporary/presigned;
- do not bypass `scan_status`.
