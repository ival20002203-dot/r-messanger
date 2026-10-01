# R-Mes 15.0.0 — быстрый старт

## Проверить через VS Code

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run_dev_vscode.ps1
```

Открыть `http://127.0.0.1:8000`. DEV: `developer@rmes.local` / `RMesLocal-2026-Dev!` (сменить после входа).

## Полный сервер Docker

```powershell
.\scripts\first_start_windows.ps1 -ServerIp "10.30.10.25" -AdminEmail "you@company.uz"
```

## Указать адрес сервера клиентам

```powershell
.\scripts\configure_clients.ps1 -ServerUrl "http://10.30.10.25:8000"
```

## Windows installer

```powershell
cd desktop
npm install
.\build_windows.ps1
```

Получишь `desktop\dist\RMes-15.0.0-Setup.exe`. MSI: `npm run dist:gpo`.

## Android APK

Один раз создай ключ `mobile\android\generate_keystore_windows.cmd`, затем `mobile\android\build_apk_windows.cmd`.

## iPhone

На Mac открыть `mobile/ios/RMesIOS.xcodeproj` → Signing Team → Product → Archive.
