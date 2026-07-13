#!/usr/bin/env python3
"""Обучение модели паводкового риска (LightGBM + встроенный TreeSHAP).

Вход:
  features.csv — из scripts/compute_terrain_features.py (+ ERA5-признаки)
  labels.csv   — name,flooded (1/0 по паводку-2024; методика — docs/data/flood-labels-methodology.md)
Выход:
  scores.csv   — name,lat,lon,score,factors_json (совместим со scripts/load_scores.py)

Использование:
    .venv/bin/python ml/i6-flood-risk/train.py \
        data/processed/features_kz-sev.csv data/raw/labels_2024.csv data/processed/scores_ml_kz-sev.csv
"""
import json
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

# Минимум позитивов: ниже 15 метрики теряют смысл даже как ориентир.
MIN_POSITIVES = 15

FEATURES = [
    "elevation_m", "dist_to_river_km", "elev_above_river_m", "population",
    "swe_mar2024_mm", "swe_mar_pct_norm", "precip_novmar_mm", "precip_novmar_pct_norm",
]
FACTOR_LABELS = {
    "elevation_m": "Высота {v:.0f} м",
    "dist_to_river_km": "Река в {v:.1f} км",
    "elev_above_river_m": "Превышение над рекой {v:.0f} м",
    "population": "Население {v:.0f}",
    "swe_mar2024_mm": "Снегозапас {v:.0f} мм",
    "swe_mar_pct_norm": "Снегозапас {v:.0f}% нормы",
    "precip_novmar_mm": "Осадки Nov–Mar {v:.0f} мм",
    "precip_novmar_pct_norm": "Осадки {v:.0f}% нормы",
}


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    features_csv, labels_csv, output_csv = sys.argv[1:4]

    df = pd.read_csv(features_csv)
    df = df.drop_duplicates(subset="name", keep="first")
    labels = pd.read_csv(labels_csv)
    df = df.merge(labels, on="name", how="inner")
    positives = int(df.flooded.sum())
    print(f"НП с разметкой: {len(df)}, затоплено: {positives}")
    if positives < MIN_POSITIVES:
        sys.exit(f"Позитивов меньше {MIN_POSITIVES} — модель не обучить, используйте baseline")

    X = df[FEATURES].fillna(df[FEATURES].median())
    y = df["flooded"]

    model = lgb.LGBMClassifier(
        n_estimators=200, learning_rate=0.05, num_leaves=7, min_child_samples=5,
        class_weight="balanced", random_state=42, verbose=-1
    )

    # Честная оценка: out-of-fold предсказания (немного позитивов → метрики шумные,
    # указываем это в ограничениях).
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    print(f"ROC-AUC (5-fold): {roc_auc_score(y, oof):.3f}, AP: {average_precision_score(y, oof):.3f}")
    top20 = df.assign(p=oof).nlargest(20, "p")
    print(f"precision@20: {top20.flooded.mean():.2f} (доля реально затопленных в топ-20 по скору)")

    # Baseline для сравнения: скор из baseline_scores.py тех же НП, если есть
    # (сравнение печатается для слайда AI/ML).
    try:
        base = pd.read_csv("data/processed/scores_kz-sev.csv").drop_duplicates(subset="name")
        merged = df.merge(base[["name", "score"]], on="name", how="inner")
        print(f"baseline ROC-AUC: {roc_auc_score(merged.flooded, merged.score):.3f} (на тех же НП)")
    except FileNotFoundError:
        pass

    # Финальная модель + встроенный TreeSHAP (pred_contrib) — без пакета shap
    model.fit(X, y)
    proba = model.predict_proba(X)[:, 1]
    contrib = model.predict(X, pred_contrib=True)  # [n, n_features+1], последний столбец — bias

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        contributions = sorted(
            zip(FEATURES, contrib[i][:-1]), key=lambda t: abs(t[1]), reverse=True
        )[:4]
        factors = [
            {"name": FACTOR_LABELS[f].format(v=row[f]), "impact": round(float(v), 2)}
            for f, v in contributions
            if not np.isnan(row[f])
        ]
        rows.append([row["name"], row["lat"], row["lon"], round(100 * proba[i], 1),
                     json.dumps(factors, ensure_ascii=False)])

    out = pd.DataFrame(rows, columns=["name", "lat", "lon", "score", "factors_json"])
    out.to_csv(output_csv, index=False)
    print(f"Скоры сохранены: {output_csv}")


if __name__ == "__main__":
    main()
