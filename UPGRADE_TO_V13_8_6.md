# Обновление Artel Link до 13.8.6

Релиз исправляет жизненный цикл присутствия сотрудников. Открытое приложение
показывает «в сети» даже при сворачивании и переключении окна. После закрытия
последнего окна сервер показывает собственное время выхода каждого сотрудника в
`Asia/Tashkent`. Статус и время разработчика скрыты от обычных пользователей.

Архив загрузите в `/home/arteladmin/upload/ArtelLink_v13_8_6_full_project.zip`.

```bash
cd /opt/artel-link
sudo cp .env /home/arteladmin/artel-link.env.before-v13-8-6
sudo mkdir -p /home/arteladmin/upload/v13_8_6
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_8_6_full_project.zip -d /home/arteladmin/upload/v13_8_6
sudo rsync -a --delete --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_8_6/localgram/ /opt/artel-link/
sudo cp /home/arteladmin/artel-link.env.before-v13-8-6 /opt/artel-link/.env
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

Ожидается версия `13.8.6` и применённая миграция
`operations.0019_artel_link_v13_8_6_presence_lifecycle`.

Переустанавливать Desktop не нужно: интерфейс и логика загружаются с обновлённого
сервера. Один раз полностью закройте Artel Link и откройте его снова; в браузере
используйте `Ctrl+F5`.
