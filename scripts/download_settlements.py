#!/usr/bin/env python3
"""Скачивает населённые пункты региона из OSM (Overpass API) в CSV.

Только стандартная библиотека — никаких pip-зависимостей.

Использование:
    python3 scripts/download_settlements.py KZ-SEV data/raw/settlements_kz-sev.csv
"""
import csv
import json
import sys
import urllib.parse
import urllib.request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Приложение использует ISO-коды границ 2017 г. (geoBoundaries, shapeISO в kz-regions.geojson),
# а OSM — новые числовые коды после реформы-2022. Скрипт принимает код приложения.
# Внимание: для KZ-ALM/KZ-KAR/KZ-VOS новые границы уже, чем старые (отделены Жетысу/Улытау/Абай) —
# для полного покрытия старой границы качайте и новую область тоже (KZ-33/KZ-62/KZ-10).
OSM_ISO_MAP = {
    "KZ-AKM": "KZ-11", "KZ-AKT": "KZ-15", "KZ-ALA": "KZ-75", "KZ-ALM": "KZ-19",
    "KZ-AST": "KZ-71", "KZ-ATY": "KZ-23", "KZ-KAR": "KZ-35", "KZ-KUS": "KZ-39",
    "KZ-KZY": "KZ-43", "KZ-MAN": "KZ-47", "KZ-PAV": "KZ-55", "KZ-SEV": "KZ-59",
    "KZ-VOS": "KZ-63", "KZ-YUZ": "KZ-61", "KZ-ZAP": "KZ-27", "KZ-ZHA": "KZ-31",
}

QUERY_TEMPLATE = """
[out:json][timeout:120];
area["ISO3166-2"="{iso}"]->.region;
node[place~"^(city|town|village|hamlet)$"](area.region);
out body;
"""


def fetch(iso: str) -> list[dict]:
    osm_iso = OSM_ISO_MAP.get(iso, iso)
    query = QUERY_TEMPLATE.format(iso=osm_iso)
    request = urllib.request.Request(
        OVERPASS_URL,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": "govtechcamp-icybeard/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.load(response)

    rows = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name:ru") or tags.get("name")
        if not name:
            continue
        population = tags.get("population")
        rows.append(
            {
                "name": name,
                "lat": element["lat"],
                "lon": element["lon"],
                "population": int(population) if population and population.isdigit() else "",
                "place": tags.get("place", ""),
            }
        )
    return rows


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    iso, output_path = sys.argv[1], sys.argv[2]

    rows = fetch(iso)
    if not rows:
        sys.exit(f"Overpass не вернул НП для {iso} — проверьте ISO-код (пример: KZ-SEV)")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "lat", "lon", "population", "place"])
        writer.writeheader()
        writer.writerows(rows)

    with_population = sum(1 for r in rows if r["population"] != "")
    print(f"{iso}: {len(rows)} НП сохранено в {output_path} (с населением: {with_population})")


if __name__ == "__main__":
    main()
