#!/usr/bin/env python3
"""Добавляет к признакам НП погодные признаки ERA5-Land (снегозапас, осадки).

Признаки (по ближайшей ячейке сетки 0.1°):
  swe_mar2024_mm          — снегозапас на март 2024, мм водного эквивалента
  swe_mar_pct_norm        — тот же снегозапас в % от нормы (среднее март 2000–2023)
  precip_novmar_mm        — сумма осадков ноябрь-2023 … март-2024, мм
  precip_novmar_pct_norm  — в % от нормы (средние суммы Nov–Mar 2000–2023)

Использование (в venv с netCDF4):
    .venv/bin/python scripts/compute_era5_features.py \
        data/raw/era5_kz-sev/data_stream-moda.nc \
        data/processed/features_kz-sev.csv data/processed/features_kz-sev.csv
"""
import calendar
import csv
import sys

import netCDF4
import numpy as np


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    nc_path, input_csv, output_csv = sys.argv[1:4]

    ds = netCDF4.Dataset(nc_path)
    lats = ds.variables["latitude"][:]
    lons = ds.variables["longitude"][:]
    times = ds.variables["valid_time"][:]
    units = ds.variables["valid_time"].units
    sd = ds.variables["sd"][:]  # м водного эквивалента (snow depth water equivalent)
    tp = ds.variables["tp"][:]  # м/день (среднесуточные осадки за месяц)

    dates = netCDF4.num2date(times, units)
    years = np.array([d.year for d in dates])
    months = np.array([d.month for d in dates])
    days = np.array([calendar.monthrange(d.year, d.month)[1] for d in dates])

    # Снегозапас: март 2024 и норма по мартам 2000–2023
    mar_2024 = (years == 2024) & (months == 3)
    mar_norm = (years < 2024) & (months == 3)

    # Осадки: сезонная сумма Nov(Y-1)..Mar(Y); mm = tp(м/день) * дни * 1000
    tp_monthly_mm = tp * days[:, None, None] * 1000.0

    def season_sum(year: int) -> np.ndarray:
        mask = ((years == year - 1) & np.isin(months, [11, 12])) | ((years == year) & np.isin(months, [1, 2, 3]))
        return tp_monthly_mm[mask].sum(axis=0)

    precip_2024 = season_sum(2024)
    precip_norm = np.mean([season_sum(y) for y in range(2001, 2024)], axis=0)

    swe_2024_mm = sd[mar_2024][0] * 1000.0
    swe_norm_mm = sd[mar_norm].mean(axis=0) * 1000.0

    with open(input_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    new_cols = ["swe_mar2024_mm", "swe_mar_pct_norm", "precip_novmar_mm", "precip_novmar_pct_norm"]
    for row in rows:
        i = int(np.abs(lats - float(row["lat"])).argmin())
        j = int(np.abs(lons - float(row["lon"])).argmin())
        swe = float(swe_2024_mm[i, j])
        swe_norm = float(swe_norm_mm[i, j])
        precip = float(precip_2024[i, j])
        p_norm = float(precip_norm[i, j])
        row["swe_mar2024_mm"] = round(swe, 1)
        row["swe_mar_pct_norm"] = round(100 * swe / swe_norm, 1) if swe_norm > 0.1 else ""
        row["precip_novmar_mm"] = round(precip, 1)
        row["precip_novmar_pct_norm"] = round(100 * precip / p_norm, 1) if p_norm > 0.1 else ""

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames + new_cols)
        writer.writeheader()
        writer.writerows(rows)

    swe_vals = [float(r["swe_mar_pct_norm"]) for r in rows if r["swe_mar_pct_norm"] != ""]
    print(f"{len(rows)} НП; снегозапас март-2024 в % нормы: медиана {np.median(swe_vals):.0f}%, максимум {max(swe_vals):.0f}% → {output_csv}")


if __name__ == "__main__":
    main()
