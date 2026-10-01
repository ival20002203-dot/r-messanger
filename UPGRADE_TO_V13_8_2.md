# Обновление Artel Link до 13.8.2 на Ubuntu

Загрузите `ArtelLink_v13_8_2_full_project.zip` в `/home/arteladmin/upload/`.

```bash
sudo timedatectl set-timezone Asia/Tashkent
sudo timedatectl set-ntp true
timedatectl status
```

```bash
sudo mkdir -p /home/arteladmin/upload/v13_8_2
sudo cp /opt/artel-link/.env /home/arteladmin/artel-link.env.before-v13-8-2
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_8_2_full_project.zip -d /home/arteladmin/upload/v13_8_2
sudo rsync -a --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_8_2/localgram/ /opt/artel-link/
sudo cp /home/arteladmin/artel-link.env.before-v13-8-2 /opt/artel-link/.env
sudo chown -R arteladmin:arteladmin /opt/artel-link
sudo chmod 600 /opt/artel-link/.env
```

```bash
cd /opt/artel-link
chmod +x scripts/*.sh
./scripts/release_13_8_2.sh
```

Проверка после запуска:

```bash
cd /opt/artel-link
docker compose ps -a
docker compose exec -T web python manage.py showmigrations accounts operations | tail -20
docker compose exec -T web python manage.py localgram_status
```

Для теста откройте Artel Link в двух окнах одного пользователя: закройте первое окно — статус должен остаться «в сети»; закройте последнее — второй пользователь должен увидеть точное серверное время выхода. Если Redis временно недоступен, статус продолжит работать через базу.

Для Desktop-сборки обновите версию до 13.8.2 через `desktop\build_windows.cmd`, опубликуйте установщик обычной командой `scripts/publish_client_update.sh`; обновление устанавливается внутри приложения.
