#!/usr/bin/env python3
"""Baseline-скоринг паводкового риска (stdlib, прозрачная формула — не ML).

Нужен как временный источник скоров до разметки-2024 и как бенчмарк для модели.
Скор 0–100 из двух факторов:
  близость к реке      (вес 0.45): 1 - dist/20км, обрезка в [0,1]
  превышение над рекой (вес 0.55): 1 - elev_above/30м, обрезка в [0,1]; учитывается
                                   только если река ближе 20 км

Использование:
    python3 ml/i6-flood-risk/baseline_scores.py \
        data/processed/features_kz-sev.csv data/processed/scores_kz-sev.csv
"""
import csv
import json
import sys

W_PROXIMITY = 0.45
W_LOW_ABOVE = 0.55
RIVER_RADIUS_KM = 20.0
ABOVE_SCALE_M = 30.0


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_row(row: dict) -> tuple[float, list[dict]]:
    dist = float(row["dist_to_river_km"]) if row["dist_to_river_km"] else RIVER_RADIUS_KM
    above = float(row["elev_above_river_m"]) if row["elev_above_river_m"] else ABOVE_SCALE_M

    proximity = clamp01(1 - dist / RIVER_RADIUS_KM)
    low_above = clamp01(1 - above / ABOVE_SCALE_M) if dist < RIVER_RADIUS_KM else 0.0

    score = 100 * (W_PROXIMITY * proximity + W_LOW_ABOVE * low_above)
    factors = [
        {"name": f"Река в {dist:.1f} км (baseline)", "impact": round(W_PROXIMITY * proximity, 2)},
        {"name": f"Превышение над рекой {above:.0f} м (baseline)", "impact": round(W_LOW_ABOVE * low_above, 2)},
    ]
    factors = [f for f in factors if f["impact"] > 0]
    return round(score, 1), factors


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    input_csv, output_csv = sys.argv[1], sys.argv[2]

    with open(input_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "lat", "lon", "score", "factors_json"])
        for row in rows:
            score, factors = score_row(row)
            writer.writerow([row["name"], row["lat"], row["lon"], score, json.dumps(factors, ensure_ascii=False)])

    scores = [score_row(r)[0] for r in rows]
    high = sum(1 for s in scores if s >= 60)
    print(f"{len(rows)} НП, скор ≥60: {high}, максимум: {max(scores):.0f} → {output_csv}")


if __name__ == "__main__":
    main()
