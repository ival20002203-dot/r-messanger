# Обновление Artel Link до 13.8.0 на Ubuntu

Загрузите полный архив в `/home/arteladmin/upload/ArtelLink_v13_8_full_project.zip`.

## Установка

```bash
sudo mkdir -p /home/arteladmin/upload/v13_8
```

```bash
sudo cp /opt/artel-link/.env /home/arteladmin/artel-link.env.before-v13-8
```

```bash
sudo tar --exclude='artel-link/media' --exclude='artel-link/private_media' --exclude='artel-link/logs' --exclude='artel-link/backups' --exclude='artel-link/client_updates' -C /opt -czf /home/arteladmin/artel-link-code-before-v13-8.tar.gz artel-link
```

```bash
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_8_full_project.zip -d /home/arteladmin/upload/v13_8
```

```bash
sudo rsync -a --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_8/localgram/ /opt/artel-link/
```

```bash
sudo cp /home/arteladmin/artel-link.env.before-v13-8 /opt/artel-link/.env
```

```bash
sudo chown -R arteladmin:arteladmin /opt/artel-link && sudo chmod 600 /opt/artel-link/.env
```

```bash
cd /opt/artel-link && chmod +x scripts/*.sh && ./scripts/release_13_8.sh
```

В конце должно быть `READY: Artel Link 13.8.0`.

## Проверка звонков и модерации

```bash
cd /opt/artel-link && docker compose ps -a && docker compose logs --tail=100 moderator turn && curl -fsS http://127.0.0.1:8000/healthz/
```

Если включён UFW:

```bash
cd /opt/artel-link && sudo bash scripts/enable_call_ports.sh
```

На внешнем firewall/NAT должны быть разрешены TCP/UDP `3478` и UDP `49160-49200` к серверу Artel Link.

## Внутреннее Desktop-обновление

Соберите Windows-клиент через `desktop\\build_windows.cmd`, затем загрузите `ArtelLink-13.8.0-Setup.exe`, `latest.yml` и `.blockmap` в `/home/arteladmin/upload/client_updates/windows/` и выполните:

```bash
cd /opt/artel-link && ./scripts/publish_client_update.sh windows /home/arteladmin/upload/client_updates/windows/ArtelLink-13.8.0-Setup.exe
```

Клиенты версии 13.7.0 и выше загрузят 13.8.0 внутри приложения. Пользователь нажимает «Обновить», затем «Перезапустить сейчас»; отдельная ручная переустановка не нужна.
