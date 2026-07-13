#!/usr/bin/env python3
"""Загружает CSV с населёнными пунктами в API (POST /api/settlements/import).

Логинится суперпользователем из .env (SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD).
Только стандартная библиотека.

Использование:
    python3 scripts/load_settlements.py KZ-SEV data/raw/settlements_kz-sev.csv [http://localhost:5080]
"""
import csv
import json
import pathlib
import sys
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


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


def post_json(url: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> None:
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    iso, csv_path = sys.argv[1], sys.argv[2]
    base_url = (sys.argv[3] if len(sys.argv) == 4 else "http://localhost:5080").rstrip("/")

    env = read_env()
    email = env.get("SEED_ADMIN_EMAIL", "admin@icybeard.local")
    password = env.get("SEED_ADMIN_PASSWORD")
    if not password:
        sys.exit("SEED_ADMIN_PASSWORD не найден в .env (cp .env.example .env)")

    settlements = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            settlements.append(
                {
                    "name": row["name"],
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "population": int(row["population"]) if row.get("population") else None,
                    "katoCode": None,
                }
            )
    if not settlements:
        sys.exit(f"{csv_path}: пусто")

    auth = post_json(f"{base_url}/api/auth/login", {"email": email, "password": password})
    result = post_json(
        f"{base_url}/api/settlements/import",
        {"regionIso": iso, "settlements": settlements},
        token=auth["token"],
    )
    print(f"{iso}: создано {result['created']}, обновлено {result['updated']} (из {len(settlements)})")


if __name__ == "__main__":
    main()
