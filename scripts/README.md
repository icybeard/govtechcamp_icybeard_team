# Скрипты

Запуск стека — `docker compose up --build` или `make up` (см. Makefile); данные пилота сидируются автоматически.

Все скрипты — только стандартная библиотека Python (кроме отмеченных venv):

**Паводки (И-6):**
- `download_settlements.py <ISO> <out.csv>` — НП региона из OSM Overpass
- `load_settlements.py <ISO> <in.csv> [api-url]` — импорт НП в API
- `compute_terrain_features.py <ISO> <settlements.csv> <features.csv>` — рельеф: реки OSM + Copernicus DEM
- `download_era5.py [out.zip]` *(venv: cdsapi)* — ERA5-Land monthly, нужен ключ CDS
- `compute_era5_features.py <nc> <in.csv> <out.csv>` *(venv: netCDF4)* — снегозапас/осадки в % нормы
- `compute_season_features.py <nc> <base.csv> <out_dir> <от> <до>` *(venv)* — сезонные признаки + сводка для графика
- `build_labels.py <positives.csv> <settlements.csv> <labels.csv>` — разметка-2024 из позитивов СМИ
- `load_scores.py <ISO> <scores.csv> [api-url] [--period YYYY]` — скоры + факторы в API

**Пожары:**
- `fire_history.py` — исторические очаги FIRMS (июли 2021–2025) → приор районов `fire-history.json`
- дневная ML-модель — см. [ml/i9-fire-risk/](../ml/i9-fire-risk/) (`fetch/train/today`; `make fire-today`)

**Зима:**
- `winter_fetch.py [от] [до]` — зимние индексы по 16 областям → CSV (сеется в БД)
- `winter_fetch_districts.py [от] [до]` — то же по 174 районам → `winter-districts.json` (использует страница)

Полный пайплайн паводков: [ml/i6-flood-risk/README.md](../ml/i6-flood-risk/README.md). Один скрипт — одна задача.
