# Web + Desktop architecture

Artel Link 11 использует один backend/PostgreSQL/Redis/MinIO для обеих оболочек.

- Web: обычный браузер, класс `web-app`.
- Desktop: Electron, отдельный User-Agent `ArtelLinkDesktop/<version>` и класс `desktop-app`.
- Сообщения, настройки, папки, прочтения и медиа синхронизируются через один сервер.
- Внутренние HTTP/HTTPS ссылки остаются внутри Desktop. Внешние сайты открываются системным браузером.
- Desktop сохраняет собственную cookie/session storage, поэтому web и desktop могут быть авторизованы независимо, но данные остаются общими.
