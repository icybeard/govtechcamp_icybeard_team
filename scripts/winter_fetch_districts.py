#!/usr/bin/env python3
"""Зимние индексы ПО РАЙОНАМ (ADM2, 174 шт.) → статический JSON для фронтенда.

Та же методика, что winter_fetch.py (переиспользует его sub_indices/веса), но:
- центроиды берутся из frontend/public/geo/kz-districts.geojson;
- результат — frontend/public/data/winter-districts.json (страница читает файл,
  БД не нужна: {"2026": {"<shapeID>": {"risk":41.2,"glaze":55,...}}, ...}).

Только стандартная библиотека. Один раз, ~2–4 минуты (21 запрос к архиву).
Использование:  python3 scripts/winter_fetch_districts.py  [2020] [2026]
"""
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winter_fetch import W, sub_indices  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
GEO = REPO / "frontend/public/geo/kz-districts.geojson"
OUT = REPO / "frontend/public/data/winter-districts.json"
CHUNK = 60  # координат на запрос: URL умеренный, лимиты архива щадим


def centroid(feature):
    lat_min, lat_max, lon_min, lon_max = 90.0, -90.0, 180.0, -180.0
    geom = feature["geometry"]
    rings = geom["coordinates"]
    if geom["type"] == "MultiPolygon":
        rings = [r for poly in rings for r in poly]
    for ring in rings:
        for lon, lat in ring:
            lat_min, lat_max = min(lat_min, lat), max(lat_max, lat)
            lon_min, lon_max = min(lon_min, lon), max(lon_max, lon)
    return (lat_min + lat_max) / 2, (lon_min + lon_max) / 2


def fetch_chunk(coords, year):
    lats = ",".join(f"{la:.3f}" for la, _ in coords)
    lons = ",".join(f"{lo:.3f}" for _, lo in coords)
    params = (
        f"latitude={lats}&longitude={lons}&start_date={year-1}-11-01&end_date={year}-03-31"
        "&daily=temperature_2m_min,temperature_2m_max,wind_speed_10m_max,snowfall_sum,rain_sum"
        "&hourly=snow_depth&wind_speed_unit=ms&timezone=UTC"
    )
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    last = None
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                payload = json.load(r)
            return payload if isinstance(payload, list) else [payload]
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError) as e:
            last = e
            print(f"    повтор ({attempt + 1}): {e}", flush=True)
            time.sleep(min(90, 10 * (attempt + 1)))
    raise SystemExit(f"Open-Meteo Archive недоступен: {last}")


def main():
    year_from = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    year_to = int(sys.argv[2]) if len(sys.argv) > 2 else 2026

    geo = json.loads(GEO.read_text(encoding="utf-8"))
    districts = [(f["properties"]["shapeID"], *centroid(f)) for f in geo["features"]]
    print(f"Районов: {len(districts)}")

    result = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for year in range(year_from, year_to + 1):
        ys = str(year)
        if ys in result and len(result[ys]) == len(districts):
            print(f"Сезон {year}: уже есть, пропускаю.")
            continue
        season = {}
        for i in range(0, len(districts), CHUNK):
            chunk = districts[i : i + CHUNK]
            data = fetch_chunk([(la, lo) for _, la, lo in chunk], year)
            for (sid, _, _), d in zip(chunk, data):
                s = sub_indices(d)
                season[sid] = {
                    "risk": round(100 * sum(W[k] * s[k] for k in W), 1),
                    "glaze": round(100 * s["glaze"], 1),
                    "blizzard": round(100 * s["blizzard"], 1),
                    "snowload": round(100 * s["snowload"], 1),
                    "cold": round(100 * s["cold"], 1),
                }
            print(f"  сезон {year}: {len(season)}/{len(districts)}", flush=True)
            time.sleep(2)
        result[ys] = season
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(f"Сезон {year} сохранён.", flush=True)
    print(f"Готово → {OUT}")


if __name__ == "__main__":
    main()
