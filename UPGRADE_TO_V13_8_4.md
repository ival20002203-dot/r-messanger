# Обновление Artel Link до 13.8.4

Архив загрузите в `/home/arteladmin/upload/ArtelLink_v13_8_4_full_project.zip`.
Команды обновляют код и сохраняют действующий `.env`, медиафайлы, логи и клиентские пакеты.

```bash
cd /opt/artel-link
sudo cp .env /home/arteladmin/artel-link.env.before-v13-8-4
sudo mkdir -p /home/arteladmin/upload/v13_8_4
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_8_4_full_project.zip -d /home/arteladmin/upload/v13_8_4
sudo rsync -a --delete --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_8_4/localgram/ /opt/artel-link/
sudo cp /home/arteladmin/artel-link.env.before-v13-8-4 /opt/artel-link/.env
sudo chown -R arteladmin:arteladmin /opt/artel-link
sudo chmod 600 /opt/artel-link/.env
cd /opt/artel-link
sudo chmod +x scripts/*.sh
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose exec -T web python manage.py migrate --noinput
sudo docker compose exec -T web python manage.py check
cat VERSION
sudo docker compose ps -a
```

Ожидается `13.8.4` и миграция `operations.0017_artel_link_v13_8_4_client_policy` со статусом `[X]`.
