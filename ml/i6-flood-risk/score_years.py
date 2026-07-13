#!/usr/bin/env python3
"""Ретроспективные скоры по сезонам: модель 2024 применяется к погоде каждого года.

Обучение — как в train.py (те же признаки/гиперпараметры, таргет — паводок-2024),
затем predict + pred_contrib на каждый сезонный features-файл.

Использование:
    .venv/bin/python ml/i6-flood-risk/score_years.py \
        data/processed/features_kz-sev.csv data/raw/labels_2024.csv \
        data/processed 2010 2024
"""
import json
import pathlib
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from train import FACTOR_LABELS, FEATURES  # noqa: E402


def main() -> None:
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    base_features_csv, labels_csv, out_dir, year_from, year_to = sys.argv[1:6]

    train_df = pd.read_csv(base_features_csv).drop_duplicates(subset="name", keep="first")
    labels = pd.read_csv(labels_csv)
    train_df = train_df.merge(labels, on="name", how="inner")
    print(f"Обучение: {len(train_df)} НП, позитивов {int(train_df.flooded.sum())}")

    medians = train_df[FEATURES].median()
    model = lgb.LGBMClassifier(
        n_estimators=200, learning_rate=0.05, num_leaves=7, min_child_samples=5,
        class_weight="balanced", random_state=42, verbose=-1
    )
    model.fit(train_df[FEATURES].fillna(medians), train_df["flooded"])

    for year in range(int(year_from), int(year_to) + 1):
        df = pd.read_csv(pathlib.Path(out_dir) / f"features_{year}_kz-sev.csv").drop_duplicates(subset="name", keep="first")
        X = df[FEATURES].fillna(medians)
        proba = model.predict_proba(X)[:, 1]
        contrib = model.predict(X, pred_contrib=True)

        rows = []
        for i, (_, row) in enumerate(df.iterrows()):
            top = sorted(zip(FEATURES, contrib[i][:-1]), key=lambda t: abs(t[1]), reverse=True)[:4]
            factors = [
                {"name": FACTOR_LABELS[f].format(v=row[f]), "impact": round(float(v), 2)}
                for f, v in top
                if not (isinstance(row[f], float) and np.isnan(row[f]))
            ]
            rows.append([row["name"], row["lat"], row["lon"], round(100 * proba[i], 1),
                         json.dumps(factors, ensure_ascii=False)])

        out_path = pathlib.Path(out_dir) / f"scores_{year}_kz-sev.csv"
        pd.DataFrame(rows, columns=["name", "lat", "lon", "score", "factors_json"]).to_csv(out_path, index=False)
        high = sum(1 for r in rows if r[3] >= 60)
        print(f"{year}: скор ≥60 у {high} НП → {out_path}")


if __name__ == "__main__":
    main()
