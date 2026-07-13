# Скрипты

Запуск стека — через `make up` в корне репозитория (см. Makefile), отдельного скрипта нет.

Скрипты (только стандартная библиотека Python, без pip):

- `download_settlements.py <ISO> <out.csv>` — населённые пункты региона из OSM Overpass (имя, координаты, население). Принимает коды приложения (`KZ-SEV`), внутри маппит на новые OSM-коды (`KZ-59`).
- `load_settlements.py <ISO> <in.csv> [api-url]` — импорт CSV в API (`POST /api/settlements/import`), логин суперпользователем из `.env`.
- `compute_terrain_features.py <ISO> <settlements.csv> <features.csv>` — признаки рельефа: реки из OSM, высоты из Copernicus DEM (Open-Meteo Elevation API); выдаёт высоту, расстояние до реки и превышение над рекой.
- `load_scores.py <ISO> <scores.csv> [api-url]` — скоры + факторы «почему» в API (`PUT /api/settlements/metrics`); матчит по имени и координатам.

Полный пайплайн И-6 — см. [ml/i6-flood-risk/README.md](../ml/i6-flood-risk/README.md).

Дальше сюда: Sentinel-1 (разметка затоплений), ERA5 (снегозапас, нужен ключ CDS), FIRMS/NDVI для И-9. Один скрипт — одна задача.
