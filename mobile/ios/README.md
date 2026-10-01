# R-Mes iOS 15.0.0

Это устанавливаемое iPhone-приложение на WKWebView с отдельным bundle id `uz.rmes.ios`, splash, deep-link `rmes://`, камерой/микрофоном и APNs token bridge.

## Сборка

1. На Mac откройте `RMesIOS.xcodeproj` в Xcode.
2. Target → Signing & Capabilities → выберите Apple Team.
3. Проект уже содержит push entitlement; в Apple Developer/Xcode включите **Push Notifications** и **Background Modes → Remote notifications** для вашего Team.
4. Проверьте bundle id.
5. Product → Archive → Distribute App → TestFlight/App Store.

Адрес сервера меняется в `RMesIOS/AppConfig.swift` или общим `scripts/configure_clients.ps1`.

На сервере для push укажите `PUSH_ENABLED=1`, APNs `.p8` key, Key ID, Team ID и bundle id. `.ipa` нельзя корректно подписать без вашего Apple Developer Team/Xcode.
