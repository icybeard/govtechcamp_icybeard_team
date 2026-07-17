#!/usr/bin/env python3
"""Разметка для зимнего ML: архив штормовых предупреждений Казгидромета.

Источник: https://www.kazhydromet.kz/ru/storm_archive. Данные отдаёт внутренний
API (подсмотрен в DevTools): POST https://www.kazhydromet.kz/ajax_storm.php
с формой  date=DD.MM.YYYY&region=&lang=ru&page=N&isInArchive=1 ; ответ — JSON
{items: [{name, opis, stormDate, myRegions, isDangerous, ...}], pages: <html>}.

Одно предупреждение может покрывать несколько областей (myRegions через
запятую) — строка CSV пишется на каждую область. Тип явления определяется
по ключевым словам текста (opis). Дата строки = дате выпуска предупреждения.

Выход: data/raw/winter_storm_warnings.csv
  date, region_iso, region, blizzard, ice, frost, wind, snow, dangerous, text

Сырые ответы кэшируются в data/raw/storm_archive/{date}.json (resume при
повторном запуске). Только стандартная библиотека, ~0.3 с пауза между днями.

Использование:  python3 scripts/winter_labels_storm_archive.py [2021] [2026]
  (годы — сезоны с ноября year-1 по март year; --url меняет адрес эндпоинта)
"""
import argparse
import csv
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

REPO = pathlib.Path(__file__).resolve().parent.parent
CACHE = REPO / "data/raw/storm_archive"
OUT = REPO / "data/raw/winter_storm_warnings.csv"
AJAX_URL = "https://www.kazhydromet.kz/ajax_storm.php"

# Регионы архива (новое деление, 19) → ISO старого деления (16, как в
# frontend/public/geo/kz-regions.geojson). Новые области 2022 года относим
# к «родительским»: Абай→ВКО, Жетісу→Алматинская, Ұлытау→Карагандинская.
REGION_ISO = {
    "астана": "KZ-AST",
    "алматы": "KZ-ALA",
    "абай": "KZ-VOS",
    "алматинская": "KZ-ALM",
    "акмолинская": "KZ-AKM",
    "актюбинская": "KZ-AKT",
    "атырауская": "KZ-ATY",
    "восточно-казахстанская": "KZ-VOS",
    "жамбылская": "KZ-ZHA",
    "жетісу": "KZ-ALM",
    "жетысу": "KZ-ALM",
    "западно-казахстанская": "KZ-ZAP",
    "карагандинская": "KZ-KAR",
    "костанайская": "KZ-KUS",
    "кызылординская": "KZ-KZY",
    "мангыстауская": "KZ-MAN",
    "павлодарская": "KZ-PAV",
    "северо-казахстанская": "KZ-SEV",
    "туркестанская": "KZ-YUZ",
    "ұлытау": "KZ-KAR",
    "улытау": "KZ-KAR",
}

# Ключевые слова явлений → колонки-флаги (порядок = порядок колонок в CSV)
PHENOMENA = [
    ("blizzard", ("метел", "буран", "позем")),
    ("ice", ("гололед", "гололёд")),
    ("frost", ("мороз",)),
    ("wind", ("ветер",)),
    ("snow", ("снег",)),
]

TAG_RE = re.compile(r"<[^>]+>")
PAGE_RE = re.compile(r"goPage\((\d+)\)")


def http_post(url, form, timeout=60, attempts=6):
    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": "icybeard-govtech/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    })
    last = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"{url}: {last}")


def fetch_day(url, day):
    """Все предупреждения за дату (с обходом пагинации). day — date."""
    form = {"date": day.strftime("%d.%m.%Y"), "region": "", "lang": "ru", "page": 1, "isInArchive": 1}
    payload = http_post(url, form)
    items = list(payload.get("items") or [])
    pages = max((int(n) for n in PAGE_RE.findall(payload.get("pages") or "")), default=1)
    for page in range(2, pages + 1):
        extra = http_post(url, {**form, "page": page})
        items.extend(extra.get("items") or [])
    return items


def region_to_iso(name):
    low = name.lower()
    for key, iso in REGION_ISO.items():
        if key in low:
            return iso
    return ""


def classify(text):
    low = text.lower()
    return {flag: int(any(k in low for k in keys)) for flag, keys in PHENOMENA}


def extract_rows(items, day_iso):
    """Предупреждение × область → строки CSV (myRegions перечисляет области)."""
    rows = []
    for item in items:
        text = re.sub(r"\s+", " ", TAG_RE.sub(" ", item.get("opis") or "")).strip()
        if not text:
            continue
        flags = classify(text)
        for region in (item.get("myRegions") or "").split(","):
            region = region.strip()
            if not region:
                continue
            rows.append({
                "date": day_iso,
                "region_iso": region_to_iso(region),
                "region": region,
                **flags,
                "dangerous": int(item.get("isDangerous") in (1, "1")),
                "text": text,
            })
    return rows


def season_dates(year):
    """Зима «year»: 1 ноября (year-1) — 31 марта (year)."""
    day = date(year - 1, 11, 1)
    while day <= date(year, 3, 31):
        yield day
        day += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(description="Архив штормовых предупреждений Казгидромета → CSV-разметка")
    parser.add_argument("first", nargs="?", type=int, default=2021, help="первый сезон (год марта)")
    parser.add_argument("last", nargs="?", type=int, default=2026, help="последний сезон (год марта)")
    parser.add_argument("--url", default=AJAX_URL, help="адрес эндпоинта (по умолчанию ajax_storm.php)")
    opts = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for year in range(opts.first, opts.last + 1):
        print(f"сезон {year - 1}–{str(year)[2:]}", flush=True)
        for day in season_dates(year):
            day_iso = day.isoformat()
            cached = CACHE / f"{day_iso}.json"
            if cached.exists():
                items = json.loads(cached.read_text(encoding="utf-8"))
            else:
                items = fetch_day(opts.url, day)
                cached.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
                time.sleep(0.3)  # бережём сайт
        rows_before = len(rows)
        for day in season_dates(year):
            day_iso = day.isoformat()
            items = json.loads((CACHE / f"{day_iso}.json").read_text(encoding="utf-8"))
            rows.extend(extract_rows(items, day_iso))
        print(f"  предупреждений (строк область×день): {len(rows) - rows_before}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    flags = [flag for flag, _ in PHENOMENA]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "region_iso", "region", *flags, "dangerous", "text"])
        writer.writeheader()
        writer.writerows(rows)
    unmapped = sum(1 for r in rows if not r["region_iso"])
    print(f"готово: {len(rows)} строк → {OUT.relative_to(REPO)}" + (f" (без ISO: {unmapped} — проверьте имена регионов)" if unmapped else ""))


if __name__ == "__main__":
    main()
