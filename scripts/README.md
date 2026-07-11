# Скрипты

Запуск стека — через `make up` в корне репозитория (см. Makefile), отдельного скрипта нет.

Скрипты (только стандартная библиотека Python, без pip):

- `download_settlements.py <ISO> <out.csv>` — населённые пункты региона из OSM Overpass (имя, координаты, население). Принимает коды приложения (`KZ-SEV`), внутри маппит на новые OSM-коды (`KZ-59`).
- `load_settlements.py <ISO> <in.csv> [api-url]` — импорт CSV в API (`POST /api/settlements/import`), логин суперпользователем из `.env`.

Пайплайн И-6: `download_settlements.py KZ-SEV data/raw/settlements_kz-sev.csv` → `load_settlements.py KZ-SEV ...` → ML считает скоры → `PUT /api/settlements/metrics` (значение + SHAP-факторы) → карта.

Дальше сюда: скачивание Sentinel-1/DEM/ERA5 (см. docs/ideas/i6-flood-risk/plan.md), FIRMS/NDVI для И-9. Один скрипт — одна задача.
