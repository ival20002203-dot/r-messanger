# Обновление Artel Link до 13.7.0 на Ubuntu

Архив должен находиться здесь:

```text
/home/arteladmin/upload/ArtelLink_v13_7_full_project.zip
```

Команды выполняются по одной. Они сохраняют `.env`, пользовательские файлы, журналы, резервные копии и опубликованные клиентские обновления.

## 1. Резервная копия и распаковка

```bash
sudo mkdir -p /home/arteladmin/upload/v13_7
```

```bash
sudo cp /opt/artel-link/.env /home/arteladmin/artel-link.env.before-v13-7
```

```bash
sudo tar --exclude='artel-link/media' --exclude='artel-link/private_media' --exclude='artel-link/logs' --exclude='artel-link/backups' --exclude='artel-link/client_updates' -C /opt -czf /home/arteladmin/artel-link-code-before-v13-7.tar.gz artel-link
```

```bash
sudo unzip -o /home/arteladmin/upload/ArtelLink_v13_7_full_project.zip -d /home/arteladmin/upload/v13_7
```

## 2. Установка нового кода без удаления постоянных данных

```bash
sudo rsync -a --exclude='.env' --exclude='media/' --exclude='private_media/' --exclude='logs/' --exclude='backups/' --exclude='client_updates/' /home/arteladmin/upload/v13_7/localgram/ /opt/artel-link/
```

```bash
sudo cp /home/arteladmin/artel-link.env.before-v13-7 /opt/artel-link/.env
```

```bash
sudo chown -R arteladmin:arteladmin /opt/artel-link
```

```bash
sudo chmod 600 /opt/artel-link/.env
```

## 3. Сборка, миграции и автоматическая проверка

```bash
cd /opt/artel-link && chmod +x scripts/*.sh && ./scripts/release_13_7.sh
```

В конце должно появиться:

```text
READY: Artel Link 13.7.0
```

Дополнительная проверка:

```bash
cd /opt/artel-link && cat VERSION && docker compose exec -T web python manage.py showmigrations chat operations && curl -fsS http://127.0.0.1:8000/healthz/ && docker compose ps -a
```

## 4. Порты аудиозвонков

Если на сервере включён UFW:

```bash
cd /opt/artel-link && sudo bash scripts/enable_call_ports.sh
```

Нужно также разрешить на внешнем firewall/NAT TCP и UDP `3478`, а также UDP `49160-49200`, направленные на сервер с coturn.

## 5. Публикация Desktop-обновления

На Windows соберите клиент командой `desktop\\build_windows.cmd`. Из `desktop\\dist` загрузите на сервер установщик, `latest.yml` и файл `.blockmap` в каталог:

```text
/home/arteladmin/upload/client_updates/windows/
```

Публикация выполняется атомарно:

```bash
cd /opt/artel-link && ./scripts/publish_client_update.sh windows /home/arteladmin/upload/client_updates/windows/ArtelLink-13.7.0-Setup.exe
```

Feed проверяется так:

```bash
curl -fsS http://127.0.0.1:8000/ops/client-update/feed/windows/latest.yml
```

Важно: установленный Desktop 13.6.0 ещё не содержит нового фонового updater. Поэтому переход с 13.6.0 на 13.7.0 нужно выполнить один раз через текущий механизм установки/GPO. После запуска 13.7.0 дальнейшие версии будут скачиваться внутри Artel Link и применяться после подтверждения перезапуска.

## Откат кода

Если проверка завершилась ошибкой, не удаляйте Docker volumes. Восстановите сохранённый архив кода и `.env`, затем выполните прежний `docker compose up -d --build` и совместимую миграцию/восстановление базы по вашей политике резервного копирования.
