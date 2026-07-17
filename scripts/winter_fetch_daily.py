#!/usr/bin/env python3
"""Дневные метео-фичи по районам (ADM2, 174) для обучения зимней ML-модели.

Для каждого района и каждого дня зимнего сезона (1 ноября — 31 марта) тянет из
Open-Meteo Archive (ERA5): t_min, t_max, макс. ветер и порывы, снегопад, дождь,
осадки — и приписывает району область (ADM1) по центроиду, чтобы join'иться
с разметкой по областям (scripts/winter_labels_storm_archive.py).

Производные признаки-прокси (считаются на лету):
  freezing_rain — дождь ≥ 0.5 мм при t_min < 0 (гололёдная ситуация);
  blizzard_like — снегопад ≥ 1 см при ветре ≥ 10 м/с (метелевая ситуация).

Выход: data/processed/winter_daily_features.csv
  season, date, district_id, district, region_iso, region,
  tmin, tmax, wmax, gusts, snowfall, rain, precip, freezing_rain, blizzard_like

Сырые ответы кэшируются в data/raw/winter_daily/ (resume при повторе).
Только стандартная библиотека. ~2–4 минуты на сезон (3 чанк-запроса).

Использование:  python3 scripts/winter_fetch_daily.py  [2021] [2026]
"""
import csv
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winter_fetch_districts import centroid  # noqa: E402 — тот же расчёт центроида

REPO = pathlib.Path(__file__).resolve().parent.parent
GEO_DISTRICTS = REPO / "frontend/public/geo/kz-districts.geojson"
GEO_REGIONS = REPO / "frontend/public/geo/kz-regions.geojson"
CACHE = REPO / "data/raw/winter_daily"
OUT = REPO / "data/processed/winter_daily_features.csv"
CHUNK = 60  # координат на запрос — как в winter_fetch_districts.py

DAILY_VARS = "temperature_2m_min,temperature_2m_max,wind_speed_10m_max,wind_gusts_10m_max,snowfall_sum,rain_sum,precipitation_sum"


def point_in_ring(lat, lon, ring):
    """Луч-тест (аналог isPointInRing в frontend/src/service/geo.js)."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def iter_rings(feature):
    geom = feature["geometry"]
    polygons = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for polygon in polygons:
        yield polygon[0]


def find_region(lat, lon, regions):
    for feature in regions:
        if any(point_in_ring(lat, lon, ring) for ring in iter_rings(feature)):
            return feature["properties"]
    # Прибрежные районы: bbox-центроид может попасть в Каспий — берём область
    # с ближайшей к точке границей (грубая метрика по вершинам полигона).
    def distance(feature):
        return min((v[1] - lat) ** 2 + (v[0] - lon) ** 2 for ring in iter_rings(feature) for v in ring)

    return min(regions, key=distance)["properties"]


def load_districts():
    """[{id, name, lat, lon, region_iso, region}] — район + его область по центроиду."""
    districts = json.loads(GEO_DISTRICTS.read_text(encoding="utf-8"))["features"]
    regions = json.loads(GEO_REGIONS.read_text(encoding="utf-8"))["features"]
    result = []
    for feature in districts:
        lat, lon = centroid(feature)
        region = find_region(lat, lon, regions) or {}
        result.append(
            {
                "id": feature["properties"]["shapeID"],
                "name": feature["properties"]["shapeName"],
                "lat": lat,
                "lon": lon,
                "region_iso": region.get("shapeISO", ""),
                "region": region.get("shapeName", ""),
            }
        )
    return result


def fetch_chunk(coords, year):
    lats = ",".join(f"{la:.3f}" for la, _ in coords)
    lons = ",".join(f"{lo:.3f}" for _, lo in coords)
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lats}&longitude={lons}&start_date={year - 1}-11-01&end_date={year}-03-31"
        f"&daily={DAILY_VARS}&wind_speed_unit=ms&timezone=UTC"
    )
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


def season_payloads(districts, year):
    """Данные сезона по всем районам: из кэша или с дозагрузкой чанков."""
    payloads = []
    for start in range(0, len(districts), CHUNK):
        cached = CACHE / f"{year}_{start}.json"
        if cached.exists():
            payloads.extend(json.loads(cached.read_text(encoding="utf-8")))
            continue
        chunk = [(d["lat"], d["lon"]) for d in districts[start : start + CHUNK]]
        print(f"  чанк {start}–{start + len(chunk) - 1}", flush=True)
        payload = fetch_chunk(chunk, year)
        cached.write_text(json.dumps(payload), encoding="utf-8")
        payloads.extend(payload)
        time.sleep(2)
    return payloads


def rows_for_season(districts, year):
    for district, payload in zip(districts, season_payloads(districts, year)):
        daily = payload.get("daily", {})
        series = {var: daily.get(var, []) or [] for var in DAILY_VARS.split(",")}
        for i, day in enumerate(daily.get("time", []) or []):
            def val(var):
                arr = series[var]
                return arr[i] if i < len(arr) and arr[i] is not None else 0.0

            tmin, rain = val("temperature_2m_min"), val("rain_sum")
            snowfall, wmax = val("snowfall_sum"), val("wind_speed_10m_max")
            yield {
                "season": year,
                "date": day,
                "district_id": district["id"],
                "district": district["name"],
                "region_iso": district["region_iso"],
                "region": district["region"],
                "tmin": tmin,
                "tmax": val("temperature_2m_max"),
                "wmax": wmax,
                "gusts": val("wind_gusts_10m_max"),
                "snowfall": snowfall,
                "rain": rain,
                "precip": val("precipitation_sum"),
                "freezing_rain": int(rain >= 0.5 and tmin < 0),
                "blizzard_like": int(snowfall >= 1 and wmax >= 10),
            }


def main():
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 2021
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    districts = load_districts()
    unmapped = [d["name"] for d in districts if not d["region_iso"]]
    print(f"районов: {len(districts)}, без области: {len(unmapped)}" + (f" ({', '.join(unmapped[:5])}…)" if unmapped else ""))

    count = 0
    fieldnames = ["season", "date", "district_id", "district", "region_iso", "region", "tmin", "tmax", "wmax", "gusts", "snowfall", "rain", "precip", "freezing_rain", "blizzard_like"]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for year in range(first, last + 1):
            print(f"сезон {year - 1}–{str(year)[2:]}", flush=True)
            for row in rows_for_season(districts, year):
                writer.writerow(row)
                count += 1
    print(f"готово: {count} строк район×день → {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
