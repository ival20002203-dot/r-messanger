# R-Mes 15 — бесплатный public test для 2 человек

## Лучший вариант: Oracle Cloud Always Free VM

Для полного R-Mes нужен обычный VM, потому что кроме Django используются PostgreSQL, Redis, MinIO, 18+ worker, ClamAV и TURN/UDP. Oracle Always Free подходит лучше бесплатных web-PaaS, если в выбранном регионе есть свободная A1 capacity.

Рекомендуемый тестовый VM: Ubuntu 24.04, Ampere A1, 2 OCPU / 12 GB RAM (в пределах Always Free квоты, если доступно).

Откройте inbound:

- TCP 22
- TCP 80
- TCP/UDP 443
- TCP/UDP 3478
- UDP 49160-49200

После копирования проекта на VM запускайте `scripts/prepare_public_vps.sh`.

Если своего домена пока нет, можно временно использовать hostname вида `PUBLIC.IP.ADDRESS.nip.io`; он резолвится на IP и позволяет выпустить нормальный TLS certificate.

## Почему не Render Free для полного релиза

Render Free удобен для демо Django/WebSocket, но free web service имеет 512 MB, засыпает при простое, локальные файлы ephemeral, а free Postgres ограничен/временный. Для NudeNet + ClamAV + TURN это неудобно.

## Нулевой запасной вариант без VPS

Cloudflare Tunnel может бесплатно открыть текущий компьютер наружу без public IP. Это удобно на пару дней для чатов, но компьютер должен быть включён, а полноценный TURN/UDP всё равно лучше держать на VM.
