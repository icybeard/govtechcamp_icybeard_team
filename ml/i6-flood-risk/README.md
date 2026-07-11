# И-6. ML-пайплайн паводкового риска

## Пайплайн (данные → карта)

```bash
# 1. НП региона из OSM → CSV → в БД приложения
python3 scripts/download_settlements.py KZ-SEV data/raw/settlements_kz-sev.csv
python3 scripts/load_settlements.py KZ-SEV data/raw/settlements_kz-sev.csv

# 2. Признаки рельефа/гидрографии (OSM реки + Copernicus DEM через Open-Meteo)
python3 scripts/compute_terrain_features.py KZ-SEV \
    data/raw/settlements_kz-sev.csv data/processed/features_kz-sev.csv

# 2b. Погодные признаки ERA5-Land: снегозапас и осадки в % от нормы
#     (нужен ключ CDS в ~/.cdsapirc и .venv: python3 -m venv .venv && .venv/bin/pip install cdsapi netCDF4)
.venv/bin/python scripts/download_era5.py data/raw/era5_land_monthly_kz-sev.nc
# CDS отдаёт zip: unzip в data/raw/era5_kz-sev/
.venv/bin/python scripts/compute_era5_features.py \
    data/raw/era5_kz-sev/data_stream-moda.nc \
    data/processed/features_kz-sev.csv data/processed/features_kz-sev.csv

# 3a. Пока нет разметки: прозрачный baseline-скоринг (stdlib, без ML)
python3 ml/i6-flood-risk/baseline_scores.py \
    data/processed/features_kz-sev.csv data/processed/scores_kz-sev.csv

# 3b. Когда есть разметка затоплений-2024 (гейт 12.07): LightGBM + SHAP
pip install -r ml/i6-flood-risk/requirements.txt
python3 ml/i6-flood-risk/train.py \
    data/processed/features_kz-sev.csv data/raw/labels_2024.csv data/processed/scores_kz-sev.csv

# 4. Скоры + факторы → API → карта
python3 scripts/load_scores.py KZ-SEV data/processed/scores_kz-sev.csv
```

## Разметка (labels_2024.csv)

Формат: `name,flooded` (1 — НП затапливался весной 2024, 0 — нет). Источники: маска воды
Sentinel-1 на пике паводка + сводки ДЧС/СМИ. Методику разметки документировать в docs/data/.

## Baseline vs модель

`baseline_scores.py` — интерпретируемый индекс из двух факторов (близость к реке,
превышение над рекой). Это НЕ ML: он нужен, чтобы приложение жило до разметки,
и как бенчмарк для слайда «наша модель лучше baseline на X%».

`train.py` — LightGBM на признаках рельефа/снегозапаса с валидацией по районам,
SHAP-объяснениями на каждый НП и сравнением с baseline. Признаки ERA5 (снегозапас)
добавить сюда после скачивания (требуется ключ CDS API).
