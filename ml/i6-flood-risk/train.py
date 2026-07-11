#!/usr/bin/env python3
"""Обучение модели паводкового риска (LightGBM + SHAP). Требует разметку.

Вход:
  features.csv — из scripts/compute_terrain_features.py (+ дополняйте признаками ERA5)
  labels.csv   — name,flooded (1/0 по паводку-2024; методика — в docs/data/)
Выход:
  scores.csv   — name,lat,lon,score,factors_json (совместим со scripts/load_scores.py)

Использование:
    pip install -r ml/i6-flood-risk/requirements.txt
    python3 ml/i6-flood-risk/train.py features.csv labels.csv scores.csv
"""
import json
import sys

import lightgbm as lgb
import pandas as pd
import shap
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

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
    labels = pd.read_csv(labels_csv)
    df = df.merge(labels, on="name", how="inner")
    print(f"НП с разметкой: {len(df)}, затоплено: {df.flooded.sum()}")
    if df.flooded.sum() < 20:
        sys.exit("Слишком мало положительных примеров (<20) — модель не обучить, используйте baseline")

    X = df[FEATURES].fillna(df[FEATURES].median())
    y = df["flooded"]

    model = lgb.LGBMClassifier(
        n_estimators=300, learning_rate=0.05, num_leaves=15,
        class_weight="balanced", random_state=42, verbose=-1
    )

    # Честная оценка: out-of-fold предсказания
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    print(f"ROC-AUC (5-fold): {roc_auc_score(y, oof):.3f}, AP: {average_precision_score(y, oof):.3f}")
    top20 = df.assign(p=oof).nlargest(20, "p")
    print(f"precision@20: {top20.flooded.mean():.2f}")

    # Финальная модель на всех данных + SHAP на каждый НП
    model.fit(X, y)
    proba = model.predict_proba(X)[:, 1]
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        contributions = sorted(
            zip(FEATURES, shap_values[i]), key=lambda t: abs(t[1]), reverse=True
        )[:4]
        factors = [
            {"name": FACTOR_LABELS[f].format(v=row[f]), "impact": round(float(v), 2)}
            for f, v in contributions
        ]
        rows.append([row["name"], row["lat"], row["lon"], round(100 * proba[i], 1), json.dumps(factors, ensure_ascii=False)])

    out = pd.DataFrame(rows, columns=["name", "lat", "lon", "score", "factors_json"])
    out.to_csv(output_csv, index=False)
    print(f"Скоры сохранены: {output_csv}")


if __name__ == "__main__":
    main()
