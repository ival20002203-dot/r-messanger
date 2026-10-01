# Artel Link 13.6.0 — Presentation Stable

- Attachments are visible immediately after upload; antivirus and DLP run asynchronously and never leave the UI stuck on “проверяем”.
- Malware is still blocked as soon as ClamAV marks an attachment infected.
- MinIO/S3 antivirus scan materializes files locally before clamd streaming for reliability.
- Security worker automatically recovers stale/failed/missing scan jobs.
- 18+ moderation worker automatically recovers stale/error jobs and missing media jobs.
- Photo/video/file previews work while background scanning continues.
- Added one-command presentation deployment: `bash scripts/presentation_release_13_6.sh`.
