#!/usr/bin/env python3
"""Загружает скоры НП (с факторами) в API — PUT /api/settlements/metrics.

Матчит строки CSV с НП в БД по имени; тёзки различаются по ближайшим координатам.
Логин суперпользователем из .env. Только стандартная библиотека.

Использование:
    python3 scripts/load_scores.py KZ-SEV data/processed/scores_kz-sev.csv [http://localhost:5080] [--period YYYY]

--period — срез сезона (SettlementMetric.Period); без него пишется в '' (актуальные скоры, к ним привязаны меры).
"""
import csv
import json
import pathlib
import sys
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE = "flood-risk"
METRIC_KEY = "risk_score"


def read_env() -> dict:
    env = {}
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip("\"'")
    return env


def request_json(method: str, url: str, payload=None, token=None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def main() -> None:
    args = sys.argv[1:]
    period = None
    if "--period" in args:
        period = args[args.index("--period") + 1]
        del args[args.index("--period") : args.index("--period") + 2]
    if len(args) not in (2, 3):
        sys.exit(__doc__)
    iso, csv_path = args[0], args[1]
    base_url = (args[2] if len(args) == 3 else "http://localhost:5080").rstrip("/")

    env = read_env()
    auth = request_json(
        "POST", f"{base_url}/api/auth/login",
        {"email": env.get("SEED_ADMIN_EMAIL", "admin@icybeard.local"), "password": env["SEED_ADMIN_PASSWORD"]},
    )
    token = auth["token"]

    settlements = request_json("GET", f"{base_url}/api/settlements/?region={iso}", token=token)
    by_name: dict[str, list[dict]] = {}
    for s in settlements:
        by_name.setdefault(s["name"], []).append(s)

    values = {}
    unmatched = 0
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            candidates = by_name.get(row["name"])
            if not candidates:
                unmatched += 1
                continue
            lat, lon = float(row["lat"]), float(row["lon"])
            best = min(candidates, key=lambda s: (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2)
            factors = json.loads(row["factors_json"]) if row.get("factors_json") else None
            values[str(best["id"])] = {"value": float(row["score"]), "factors": factors}

    if not values:
        sys.exit("Ни одна строка не сматчилась с НП в БД — сначала load_settlements.py")

    result = request_json(
        "PUT", f"{base_url}/api/settlements/metrics",
        {"module": MODULE, "metricKey": METRIC_KEY, "period": period, "values": values},
        token=token,
    )
    suffix = f" (period={period})" if period else ""
    print(f"Загружено скоров: {result['updated']}{suffix}, не сматчилось по имени: {unmatched}")


if __name__ == "__main__":
    main()
