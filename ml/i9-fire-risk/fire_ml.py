#!/usr/bin/env python3
"""Дневная ML-модель пожарного риска по районам (LightGBM, честный сплит по годам).

Подкоманды:
  fetch    — скачать архив очагов FIRMS (апр–окт 2021–2025, окна по 5 дней, кэш+resume)
             и дневную погоду Open-Meteo Archive по 174 районам (кэш по годам)
  train    — собрать датасет район×день, обучить LightGBM (train 2021–2024, test 2025),
             сравнить с композитным baseline, сохранить модель и metrics.json
  today    — прогноз на сегодня: погода Open-Meteo forecast → скор 0–100 на район
             → frontend/public/data/fire-ml-today.json (режим «ML-прогноз» на карте)

Запуск (venv): .venv/bin/python ml/i9-fire-risk/fire_ml.py fetch|train|today
"""
import csv
import io
import json
import math
import pathlib
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
GEO = REPO / "frontend/public/geo/kz-districts.geojson"
FIRE_DIR = REPO / "data/raw/fire_arch"
WEATHER_DIR = REPO / "data/raw"
MODEL_PATH = REPO / "data/processed/fire_lgbm.txt"
METRICS_PATH = REPO / "ml/i9-fire-risk/metrics.json"
TODAY_JSON = REPO / "frontend/public/data/fire-ml-today.json"

BBOX = "46,40,88,56"
YEARS = list(range(2021, 2026))
SEASON = (4, 10)  # апрель–октябрь
FEATURES = ["tmax", "wmax", "precip", "dry_streak", "doy_sin", "doy_cos", "prior"]


# ---------- общее ----------

def read_env_key():
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("FIRMS_MAP_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("FIRMS_MAP_KEY не найден в .env")


def http_get(url, timeout=180, attempts=6):
    last = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode()
        except Exception as e:
            last = e
            time.sleep(min(60, 8 * (attempt + 1)))
    raise SystemExit(f"HTTP не удалось: {last}")


def load_districts():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    out = []
    for f in geo["features"]:
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        outers = [poly[0] for poly in polys]
        lats = [lat for ring in outers for _, lat in ring]
        lons = [lon for ring in outers for lon, _ in ring]
        out.append({
            "id": f["properties"]["shapeID"],
            "lat": (min(lats) + max(lats)) / 2,
            "lon": (min(lons) + max(lons)) / 2,
            "bbox": (min(lats), max(lats), min(lons), max(lons)),
            "rings": outers,
        })
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


def season_windows(year):
    d = date(year, SEASON[0], 1)
    end = date(year, SEASON[1], 31)
    while d <= end:
        yield d
        d += timedelta(days=5)


# ---------- fetch ----------

def cmd_fetch():
    key = read_env_key()
    FIRE_DIR.mkdir(parents=True, exist_ok=True)

    for year in YEARS:
        for start in season_windows(year):
            cache = FIRE_DIR / f"{start.isoformat()}.csv"
            if cache.exists():
                continue
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_SP/{BBOX}/5/{start.isoformat()}"
            text = http_get(url, timeout=120)
            if not text.startswith("latitude"):
                print(f"{start}: не CSV ({text[:60]}) — пропуск")
                continue
            cache.write_text(text, encoding="utf-8")
            print(f"{start}: {max(0, len(text.splitlines()) - 1)} очагов", flush=True)
            time.sleep(1.5)

    districts = load_districts()
    for year in YEARS:
        cache = WEATHER_DIR / f"fire_weather_{year}.json"
        if cache.exists():
            continue
        lats = ",".join(f"{d['lat']:.3f}" for d in districts)
        lons = ",".join(f"{d['lon']:.3f}" for d in districts)
        url = ("https://archive-api.open-meteo.com/v1/archive?"
               f"latitude={lats}&longitude={lons}"
               f"&start_date={year}-{SEASON[0]:02d}-01&end_date={year}-{SEASON[1]:02d}-31"
               "&daily=temperature_2m_max,wind_speed_10m_max,precipitation_sum"
               "&wind_speed_unit=ms&timezone=UTC")
        cache.write_text(http_get(url), encoding="utf-8")
        print(f"погода {year}: ok", flush=True)
        time.sleep(2)
    print("fetch: готово")


# ---------- датасет ----------

def build_rows():
    districts = load_districts()
    ids = [d["id"] for d in districts]

    # очаги: (district, date) -> count
    fire_counts = {}
    for f in sorted(FIRE_DIR.glob("*.csv")):
        for row in csv.DictReader(io.StringIO(f.read_text(encoding="utf-8"))):
            sid = assign(float(row["latitude"]), float(row["longitude"]), districts)
            if sid:
                key = (sid, row["acq_date"])
                fire_counts[key] = fire_counts.get(key, 0) + 1

    rows = []
    for year in YEARS:
        payload = json.loads((WEATHER_DIR / f"fire_weather_{year}.json").read_text(encoding="utf-8"))
        payload = payload if isinstance(payload, list) else [payload]
        for d, w in zip(districts, payload):
            days = w["daily"]["time"]
            tmax = w["daily"]["temperature_2m_max"]
            wmax = w["daily"]["wind_speed_10m_max"]
            precip = w["daily"]["precipitation_sum"]
            dry = 0
            for i, day in enumerate(days):
                p = precip[i] or 0.0
                dry = 0 if p >= 1 else dry + 1
                doy = datetime.strptime(day, "%Y-%m-%d").timetuple().tm_yday
                rows.append({
                    "district": d["id"], "date": day, "year": year,
                    "tmax": tmax[i], "wmax": wmax[i], "precip": p, "dry_streak": min(dry, 30),
                    "doy_sin": math.sin(2 * math.pi * doy / 365), "doy_cos": math.cos(2 * math.pi * doy / 365),
                    "fires": fire_counts.get((d["id"], day), 0),
                })
    return rows, ids


def cmd_train():
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    from sklearn.metrics import average_precision_score, roc_auc_score

    rows, _ = build_rows()
    df = pd.DataFrame(rows)
    df["target"] = (df.fires > 0).astype(int)

    # приор района — ТОЛЬКО по train-годам (без утечки в тест)
    train_mask = df.year <= 2024
    prior_counts = df[train_mask].groupby("district").fires.sum()
    prior = (np.log1p(prior_counts) / np.log1p(prior_counts.max()) * 100).to_dict()
    df["prior"] = df.district.map(prior).fillna(0)

    train, test = df[train_mask], df[~train_mask]
    print(f"train: {len(train)} строк ({train.target.mean():.3%} позитивов), test-2025: {len(test)} ({test.target.mean():.3%})")

    model = lgb.LGBMClassifier(
        n_estimators=400, learning_rate=0.05, num_leaves=31,
        class_weight="balanced", random_state=42, verbose=-1
    )
    model.fit(train[FEATURES], train.target)
    proba = model.predict_proba(test[FEATURES])[:, 1]

    # baseline — наш продуктовый композит на тех же строках (без влажности — её нет в daily)
    weather_proxy = (
        25 * (test.tmax / 35).clip(0, 1) + 20 * (test.wmax * 3.6 / 40).clip(0, 1) + 20 * (test.dry_streak / 7).clip(0, 1)
    ) / 65 * 100
    baseline = 0.5 * weather_proxy + 0.5 * test.prior

    k = int(0.2 * len(test))
    def capture(scores):
        idx = np.argsort(-scores)[:k]
        return test.target.values[idx].sum() / max(1, test.target.sum())

    metrics = {
        "rows_train": int(len(train)), "rows_test": int(len(test)),
        "positives_test": int(test.target.sum()),
        "model_auc": round(float(roc_auc_score(test.target, proba)), 3),
        "baseline_auc": round(float(roc_auc_score(test.target, baseline)), 3),
        "model_ap": round(float(average_precision_score(test.target, proba)), 3),
        "baseline_ap": round(float(average_precision_score(test.target, baseline)), 3),
        "model_capture_top20": round(float(capture(proba)), 3),
        "baseline_capture_top20": round(float(capture(baseline.values)), 3),
        "split": "train 2021-2024, test 2025 (apr-oct, district-day)",
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=1))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(MODEL_PATH))
    # приор сохраняем рядом с метриками — нужен для today-прогноза
    METRICS_PATH.write_text(json.dumps({**metrics, "prior": prior}, ensure_ascii=False), encoding="utf-8")
    print(f"Модель → {MODEL_PATH}, метрики → {METRICS_PATH}")


