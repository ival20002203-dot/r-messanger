# Artel Link 13.5.0

## Telegram-style chat delivery
- Text messages still appear optimistically before server acknowledgement.
- Photos, videos, voice notes and files now appear in the chat immediately when selected.
- Image/video/audio sender previews use a local object URL while the upload is in progress.
- Each attachment shows true XMLHttpRequest upload progress.
- Upload failure stays in the chat with a retry action instead of silently disappearing.
- Retries reuse `client_message_id`; the server is idempotent and does not duplicate an already accepted attachment.
- Multiple selected/dropped files start without serial waiting.

## Attachments
- Filenames are no longer duplicated as message text; a filename belongs to the attachment card.
- Pending antivirus state is a compact Telegram-like attachment status instead of the large “Подготавливаем файл” block.
- Receiver sees a pending photo/file card immediately after the server accepts the upload.
- Safe scan update replaces the pending card through realtime `message_updated`.

## Time
- Message payloads and sidebar payloads contain server-local `Asia/Tashkent` time.
- UI prefers server-provided `HH:MM`, avoiding incorrect Windows/browser timezone rendering.

## Composer
- Paperclip opens an attachment menu with “Фото или видео” and “Файл”.
- Paste and drag/drop support multiple files.
