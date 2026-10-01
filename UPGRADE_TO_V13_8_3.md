# Обновление Artel Link до 13.8.3 на Ubuntu

Загрузите `ArtelLink_v13_8_3_full_project.zip` в `/home/arteladmin/upload/`.

```bash
cd /opt/artel-link
sudo cp .env /home/arteladmin/artel-link.env.before-v13-8-3
sudo mkdir -p /home/arteladmin/upload/v13_8_3
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_8_3_full_project.zip -d /home/arteladmin/upload/v13_8_3
sudo rsync -a --delete --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_8_3/localgram/ /opt/artel-link/
sudo cp /home/arteladmin/artel-link.env.before-v13-8-3 /opt/artel-link/.env
sudo chown -R arteladmin:arteladmin /opt/artel-link
sudo chmod 600 /opt/artel-link/.env
cd /opt/artel-link
chmod +x scripts/*.sh
docker compose up -d --build
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py check
docker compose ps -a
```

После входа откройте **Настройки → Язык** и выберите язык. Поле времени не заполняется вручную: сервер всегда использует `Asia/Tashkent`. Проверьте, что `docker compose exec web python manage.py showmigrations accounts` показывает `[X] 0014_artel_link_language_preferences`.
