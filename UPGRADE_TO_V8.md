# Upgrade to V8 (Artel Link)

## Что нового
- новое название продукта: **Artel Link**;
- обновлён desktop brand + иконка;
- улучшенный UI/UX и анимации;
- добавлена миграция `0008_artel_link_branding`;
- desktop поддерживает GPO-friendly MSI сборку: `npm run dist:gpo`.

## Обновление
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

## Desktop
```powershell
cd desktop
npm install
npm run dist:win
npm run dist:gpo
```
