#!/usr/bin/env python3
"""Сезонные погодные признаки для ретроспективы 2010–2024.

Для каждого года Y подменяет в базовом features-файле погодные колонки на сезон Y:
снегозапас марта-Y (мм и % от нормы 2000–2023) и осадки Nov(Y−1)–Mar(Y).
Имена колонок сохраняются как в базовом файле (swe_mar2024_mm и т.д.) —
это метки признаков модели, «2024» в имени читать как «целевой сезон».

Дополнительно пишет frontend/public/data/season-summary.json —
медианный снегозапас (% нормы) по годам для графика в UI.

Использование (в venv с netCDF4):
    .venv/bin/python scripts/compute_season_features.py \
        data/raw/era5_kz-sev/data_stream-moda.nc \
        data/processed/features_kz-sev.csv data/processed 2010 2024
"""
import calendar
import csv
import json
import pathlib
import statistics
import sys

import netCDF4
import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SUMMARY_PATH = REPO_ROOT / "frontend/public/data/season-summary.json"


def main() -> None:
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    nc_path, base_csv, out_dir, year_from, year_to = sys.argv[1:6]
    years = range(int(year_from), int(year_to) + 1)

    ds = netCDF4.Dataset(nc_path)
    lats = ds.variables["latitude"][:]
    lons = ds.variables["longitude"][:]
    times = ds.variables["valid_time"][:]
    units = ds.variables["valid_time"].units
    sd = ds.variables["sd"][:]
    tp = ds.variables["tp"][:]

    dates = netCDF4.num2date(times, units)
    d_years = np.array([d.year for d in dates])
    d_months = np.array([d.month for d in dates])
    d_days = np.array([calendar.monthrange(d.year, d.month)[1] for d in dates])
    tp_monthly_mm = tp * d_days[:, None, None] * 1000.0

    swe_norm_mm = sd[(d_years <= 2023) & (d_months == 3)].mean(axis=0) * 1000.0

    def season_precip(year: int) -> np.ndarray:
        mask = ((d_years == year - 1) & np.isin(d_months, [11, 12])) | ((d_years == year) & np.isin(d_months, [1, 2, 3]))
        return tp_monthly_mm[mask].sum(axis=0)

    precip_norm = np.mean([season_precip(y) for y in range(2001, 2024)], axis=0)

    with open(base_csv, encoding="utf-8") as f:
        base_rows = list(csv.DictReader(f))
        fieldnames = list(base_rows[0].keys())

    # индексы ближайших ячеек считаем один раз
    cells = [(int(np.abs(lats - float(r["lat"])).argmin()), int(np.abs(lons - float(r["lon"])).argmin())) for r in base_rows]

    summary = []
    for year in years:
        swe_mm = sd[(d_years == year) & (d_months == 3)][0] * 1000.0
        precip_mm = season_precip(year)

        pct_values = []
        out_path = pathlib.Path(out_dir) / f"features_{year}_kz-sev.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row, (i, j) in zip(base_rows, cells):
                out = dict(row)
                swe = float(swe_mm[i, j])
                norm = float(swe_norm_mm[i, j])
                precip = float(precip_mm[i, j])
                p_norm = float(precip_norm[i, j])
                out["swe_mar2024_mm"] = round(swe, 1)
                out["swe_mar_pct_norm"] = round(100 * swe / norm, 1) if norm > 0.1 else ""
                out["precip_novmar_mm"] = round(precip, 1)
                out["precip_novmar_pct_norm"] = round(100 * precip / p_norm, 1) if p_norm > 0.1 else ""
                if out["swe_mar_pct_norm"] != "":
                    pct_values.append(out["swe_mar_pct_norm"])
                writer.writerow(out)

        median_pct = round(statistics.median(pct_values), 1)
        summary.append({"year": year, "sweMedianPctNorm": median_pct})
        print(f"{year}: снегозапас {median_pct}% нормы → {out_path}")

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Сводка: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
