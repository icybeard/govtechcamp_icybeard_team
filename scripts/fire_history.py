#!/usr/bin/env python3
"""Историческая частота очагов FIRMS по районам (июль 2021–2025) → JSON-приор.

Качает архивные очаги (VIIRS standard product, окна по 5 дней — ограничение API),
привязывает к районам ADM2 (ray casting, stdlib) и считает приор 0–100 по
log-шкале от числа очагов. Фронтенд смешивает его с live-метео-индексом.

Нужен FIRMS_MAP_KEY в .env. Один раз, ~30 запросов с паузами (2–3 минуты).
Использование:  python3 scripts/fire_history.py
"""
import csv
import io
import json
import math
import pathlib
import time
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
GEO = REPO / "frontend/public/geo/kz-districts.geojson"
OUT = REPO / "frontend/public/data/fire-history.json"
BBOX = "46,40,88,56"
YEARS = range(2021, 2026)
JULY_WINDOWS = ["07-01", "07-06", "07-11", "07-16", "07-21", "07-26"]  # 6×5 дней = 1–30 июля


def read_env_key():
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("FIRMS_MAP_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("FIRMS_MAP_KEY не найден в .env")


def load_districts():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    districts = []
    for f in geo["features"]:
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        outers = [poly[0] for poly in polys]  # внешних колец достаточно
        lats = [lat for ring in outers for _, lat in ring]
        lons = [lon for ring in outers for lon, _ in ring]
        districts.append({
            "id": f["properties"]["shapeID"],
            "bbox": (min(lats), max(lats), min(lons), max(lons)),
            "rings": outers,
        })
    return districts


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
        if not (b[0] <= lat <= b[1] and b[2] <= lon <= b[3]):
            continue
        if any(point_in_ring(lat, lon, ring) for ring in d["rings"]):
            return d["id"]
    return None


def main():
    key = read_env_key()
    districts = load_districts()
    counts = {d["id"]: 0 for d in districts}
    total = skipped = 0

    for year in YEARS:
        for start in JULY_WINDOWS:
            url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/"
                   f"VIIRS_SNPP_SP/{BBOX}/5/{year}-{start}")
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(url, timeout=120) as r:
                        text = r.read().decode()
                    break
                except Exception as e:  # 429/сеть — подождать
                    print(f"  повтор {attempt + 1}: {e}", flush=True)
                    time.sleep(15 * (attempt + 1))
            else:
                raise SystemExit("FIRMS недоступен после повторов")
            if not text.startswith("latitude"):
                print(f"  {year}-{start}: ответ не CSV ({text[:80]}) — пропускаю")
                continue
            rows = list(csv.DictReader(io.StringIO(text)))
            for row in rows:
                total += 1
                sid = assign(float(row["latitude"]), float(row["longitude"]), districts)
                if sid:
                    counts[sid] += 1
                else:
                    skipped += 1  # очаги соседних стран внутри bbox
            print(f"{year}-{start}: +{len(rows)} очагов", flush=True)
            time.sleep(2)

    max_count = max(counts.values()) or 1
    result = {
        sid: {"count": c, "prior": round(100 * math.log1p(c) / math.log1p(max_count), 1)}
        for sid, c in counts.items()
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    in_kz = total - skipped
    print(f"Готово: {total} очагов, в районах РК {in_kz}, максимум на район {max_count} → {OUT}")


if __name__ == "__main__":
    main()
