# GovTech Camp — команда IcyBeard

AI-решение для госсектора Казахстана (отборочный этап GovTech Camp, дедлайн **17.07.2026 23:59 GMT+5**).

Три идеи-кандидата разрабатываются как модули одного приложения:

| Код | Идея | Статус |
| --- | --- | --- |
| `i6-flood-risk` | Паводковый риск-скоринг населённых пунктов ⭐ фаворит | в работе |
| `i9-fire-risk` | Степные/лесные пожары: риск-карта и раннее оповещение | в работе |
| `poaching` | Мониторинг браконьерства | в работе |

## Быстрый старт (одна команда)

```bash
make up
```

Весь стек в docker-контейнерах: PostgreSQL (+PostGIS) → API (миграции применяются сами) → веб-клиент (nginx). При первом запуске создаётся `.env` из `.env.example` — там логин/пароль суперпользователя и JWT-ключ (поменяйте при необходимости; `.env` в git не попадает).

- **Веб-клиент:** http://localhost:5173 — вход суперпользователем из `.env` (по умолчанию `admin@icybeard.local` / `ChangeMe123!`)
- **API:** http://localhost:5080 (`/api/health`); из веб-клиента `/api` проксирует nginx
- `Ctrl+C` — остановить; `make upd` — в фоне; `make down` — погасить; `make clean` — сброс БД; `make logs` — логи

Для запуска нужен только Docker. Для локальной разработки с hot-reload (нужны .NET SDK 10 и Node.js 20+): `make db` + `make backend` + `make frontend` — vite и `dotnet watch` быстрее пересборки контейнеров. Детали — в [backend/README.md](backend/README.md) и [frontend/README.md](frontend/README.md).

## Стек

- **Frontend:** Vue 3 + PrimeVue (шаблон [Sakai](https://sakai.primevue.org/)), Leaflet-карта Казахстана
- **Backend:** .NET 10 minimal API, JWT-аутентификация, роли Admin/Analyst
- **DB:** PostgreSQL + PostGIS, EF Core миграции (применяются автоматически)
- **ML/Data:** Python-ноутбуки и пайплайны в `ml/`, результаты загружаются в API (`PUT /api/regions/metrics`)

## Структура репозитория

```
├── docs/          # ВСЕ документы — только здесь, по тематическим подпапкам
│   ├── org/           # договор, ТЗ, дедлайны, организационное
│   ├── ideas/         # проработка идей (по одной подпапке на идею)
│   ├── architecture/  # архитектура, ADR, схема БД
│   ├── data/          # описание датасетов: источники, структура, ограничения
│   └── presentation/  # презентация, сценарий демо-видео
├── frontend/      # Vue 3 SPA (Sakai): разделы идей, аккаунт, карта РК
├── backend/       # .NET solution: auth, аккаунт, регионы/метрики
├── database/      # заметки по схеме; EF-миграции — в backend/src/Api/Data/Migrations
├── ml/            # эксперименты и пайплайны Data Science (по идее)
├── data/          # датасеты (raw/ и processed/ — в git не коммитятся)
├── scripts/       # вспомогательные скрипты (загрузка данных и т.п.)
└── docker-compose.yml  # три сервиса: db (PostGIS, arm64/amd64), api, web (nginx)
```

## Как данные попадают на карту

1. ML-пайплайн (`ml/<идея>/`) считает скоры по регионам.
2. Загрузка в API: `PUT /api/regions/metrics` (роль Admin) с телом `{ module, metricKey, period, values: { "KZ-SEV": 87, ... } }`.
3. Фронтенд читает `GET /api/regions/metrics/{module}` и передаёт объект в `<KazakhstanMap :values="..." />`.

## Правила для команды (2 человека)

- Документы кладём **только в `docs/`**, в подходящую тематическую подпапку.
- Каждая идея везде называется своим кодом: `i6-flood-risk`, `i9-fire-risk`, `poaching`.
- Сырые датасеты — в `data/raw/` (не коммитим, в `docs/data/` описываем, откуда скачать).
- Работаем в ветках `feat/<код-идеи>-<что-делаем>`, мерджим в `main` через PR.

## Известные ограничения

- Границы регионов (`frontend/public/geo/kz-regions.geojson`) — geoBoundaries 2017 г., **16 регионов, без Абайской, Жетысу и Улытау**. Заменить синхронно с сидером регионов (`backend/src/Api/Data/DbSeeder.cs`).
- Скоры на страницах идей — демо-данные, до подключения ML-пайплайна.
