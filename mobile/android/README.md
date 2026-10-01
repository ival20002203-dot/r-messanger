# R-Mes Android 15.0.0

Это устанавливаемое Android-приложение, а не вкладка браузера. Оно использует собственный package `uz.rmes.app`, splash, иконку, deep-link `rmes://`, камеру/микрофон, системные загрузки и FCM push.

## Адрес сервера

Меняется общим скриптом из корня проекта:

```powershell
.\scripts\configure_clients.ps1 -ServerUrl "https://rmes.example.com"
```

## Push

Для настоящих push положите Firebase `google-services.json` в:

`mobile/android/app/google-services.json`

и настройте на сервере `PUSH_ENABLED=1`, `FCM_PROJECT_ID`, `FCM_SERVICE_ACCOUNT_FILE`.
Без Firebase приложение всё равно собирается и работает, просто без background push.

## Сборка Windows

1. Android Studio + SDK Platform 35 / Build Tools 35.x.
2. Один раз: `generate_keystore_windows.cmd`.
3. Всегда храните `rmes-release.jks` и `keystore.properties` — обновления должны подписываться тем же ключом.
4. Запустите `build_apk_windows.cmd`.

Результат:

- `RMes-15.0.0.apk` — ручная установка/тест;
- `RMes-15.0.0.aab` — Google Play.
