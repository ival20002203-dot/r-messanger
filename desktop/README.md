# R-Mes Desktop v15.0.0

Native Electron desktop shell for the R-Mes server.

Default test server in this build:

```text
http://10.10.10.130:8000
```

The address can later be changed inside **Настройки → Приложение** without rebuilding the client.

## v15 behavior

- opens R-Mes inside its own application window, not in the browser;
- internal R-Mes links stay inside the application;
- external websites open in the system browser;
- Windows system tray and minimize-to-tray;
- optional launch with Windows;
- server address editor inside R-Mes settings;
- app-lock integration: if the user enabled a PIN and **При каждом запуске**, Desktop opens the server lock screen before showing chats;
- tray menu contains **Заблокировать**;
- camera, microphone and notifications are allowed only for configured R-Mes origins;
- cookies/session are persisted by Electron so the app remains synchronized with the web server;
- old v10/v11 default URLs are automatically migrated to the current test server URL.

## Development

```powershell
cd desktop
npm.cmd install
npm.cmd start
```

## Windows installer + MSI for GPO

Run:

```powershell
.\build_windows.ps1
```

or:

```cmd
build_windows.cmd
```

Generated files are placed in `desktop\dist\`.

Expected installer:

```text
RMes-15.0.0-Setup.exe
```

The MSI uses a stable `upgradeCode`, so later versions can upgrade the same per-machine GPO installation.
