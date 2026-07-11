# Backend — .NET

Единое API-решение. Предлагаемая структура solution:

```
backend/
├── GovTech.sln
├── src/
│   ├── Api/                  # ASP.NET Core Web API, единая точка входа
│   ├── Shared/               # общие сущности, доступ к PostgreSQL, утилиты
│   └── Modules/
│       ├── FloodRisk/        # i6-flood-risk
│       ├── FireRisk/         # i9-fire-risk
│       └── Poaching/         # poaching
└── tests/
```

Инициализация:

```bash
dotnet new sln -n GovTech
dotnet new webapi -o src/Api
dotnet sln add src/Api
```

Строка подключения к локальной БД (см. docker-compose.yml в корне):
`Host=localhost;Port=5432;Database=govtech;Username=govtech;Password=govtech`
