# Artel Link 13.0.0 — release notes

## Telegram-like UX

- Замок постоянно находится в верхней панели над чатами.
- Текстовое сообщение появляется локально сразу после нажатия Send.
- `↻` вращается, пока сервер не подтвердит сохранение сообщения.
- После подтверждения — `✓`, после прочтения собеседником — `✓✓`.
- При серверной ошибке — красный `!`; по нажатию сообщение отправляется повторно с тем же idempotency key.
- Превью активного чата в левой колонке меняется сразу вместе с optimistic message.

## Presence

- Online marker имеет короткий TTL и heartbeat.
- Web/Desktop/Android публикуют active only when document/app is visible and focused.
- При уходе в background статус перестаёт считаться online.
- Смена presence транслируется в активные chat groups, а online-dot в списке чатов обновляется без перезагрузки.

## Avatars

- До 25 MB.
- JPG, PNG, WEBP, GIF, BMP, TIFF; HEIC/HEIF через `pillow-heif`.
- EXIF orientation исправляется.
- Первый кадр animated image используется как avatar.
- Изображение масштабируется максимум до 1600×1600 и сохраняется как WebP.
- Клиент получает avatar через authenticated `/auth/avatar/<user_id>/`, поэтому MinIO public URL больше не ломает отображение.

## Native updates

- `ClientVersionPolicy` поддерживает Windows/Android/iOS/macOS/Linux.
- `/ops/client-policy/` сообщает latest/minimum/version/update metadata.
- `/ops/client-update/download/` выдаёт опубликованный artifact.
- `client_updates/` bind-mounted в web container.
- Windows v13 скачивает EXE с сервера, проверяет SHA-256, запускает установщик и закрывает текущий процесс.
- Android загружает APK через DownloadManager и после завершения открывает системную установку обновления.
- ОС всё равно требует стандартное пользовательское подтверждение установки APK — это системное ограничение Android.

## Publish update

```bash
./scripts/publish_client_update.sh windows /path/ArtelLink-13.1.0-Setup.exe
./scripts/publish_client_update.sh android /path/ArtelLink-13.1.0.apk
```

No database or media volumes are deleted by this process.
