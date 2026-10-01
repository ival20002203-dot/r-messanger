# Обновление Artel Link до 13.8.5

Релиз исправляет именно присутствие пользователей: каждый браузер/клиент
получает собственную lease-сессию, статус меняется на «в сети» при входе и на
«был(а) в сети …» при выходе. Время рассчитывается сервером в `Asia/Tashkent`.
Время и online-состояние разработчика не отдаются обычным пользователям.

Архив загрузите в `/home/arteladmin/upload/ArtelLink_v13_8_5_full_project.zip`.

```bash
cd /opt/artel-link
sudo cp .env /home/arteladmin/artel-link.env.before-v13-8-5
sudo mkdir -p /home/arteladmin/upload/v13_8_5
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_8_5_full_project.zip -d /home/arteladmin/upload/v13_8_5
sudo rsync -a --delete --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_8_5/localgram/ /opt/artel-link/
sudo cp /home/arteladmin/artel-link.env.before-v13-8-5 /opt/artel-link/.env
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

Ожидается `13.8.5` и применённая миграция
`operations.0018_artel_link_v13_8_5_presence_policy`.

После обновления достаточно перезапустить клиент/обновить вкладку. Данные,
переписка, `.env`, media и настройки не переустанавливаются и не удаляются.
