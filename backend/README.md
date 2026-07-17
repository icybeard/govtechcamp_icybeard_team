# Backend — .NET 10 API

Единый Web API (`src/Api`, minimal API), идеи — папками-модулями внутри проекта:

```
backend/
├── GovTech.sln
└── src/Api/
    ├── Program.cs            # DI, JWT, CORS, авто-миграция + сид при старте
    ├── Auth/                 # JWT-сервис, /api/auth (login, register, me)
    ├── Account/              # /api/account (профиль, смена пароля)
    ├── Modules/              # regions, settlements, measures (очередь мер), fire (FIRMS-прокси)
    └── Data/                 # AppDbContext, сущности, DbSeeder (справочники+админ),
                              # DataFileSeeder (автосид CSV пилота при пустой БД), Migrations/
```

## Запуск

В контейнере (вместе со всем стеком): `make up` из корня. Образ — multi-stage `Dockerfile` (sdk → aspnet, порт 8080 внутри, 5080 снаружи); конфигурация передаётся через env в `docker-compose.yml`.

Локально с hot-reload:

```bash
make db                       # PostgreSQL (из корня репозитория)
cd backend/src/Api
dotnet watch                  # http://localhost:5080, миграции применятся сами
```

## Суперпользователь

Создаётся сидером при старте API из `.env` в корне репозитория (`SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, см. `.env.example`):

- если пользователя с таким email нет — создаётся с ролью `Admin`;
- если есть — ему гарантируется роль `Admin` (пароль не перезаписывается).

`.env` читают и docker-compose (подстановка в environment), и локальный `dotnet run` (загрузчик `EnvFile.cs` ищет файл вверх по дереву). Приоритет: переменная окружения → `.env` → appsettings.

## Аутентификация и роли

- JWT Bearer, токен живёт 12 часов. Ключ — `JWT_KEY` в `.env` (dev-fallback в `appsettings.Development.json`); в проде задавать через env `JWT__KEY`/`JWT_KEY`.
- Роли: `Admin` (загрузка метрик), `Analyst` (все остальные, назначается при регистрации).

## API

| Метод | Путь | Доступ |
| --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login` | публичный |
| GET | `/api/auth/me` | авторизованный |
| PUT | `/api/account/profile`, `/api/account/password` | авторизованный |
| GET | `/api/regions/`, `/api/regions/metrics/{module}` | авторизованный |
| PUT | `/api/regions/metrics` | Admin |
| GET | `/api/settlements/?region=`, `/api/settlements/metrics/{module}?metricKey=&period=` | авторизованный |
| POST | `/api/settlements/import` | Admin |
| PUT | `/api/settlements/metrics` | Admin |
| GET | `/api/measures/?module=&status=&settlementId=` | авторизованный |
| POST | `/api/measures/`, `/api/measures/generate` | авторизованный / Admin; generate: flood-risk — из метрик НП в БД, fire-risk/winter-risk — из `districtValues` (скоры районов присылает фронт) |
| PUT | `/api/measures/{id}/status` | авторизованный (аудит: кто/когда) |
| GET | `/api/fire/hotspots` | авторизованный (прокси NASA FIRMS, кэш 15 мин, ключ `FIRMS_MAP_KEY`) |
| GET | `/api/datasets/` | авторизованный (реестр загруженных наборов) |
| POST | `/api/datasets/upload` | Admin (multipart: file + kind + period + note; kind=flood-scores ингестируется в метрики сразу) |
| DELETE | `/api/datasets/{id}` | Admin |

**Важно:** `GET .../metrics/{module}` без `period` возвращает все сезоны разом; для актуальных скоров И-6 передавайте `period=2024`.

`PUT /api/regions/metrics` — канал обогащения карты из ML-пайплайна:

```json
{ "module": "flood-risk", "metricKey": "risk_score", "period": "2026-04",
  "values": { "KZ-SEV": 87, "KZ-AKT": 82 } }
```

## Миграции

EF Core миграции лежат в `src/Api/Data/Migrations` (локальный tool `dotnet-ef`):

```bash
cd backend/src/Api
dotnet ef migrations add <Name> -o Data/Migrations
```

Применяются автоматически при старте приложения.
