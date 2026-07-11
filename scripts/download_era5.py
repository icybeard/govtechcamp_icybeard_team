#!/usr/bin/env python3
"""Скачивает ERA5-Land monthly means для региона (снегозапас, осадки, температура).

Требует ключ CDS в ~/.cdsapirc и пакет cdsapi (см. .venv):
    .venv/bin/python scripts/download_era5.py data/raw/era5_land_monthly_kz-sev.nc

Область по умолчанию — бокс СКО с запасом. Годы 2000–2024: 2024 — целевой,
остальные — климатическая норма для признака «снегозапас в % от нормы».
"""
import sys

import cdsapi

# North, West, South, East — бокс СКО
AREA_KZ_SEV = [56.0, 65.0, 52.5, 71.5]

VARIABLES = [
    "2m_temperature",
    "total_precipitation",
    "snow_depth_water_equivalent",
    "snowmelt",
    "surface_runoff",
]


def main() -> None:
    output = sys.argv[1] if len(sys.argv) > 1 else "data/raw/era5_land_monthly_kz-sev.nc"

    client = cdsapi.Client()
    client.retrieve(
        "reanalysis-era5-land-monthly-means",
        {
            "product_type": "monthly_averaged_reanalysis",
            "variable": VARIABLES,
            "year": [str(y) for y in range(2000, 2025)],
            "month": ["01", "02", "03", "04", "11", "12"],
            "time": "00:00",
            "area": AREA_KZ_SEV,
            "format": "netcdf",
        },
        output,
    )
    print(f"Сохранено: {output}")


if __name__ == "__main__":
    main()
