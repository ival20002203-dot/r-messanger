R-Messanger — rollback Screen Privacy

Этот патч ОТМЕНЯЕТ только:
- блокировку скриншотов Windows/Electron;
- FLAG_SECURE Android;
- black-screen shield iOS;
- браузерный black-screen overlay при blur/PrintScreen.

НЕ отменяет:
- изменения звонков;
- отключение аудиозаписи звонков;
- privacy/last seen;
- интерфейс и переводы;
- остальные функции v15.1.2.

Установка:
1. Остановить сервер Ctrl+C.
2. PowerShell в папке патча:
   Set-ExecutionPolicy -Scope Process Bypass
   .\APPLY_ROLLBACK.ps1 -ProjectRoot "N:\VS CODE\localgram"
3. Запустить сервер:
   cd "N:\VS CODE\localgram"
   .\scripts\run_dev_vscode.ps1
4. Ctrl+F5 в браузере.

Для уже собранных Android/iOS/Desktop приложений нужно пересобрать клиент,
потому что OS-level защита находится внутри native/desktop кода.
