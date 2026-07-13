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

- `src/views/ideas/` — `FloodRisk.vue` (520 НП, сезоны 2010–2026, очередь мер, live-погода), `FireRisk.vue` (live: метео-индекс по 174 районам, очаги FIRMS), `Poaching.vue` (концепция)
- `src/views/Dashboard.vue` — сводка пилота; `src/views/account/AccountSettings.vue` — профиль/пароль
- `src/components/KazakhstanMap.vue` — карта (Leaflet). Props: `values` (хороплет `{ключ: число}`), `points` (кружки НП), `markers` (div-иконки: 🔥, стрелки), `tileOverlays` (слои NASA GIBS, отдельная панель поверх заливки), `windGrid` (анимация ветра leaflet-velocity), `geoUrl` (области по умолчанию / `kz-districts.geojson`), `height`
- `src/service/` — `api.js` (fetch+JWT), `auth.js`, `weather.js` (Open-Meteo: погода по центроидам + сетка ветра, ретраи на 429), `gibs.js` (тайлы NASA GIBS без ключей)
- `public/geo/` — `kz-regions.geojson` (области, 2017 г., 16 шт.) и `kz-districts.geojson` (районы ADM2, 174 шт.)
- `public/data/season-summary.json` — снегозапас по годам для графика (генерирует `scripts/compute_season_features.py`)

## Данные

Скоры приезжают из API (автосид при первом старте контейнера): `GET /api/settlements/metrics/flood-risk?metricKey=risk_score&period=2024`. Live-слои — напрямую с Open-Meteo/GIBS (без ключей) и `/api/fire/hotspots` (нужен `FIRMS_MAP_KEY`).
