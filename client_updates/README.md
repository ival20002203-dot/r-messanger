# R-Mes client updates

Put signed release artifacts here before restarting the server:

- `windows/RMes-<version>-Setup.exe`
- `android/RMes-<version>.apk`

`sync_client_versions` discovers the newest artifact and updates `ClientVersionPolicy`. Desktop can download and launch the signed installer; Android downloads an in-place APK update signed with the same keystore. iOS updates are distributed through TestFlight/App Store.
