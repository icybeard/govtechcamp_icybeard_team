#!/usr/bin/env python3
"""Генерация зимних данных в CSV (ОДИН РАЗ, нужен интернет).

Тянет Open-Meteo Archive (ERA5, без ключа) по 16 областям за сезоны 2020–2026
ОДНИМ запросом на сезон (все 16 координат сразу — быстро, ~10–20 сек), считает
индекс зимней опасности 0–100 + 4 под-индекса и пишет data/processed/winter_regions.csv.
На старте этот CSV пакетом сеет бэк (DataFileSeeder, module=winter-risk, без интернета) —
как у паводка со скорами: тяжёлая генерация делается один раз, дальше только быстрая загрузка.

Пороги с запасом (не упираются в 100). Снегонагрузка — по пиковому снежному покрову.
Устойчив к обрывам сети, продолжает с места остановки (пропускает готовые область-сезоны).

Только стандартная библиотека.
Использование:  python scripts/winter_fetch.py  [2020] [2026]
"""
import csv
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT_CSV = REPO / "data" / "processed" / "winter_regions.csv"

REGIONS = [
    ("KZ-PAV", 52.236, 76.372), ("KZ-ZHA", 44.164, 72.445), ("KZ-KUS", 51.444, 64.043),
    ("KZ-MAN", 43.883, 53.374), ("KZ-KAR", 48.655, 70.326), ("KZ-KZY", 45.075, 63.545),
    ("KZ-VOS", 48.622, 81.953), ("KZ-AKT", 48.247, 58.954), ("KZ-ATY", 47.626, 51.761),
    ("KZ-YUZ", 43.285, 68.471), ("KZ-AKM", 51.862, 69.806), ("KZ-ALM", 44.771, 78.155),
    ("KZ-SEV", 53.844, 69.999), ("KZ-ALA", 43.218, 76.953), ("KZ-ZAP", 49.848, 50.529),
    ("KZ-AST", 51.176, 71.504),
]
W = {"glaze": 0.30, "blizzard": 0.30, "snowload": 0.20, "cold": 0.20}
COLUMNS = ["iso", "season", "risk_score", "idx_glaze", "idx_blizzard", "idx_snowload", "idx_cold"]


def clamp01(x):
    return max(0.0, min(1.0, x))


def openmeteo_batch(regions, year):
    """Один запрос к архиву на ВСЕ переданные области за сезон. Возвращает список,
    выровненный с regions (Open-Meteo принимает координаты через запятую)."""
    lats = ",".join(str(la) for _, la, _ in regions)
    lons = ",".join(str(lo) for _, _, lo in regions)
    params = (
        f"latitude={lats}&longitude={lons}&start_date={year-1}-11-01&end_date={year}-03-31"
        "&daily=temperature_2m_min,temperature_2m_max,wind_speed_10m_max,snowfall_sum,rain_sum"
        "&hourly=snow_depth&wind_speed_unit=ms&timezone=UTC"
    )
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    last = None
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                payload = json.load(r)
            return payload if isinstance(payload, list) else [payload]
        except urllib.error.HTTPError as e:
            last = e
            time.sleep(min(60, 5 * (attempt + 1)))  # 429/5xx — подождать и повторить
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last = e  # сеть отвалилась/таймаут — ждём восстановления и пробуем снова
            print(f"    сеть недоступна, жду и повторяю… ({attempt+1})", flush=True)
            time.sleep(min(60, 8 * (attempt + 1)))
    raise SystemExit(f"Open-Meteo недоступен после повторов: {last}. Проверь интернет и запусти снова — продолжит с места остановки.")


def sub_indices(d):
    daily = d.get("daily", {})
    tmin = daily.get("temperature_2m_min", []) or []
    tmax = daily.get("temperature_2m_max", []) or []
    wmax = daily.get("wind_speed_10m_max", []) or []
    snow = daily.get("snowfall_sum", []) or []
    rain = daily.get("rain_sum", []) or []
    depth = [x for x in (d.get("hourly", {}).get("snow_depth", []) or []) if x is not None]

    glaze_days = freeze_thaw = blizzard_days = cold_days = 0
    tmin_season = 99.0
    for i in range(len(tmin)):
        lo = tmin[i] if tmin[i] is not None else 0.0
        hi = tmax[i] if tmax[i] is not None else 0.0
        w = wmax[i] if i < len(wmax) and wmax[i] is not None else 0.0
        sn = snow[i] if i < len(snow) and snow[i] is not None else 0.0
        rn = rain[i] if i < len(rain) and rain[i] is not None else 0.0
        if rn > 0.2 and hi <= 1:
            glaze_days += 1
        if lo < 0 and hi > 0:
            freeze_thaw += 1
        if w >= 11 and sn > 0:
            blizzard_days += 1
        if lo <= -25:
            cold_days += 1
        tmin_season = min(tmin_season, lo)
    snow_depth_max = max(depth) if depth else 0.0  # м

    return {
        "glaze": clamp01(0.7 * (glaze_days / 10) + 0.3 * (freeze_thaw / 60)),
        "blizzard": clamp01(blizzard_days / 20),
        "snowload": clamp01(snow_depth_max / 1.5),   # 1.5 м покрова — экстремум
        "cold": clamp01(0.5 * (cold_days / 40) + 0.5 * ((-25 - tmin_season) / 25)),
    }


def main():
    year_from = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    year_to = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Резюме: пропускаем уже готовые область-сезоны (append, без перезаписи)
    done = set()
    if OUT_CSV.exists():
        with open(OUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["iso"], str(row["season"])))
        if done:
            print(f"Продолжаю: уже готово {len(done)} записей, пропускаю их.", flush=True)

    new_file = not OUT_CSV.exists()
    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(COLUMNS)
        for year in range(year_from, year_to + 1):
            ys = str(year)
            missing = [r for r in REGIONS if (r[0], ys) not in done]
            if not missing:
                print(f"Сезон {year}: уже есть, пропускаю.", flush=True)
                continue
            print(f"Сезон {year} (Nov{year-1}–Mar{year}): один запрос на {len(missing)} обл…", flush=True)
            results = openmeteo_batch(missing, year)
            for (iso, la, lo), d in zip(missing, results):
                s = sub_indices(d)
                risk = round(100 * sum(W[k] * s[k] for k in W), 1)
                w.writerow([iso, year, risk,
                            round(100 * s["glaze"], 1), round(100 * s["blizzard"], 1),
                            round(100 * s["snowload"], 1), round(100 * s["cold"], 1)])
            f.flush()  # прогресс сохранён — при обрыве не потеряется
            print(f"  сезон {year}: +{len(missing)} обл.", flush=True)
            time.sleep(1)
    print(f"Готово → {OUT_CSV}. Дальше на старте его быстро подхватит winter_load.py.")


if __name__ == "__main__":
    main()
