# ML

Две обученные модели платформы (по подпапке на контур):

- [`i6-flood-risk/`](i6-flood-risk/) — паводки: LightGBM на разметке-2024 (СМИ+SAR-методика), ROC-AUC 0.867 vs 0.794 baseline; `train.py`, `score_years.py` (ретроспектива сезонов), `baseline_scores.py`
- [`i9-fire-risk/`](i9-fire-risk/) — пожары: дневная LightGBM «район×день» (186 тыс. строк, FIRMS 2021–2025 + погода), тест-2025 AUC 0.832 vs 0.686; `fire_ml.py fetch|train|today`

Окружение: `python3 -m venv .venv && .venv/bin/pip install -r ml/i6-flood-risk/requirements.txt` (pandas, scikit-learn, lightgbm; SHAP — встроенный TreeSHAP LightGBM).

Результаты уезжают в приложение двумя путями: скоры паводков — в PostgreSQL через `scripts/load_scores.py` (и автосидом из CSV), пожарный прогноз — статическим `frontend/public/data/fire-ml-today.json`. Каждый датасет описан в `docs/data/datasets.md` (требование ТЗ §9).
