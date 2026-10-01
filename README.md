# R-Mes 15.0.0

R-Mes is a private messenger for web, Windows, Android and iPhone with realtime chats, voice messages, calls, files, moderation, administration and device security.

## Fast local start (Windows / VS Code)

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run_dev_vscode.ps1
```

Open `http://127.0.0.1:8000`.

Local developer account is printed by the start script.

## What is included in v15

- realtime WebSocket chats, delivery/read states, typing and exact presence;
- last-seen privacy: exact / recently / hidden, while Developer can audit exact presence;
- replies, reactions, forwarding, pins, polls, scheduled posts and folders;
- voice messages with animated waveform, seeking and 1x/1.5x/2x playback;
- WebRTC calls with TURN support;
- call recordings stored only in Developer Control Center, never as chat messages;
- native Android and iOS shells with app icon, splash, deep links and push-token integration;
- Windows Electron client with updater and tray mode;
- multi-device sessions and remote session revoke;
- upload progress, previews, authenticated files and image normalization;
- 18+ media moderation, DLP, ClamAV integration and audit logs;
- rate limits, anti-spam, backups, restore checks and Prometheus/Zabbix monitoring;
- optional FCM/APNs push notifications;
- production Docker stack: PostgreSQL, Redis, MinIO, ClamAV, TURN, Nginx and Caddy HTTPS.

## Public server

See `DEPLOY_FREE_RU.md`. For two testers the recommended zero-cost full-stack option is an Oracle Cloud Always Free VM when capacity is available.

## Mobile builds

- Android: `mobile/android/build_apk_windows.cmd`
- iPhone: open `mobile/ios/RMesIOS.xcodeproj` in Xcode, sign and Archive.

Set the public URL in every client at once:

```powershell
.\scripts\configure_clients.ps1 -ServerUrl "https://your-rmes-host"
```

## Important

Push notifications require your Firebase/APNs credentials. iOS installation requires Apple signing. Android release updates must always use the same keystore.
