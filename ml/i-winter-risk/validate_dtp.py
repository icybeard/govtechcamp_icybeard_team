#!/usr/bin/env python3
"""Валидация зимней ML-модели на фактических ДТП (qamqor.gov.kz или любая выгрузка).

Модель обучена предсказывать предупреждения Казгидромета; здесь проверяем её
на независимых фактах: ловят ли дни с высоким скором реальные зимние аварии.

Вход — CSV с ДТП, колонки определяются по именам (регистронезависимо):
  дата  — содержит "date"/"дата";  широта — "lat"/"шир";  долгота — "lon"/"lng"/"долг".
Берутся только зимние дни (ноябрь–март) сезонов из winter_daily_features.csv.

Метрики: какая доля ДТП приходится на топ-10%/20% «район-дней» по скору модели
(capture) и во сколько раз плотность ДТП в топ-скорах выше среднего (lift).

Использование: .venv/bin/python ml/i-winter-risk/validate_dtp.py data/raw/dtp.csv
Выход: печать + ml/i-winter-risk/validation_dtp.json
"""
import csv
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
GEO_DISTRICTS = REPO / "frontend/public/geo/kz-districts.geojson"
FEATURES_CSV = REPO / "data/processed/winter_daily_features.csv"
MODEL_PATH = REPO / "data/processed/winter_lgbm.txt"
METRICS_PATH = REPO / "ml/i-winter-risk/metrics.json"
OUT = REPO / "ml/i-winter-risk/validation_dtp.json"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winter_ml import FEATURES, add_doy  # noqa: E402


def load_district_polygons():
    geo = json.loads(GEO_DISTRICTS.read_text(encoding="utf-8"))
    out = []
    for f in geo["features"]:
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        outers = [poly[0] for poly in polys]
        lats = [lat for ring in outers for _, lat in ring]
        lons = [lon for ring in outers for lon, _ in ring]
        out.append({"id": f["properties"]["shapeID"], "bbox": (min(lats), max(lats), min(lons), max(lons)), "rings": outers})
    return out


def point_in_ring(lat, lon, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def assign(lat, lon, districts):
    for d in districts:
        b = d["bbox"]
        if b[0] <= lat <= b[1] and b[2] <= lon <= b[3] and any(point_in_ring(lat, lon, r) for r in d["rings"]):
            return d["id"]
    return None


def find_col(fieldnames, *needles):
    for name in fieldnames:
        low = name.lower()
        if any(n in low for n in needles):
            return name
    raise SystemExit(f"В CSV не найдена колонка по признакам {needles}; есть: {fieldnames}")


def normalize_date(value):
    value = value.strip()[:10]
    if "." in value:  # DD.MM.YYYY → ISO
        day, month, year = value.split(".")
        return f"{year}-{month}-{day}"
    return value  # уже YYYY-MM-DD


def load_dtp_counts(path, districts):
    """CSV ДТП → {(district_id, iso_date): count} только по зимним месяцам."""
    counts, skipped = {}, 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        date_col = find_col(reader.fieldnames, "date", "дата")
        lat_col = find_col(reader.fieldnames, "lat", "шир")
        lon_col = find_col(reader.fieldnames, "lon", "lng", "долг")
        for row in reader:
            try:
                day = normalize_date(row[date_col])
                month = int(day[5:7])
                if 4 <= month <= 10:
                    continue  # не зима
                district = assign(float(row[lat_col]), float(row[lon_col]), districts)
            except (ValueError, KeyError):
                skipped += 1
                continue
            if district:
                counts[(district, day)] = counts.get((district, day), 0) + 1
    print(f"ДТП зимних, привязанных к районам: {sum(counts.values())} (пропущено строк: {skipped})")
    return counts


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    import lightgbm as lgb
    import pandas as pd

    districts = load_district_polygons()
    dtp = load_dtp_counts(sys.argv[1], districts)
    if not dtp:
        sys.exit("Ни одного зимнего ДТП не привязалось — проверьте формат CSV.")

    booster = lgb.Booster(model_file=str(MODEL_PATH))
    prior = json.loads(METRICS_PATH.read_text(encoding="utf-8"))["prior"]
    df = add_doy(pd.read_csv(FEATURES_CSV))
    df["prior"] = df.district_id.map(prior).fillna(0)
    df["score"] = booster.predict(df[FEATURES].to_numpy())
    df["dtp"] = [dtp.get((d, day), 0) for d, day in zip(df.district_id, df.date)]

    total = int(df.dtp.sum())
    result = {"district_days": int(len(df)), "dtp_total": total}
    ranked = df.sort_values("score", ascending=False)
    for share in (0.1, 0.2):
        k = int(share * len(ranked))
        captured = int(ranked.head(k).dtp.sum())
        result[f"capture_top{int(share * 100)}"] = round(captured / max(1, total), 3)
        result[f"lift_top{int(share * 100)}"] = round((captured / max(1, k)) / (total / len(df)), 2)
    print(json.dumps(result, ensure_ascii=False, indent=1))

    OUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"→ {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
