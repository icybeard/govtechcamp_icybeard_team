#!/usr/bin/env python3
"""Считает признаки рельефа/гидрографии для НП региона (только stdlib).

Источники: реки — OSM Overpass (waterway=river|canal), высоты — Open-Meteo
Elevation API (Copernicus DEM GLO-90 под капотом, батчи по 100 точек).

Признаки на НП:
  elevation_m        — высота НП
  dist_to_river_km   — расстояние до ближайшей реки
  elev_above_river_m — превышение над ближайшей точкой реки (главный фактор риска)

Использование:
    python3 scripts/compute_terrain_features.py KZ-SEV \
        data/raw/settlements_kz-sev.csv data/processed/features_kz-sev.csv
"""
import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
USER_AGENT = "govtechcamp-icybeard/1.0"

# см. download_settlements.py — маппинг кодов приложения на новые OSM-коды
OSM_ISO_MAP = {
    "KZ-AKM": "KZ-11", "KZ-AKT": "KZ-15", "KZ-ALA": "KZ-75", "KZ-ALM": "KZ-19",
    "KZ-AST": "KZ-71", "KZ-ATY": "KZ-23", "KZ-KAR": "KZ-35", "KZ-KUS": "KZ-39",
    "KZ-KZY": "KZ-43", "KZ-MAN": "KZ-47", "KZ-PAV": "KZ-55", "KZ-SEV": "KZ-59",
    "KZ-VOS": "KZ-63", "KZ-YUZ": "KZ-61", "KZ-ZAP": "KZ-27", "KZ-ZHA": "KZ-31",
}

RIVERS_QUERY = """
[out:json][timeout:180];
area["ISO3166-2"="{iso}"]->.region;
way[waterway="river"](area.region);
out geom;
"""


def fetch_rivers(iso: str) -> list[tuple[float, float]]:
    query = RIVERS_QUERY.format(iso=OSM_ISO_MAP.get(iso, iso))
    payload = None
    last_error = None
    for url in OVERPASS_URLS:
        for attempt in range(2):
            try:
                request = urllib.request.Request(
                    url,
                    data=urllib.parse.urlencode({"data": query}).encode(),
                    headers={"User-Agent": USER_AGENT},
                )
                with urllib.request.urlopen(request, timeout=300) as response:
                    payload = json.load(response)
                break
            except Exception as error:  # 504/429 у публичных зеркал — обычное дело
                last_error = error
                print(f"  {url}: {error} — пробую дальше…")
                time.sleep(5)
        if payload is not None:
            break
    if payload is None:
        raise SystemExit(f"Все зеркала Overpass недоступны: {last_error}")

    points = []
    for way in payload.get("elements", []):
        geometry = way.get("geometry") or []
        # каждый ~3-й узел достаточен для поиска ближайшей точки
        points.extend((node["lat"], node["lon"]) for node in geometry[::3])
    return points


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_grid(points: list[tuple[float, float]], cell: float = 0.25) -> dict:
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for lat, lon in points:
        grid.setdefault((int(lat / cell), int(lon / cell)), []).append((lat, lon))
    return grid


def nearest_river_point(lat: float, lon: float, grid: dict, cell: float = 0.25):
    """Ближайшая точка реки через поиск по расширяющимся кольцам сетки."""
    ci, cj = int(lat / cell), int(lon / cell)
    for radius in range(0, 40):
        candidates = []
        for i in range(ci - radius, ci + radius + 1):
            for j in range(cj - radius, cj + radius + 1):
                if max(abs(i - ci), abs(j - cj)) == radius:
                    candidates.extend(grid.get((i, j), []))
        if candidates:
            best = min(candidates, key=lambda p: haversine_km(lat, lon, p[0], p[1]))
            # соседнее кольцо может содержать чуть более близкую точку — добираем его
            more = []
            for i in range(ci - radius - 1, ci + radius + 2):
                for j in range(cj - radius - 1, cj + radius + 2):
                    if max(abs(i - ci), abs(j - cj)) == radius + 1:
                        more.extend(grid.get((i, j), []))
            if more:
                best2 = min(more, key=lambda p: haversine_km(lat, lon, p[0], p[1]))
                if haversine_km(lat, lon, *best2) < haversine_km(lat, lon, *best):
                    best = best2
            return best
    return None


def fetch_elevations(coords: list[tuple[float, float]]) -> list[float]:
    result = []
    for start in range(0, len(coords), 50):
        batch = coords[start : start + 50]
        params = urllib.parse.urlencode(
            {
                "latitude": ",".join(f"{lat:.5f}" for lat, _ in batch),
                "longitude": ",".join(f"{lon:.5f}" for _, lon in batch),
            }
        )
        request = urllib.request.Request(f"{ELEVATION_URL}?{params}", headers={"User-Agent": USER_AGENT})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    result.extend(json.load(response)["elevation"])
                break
            except urllib.error.HTTPError as error:
                if error.code == 429 and attempt < 5:  # rate limit — ждём и повторяем
                    time.sleep(2 ** (attempt + 1))
                else:
                    raise
        time.sleep(1)  # бережём бесплатный API
    return result


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    iso, input_csv, output_csv = sys.argv[1:4]

    with open(input_csv, encoding="utf-8") as f:
        settlements = list(csv.DictReader(f))
    print(f"НП: {len(settlements)}")

    river_points = fetch_rivers(iso)
    if not river_points:
        sys.exit(f"OSM не вернул рек для {iso}")
    print(f"Точек рек: {len(river_points)}")
    grid = build_grid(river_points)

    nearest = []
    for row in settlements:
        point = nearest_river_point(float(row["lat"]), float(row["lon"]), grid)
        nearest.append(point)

    settlement_coords = [(float(r["lat"]), float(r["lon"])) for r in settlements]
    river_coords = [p if p else (0.0, 0.0) for p in nearest]
    print("Запрашиваю высоты (Open-Meteo / Copernicus DEM)…")
    settlement_elev = fetch_elevations(settlement_coords)
    river_elev = fetch_elevations(river_coords)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "lat", "lon", "population", "elevation_m", "dist_to_river_km", "elev_above_river_m"])
        for row, point, elev, r_elev in zip(settlements, nearest, settlement_elev, river_elev):
            dist = haversine_km(float(row["lat"]), float(row["lon"]), *point) if point else ""
            above = round(elev - r_elev, 1) if point else ""
            writer.writerow(
                [row["name"], row["lat"], row["lon"], row["population"], elev, round(dist, 2) if dist != "" else "", above]
            )
    print(f"Признаки сохранены: {output_csv}")


if __name__ == "__main__":
    main()
