# Database — PostgreSQL (+PostGIS)

- `migrations/` — миграции схемы (EF Core migrations или SQL-скрипты с нумерацией `001_...sql`)
- `seed/` — скрипты начальных данных; монтируются в контейнер и выполняются при первом старте `docker compose up`

Локальный запуск: `docker compose up -d` из корня репозитория (порт 5432, БД/пользователь/пароль — `govtech`).
