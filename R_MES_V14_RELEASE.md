# R-Mes 14.0.0

Полный исходный проект включён в релиз. Пользовательский бренд заменён на **R-Mes**; внутреннее Django-имя `localgram` и старые migration filenames сохранены, чтобы не ломать БД.

Исправлено: developer видит online/last seen всех ролей; presence developer/superadmin скрыт от остальных; control panel использует реальный presence snapshot. Добавлены Windows Electron, Android и iOS native shells, `rmes://`, единый скрипт смены server URL, `.env` validator, DEV и Docker first-start scripts.