def cmd_today():
    import lightgbm as lgb
    import numpy as np

    booster = lgb.Booster(model_file=str(MODEL_PATH))
    prior = json.loads(METRICS_PATH.read_text(encoding="utf-8"))["prior"]
    districts = load_districts()

    payload = []
    for i in range(0, len(districts), 60):  # батчи + паузы: не упираться в минутный лимит
        chunk = districts[i : i + 60]
        lats = ",".join(f"{d['lat']:.3f}" for d in chunk)
        lons = ",".join(f"{d['lon']:.3f}" for d in chunk)
        url = ("https://api.open-meteo.com/v1/forecast?"
               f"latitude={lats}&longitude={lons}"
               "&daily=temperature_2m_max,wind_speed_10m_max,precipitation_sum"
               "&past_days=7&forecast_days=1&wind_speed_unit=ms&timezone=UTC")
        part = json.loads(http_get(url, attempts=10))
        payload.extend(part if isinstance(part, list) else [part])
        time.sleep(20)

    doy = datetime.now(timezone.utc).timetuple().tm_yday
    feats = []
    for d, w in zip(districts, payload):
        precip = [p or 0.0 for p in w["daily"]["precipitation_sum"]]
        dry = 0
        for p in precip[:-1]:  # прошлые 7 дней
            dry = 0 if p >= 1 else dry + 1
        feats.append([
            w["daily"]["temperature_2m_max"][-1], w["daily"]["wind_speed_10m_max"][-1], precip[-1],
            min(dry, 30), math.sin(2 * math.pi * doy / 365), math.cos(2 * math.pi * doy / 365),
            prior.get(d["id"], 0),
        ])
    proba = booster.predict(np.array(feats))
    values = {d["id"]: round(float(p) * 100) for d, p in zip(districts, proba)}
    TODAY_JSON.write_text(json.dumps({
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "values": values,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"Прогноз на сегодня (макс {max(values.values())}) → {TODAY_JSON}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"fetch": cmd_fetch, "train": cmd_train, "today": cmd_today}.get(cmd, lambda: sys.exit(__doc__))()
