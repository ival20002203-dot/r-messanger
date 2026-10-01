# Artel Link 13.3.0 — installation for the presentation server

The archive is a full project. Keep the current `.env` and Docker volumes.

```bash
cp /opt/artel-link/.env /home/arteladmin/artel-link.env.before-v13-3
mkdir -p /home/arteladmin/upload/v13_3
unzip -o /home/arteladmin/upload/ArtelLink_v13_3_full_project.zip -d /home/arteladmin/upload/v13_3
sudo cp -a /home/arteladmin/upload/v13_3/localgram/. /opt/artel-link/
sudo cp /home/arteladmin/artel-link.env.before-v13-3 /opt/artel-link/.env
sudo chown -R arteladmin:arteladmin /opt/artel-link
chmod 600 /opt/artel-link/.env
cd /opt/artel-link
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py check
bash scripts/presentation_check.sh
```

For calls through TURN, if UFW is enabled:

```bash
cd /opt/artel-link
bash scripts/enable_call_ports.sh
```

For production change the TURN password in `.env`:

```env
TURN_ENABLED=1
TURN_HOST=10.10.10.130
TURN_USERNAME=artellink
TURN_PASSWORD=<strong password>
RTC_ICE_SERVERS_JSON=[]
```

Build the Windows Desktop 13.3 client from `desktop/build_windows.cmd`, then publish it with:

```bash
./scripts/publish_client_update.sh windows /home/arteladmin/upload/client_updates/windows/ArtelLink-13.3.0-Setup.exe
```

Do not run `docker compose down -v`.
