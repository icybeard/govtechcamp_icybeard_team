# Database — PostgreSQL (+PostGIS)

Схема управляется EF Core миграциями из бэкенда: `backend/src/Api/Data/Migrations` (применяются автоматически при старте API). Справочник регионов и первый админ сидятся кодом (`DbSeeder`).

- `migrations/` — для «ручных» SQL-скриптов вне EF (например, PostGIS-индексы), нумерация `001_...sql`
- `seed/` — SQL, выполняемый контейнером при первом старте (`docker-entrypoint-initdb.d`)

Локальный запуск: `docker compose up -d` из корня (порт 5432, БД/пользователь/пароль — `govtech`).

Таблицы: `Users` (аккаунты, роли Admin/Analyst), `Regions` (области РК, IsoCode = shapeISO из geojson), `RegionMetrics` (метрики по модулям для заливки карты; уникальность по региону+module+metricKey+period).
