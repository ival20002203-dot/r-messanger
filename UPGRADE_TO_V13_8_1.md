# Обновление Artel Link до 13.8.1 на Ubuntu

Загрузите полный архив в `/home/arteladmin/upload/ArtelLink_v13_8_1_full_project.zip`.

## Установка

```bash
sudo timedatectl set-timezone Asia/Tashkent && sudo timedatectl set-ntp true && timedatectl status
```

```bash
sudo mkdir -p /home/arteladmin/upload/v13_8_1 && sudo cp /opt/artel-link/.env /home/arteladmin/artel-link.env.before-v13-8-1
```

```bash
sudo tar --exclude='artel-link/media' --exclude='artel-link/private_media' --exclude='artel-link/logs' --exclude='artel-link/backups' --exclude='artel-link/client_updates' -C /opt -czf /home/arteladmin/artel-link-code-before-v13-8-1.tar.gz artel-link
```

```bash
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_8_1_full_project.zip -d /home/arteladmin/upload/v13_8_1
```

```bash
sudo rsync -a --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_8_1/localgram/ /opt/artel-link/
```

```bash
sudo cp /home/arteladmin/artel-link.env.before-v13-8-1 /opt/artel-link/.env && sudo chown -R arteladmin:arteladmin /opt/artel-link && sudo chmod 600 /opt/artel-link/.env
```

```bash
cd /opt/artel-link && chmod +x scripts/*.sh && ./scripts/release_13_8_1.sh
```

В конце должно быть `READY: Artel Link 13.8.1`.

## Проверка 18+ и звонков

```bash
cd /opt/artel-link && docker compose ps -a && docker compose logs --tail=150 moderator web coturn
```

```bash
cd /opt/artel-link && ./scripts/presentation_check.sh
```

Если включён UFW:

```bash
cd /opt/artel-link && sudo bash scripts/enable_call_ports.sh
```

На внешнем firewall/NAT разрешите TCP/UDP `3478` и UDP `49160-49200` к серверу Artel Link.

## Внутреннее Desktop-обновление

На Windows-сборочной машине запустите `desktop\build_windows.cmd`. Затем загрузите `ArtelLink-13.8.1-Setup.exe`, `latest.yml` и `.blockmap` в `/home/arteladmin/upload/client_updates/windows/` и выполните:

```bash
cd /opt/artel-link && ./scripts/publish_client_update.sh windows /home/arteladmin/upload/client_updates/windows/ArtelLink-13.8.1-Setup.exe
```

Клиент загрузит обновление внутри Artel Link. После нажатия «Перезапустить сейчас» он установит новую версию с сохранением переписки и настроек; отдельная ручная переустановка не нужна. После запуска 13.8.1 кнопка обновления исчезает автоматически.
