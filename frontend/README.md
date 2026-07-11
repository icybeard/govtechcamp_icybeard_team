# Frontend — Vue 3 (Sakai / PrimeVue)

Основан на шаблоне [Sakai Vue](https://github.com/primefaces/sakai-vue) (MIT): PrimeVue 4 + Tailwind. Оригинальный README шаблона — `SAKAI.md`.

## Запуск

В контейнере (вместе со всем стеком): `make up` из корня — Dockerfile собирает Vite-бандл и отдаёт его через nginx (`nginx.conf`), который проксирует `/api` на контейнер `api`.

Локально с hot-reload:

```bash
npm install
npm run dev        # http://localhost:5173, /api проксируется vite на бэкенд :5080
```

Вход: сид-админ `admin@icybeard.local` / `ChangeMe123!` (создаётся бэкендом).

## Структура

- `src/views/ideas/` — разделы идей: `FloodRisk.vue`, `FireRisk.vue`, `Poaching.vue`
- `src/views/account/AccountSettings.vue` — настройки аккаунта (профиль, пароль)
- `src/components/KazakhstanMap.vue` — интерактивная карта РК (Leaflet): хороплет по `values` (`{ 'KZ-PAV': 42 }`), события `region-click`/`region-hover`, легенда
- `src/service/api.js` — fetch-обёртка с JWT; `src/service/auth.js` — состояние пользователя, login/logout
- `src/router/index.js` — маршруты + guard (без токена → `/auth/login`)
- `public/geo/kz-regions.geojson` — границы областей (geoBoundaries, **2017 г., 16 регионов** — заменить на границы 2022 г. вместе с сидером регионов в бэкенде)

Раздел меню «Справочник (Sakai UI Kit)» — примеры компонентов на время разработки, перед сдачей удалить.

## Демо-данные

Скоры на страницах идей сейчас захардкожены. Реальные значения брать из API:
`GET /api/regions/metrics/flood-risk?metricKey=risk_score` → `{ 'KZ-SEV': 87, ... }` — этот объект отдавать в `<KazakhstanMap :values="..." />`.
