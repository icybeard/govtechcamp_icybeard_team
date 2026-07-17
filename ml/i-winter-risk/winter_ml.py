#!/usr/bin/env python3
"""Зимняя ML-модель по районам (LightGBM, честный сплит по сезонам) — по образцу
паводков (i6: ретроспектива сезонов + факторы «почему») и пожаров (i9: район×день).

Данные готовятся скриптами (см. docs/ideas/i-winter-risk/winter-ml-data.md):
  scripts/winter_fetch_daily.py          → data/processed/winter_daily_features.csv
  scripts/winter_labels_storm_archive.py → data/raw/winter_storm_warnings.csv

Подкоманды:
  train    — собрать датасет район×день (join разметки по области и дате),
             обучить LightGBM (train — сезоны до 2025, test — 2025–26),
             сравнить с формульным baseline, сохранить модель и metrics.json
  seasons  — ретроспектива как у паводков: модель скорит каждый сезон, на район —
             скор 0–100 и топ-факторы «почему» (средние SHAP-вклады за сезон)
             → frontend/public/data/winter-ml-seasons.json
  today    — прогноз на сегодня: погода Open-Meteo forecast → скор и факторы
             → frontend/public/data/winter-ml-today.json

Запуск (venv): .venv/bin/python ml/i-winter-risk/winter_ml.py train|seasons|today
Target: день с предупреждением Казгидромета (метель/гололёд/мороз) по области района.
"""
import csv
import json
import math
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
FEATURES_CSV = REPO / "data/processed/winter_daily_features.csv"
LABELS_CSV = REPO / "data/raw/winter_storm_warnings.csv"
MODEL_PATH = REPO / "data/processed/winter_lgbm.txt"
METRICS_PATH = REPO / "ml/i-winter-risk/metrics.json"
SEASONS_JSON = REPO / "frontend/public/data/winter-ml-seasons.json"
TODAY_JSON = REPO / "frontend/public/data/winter-ml-today.json"

TEST_SEASON = 2026  # test — последняя зима 2025–26, train — всё, что раньше
TARGET_FLAGS = ("blizzard", "ice", "frost")  # опасный день = предупреждение этих типов
WEATHER_FEATURES = ["tmin", "tmax", "wmax", "gusts", "snowfall", "rain", "precip", "freezing_rain", "blizzard_like"]
FEATURES = [*WEATHER_FEATURES, "doy_sin", "doy_cos", "prior"]

# Подписи факторов для карточки района (как FACTOR_LABELS у паводков)
FACTOR_LABELS = {
    "tmin": "Минимальная температура",
    "tmax": "Максимальная температура",
    "wmax": "Ветер",
    "gusts": "Порывы ветра",
    "snowfall": "Снегопад",
    "rain": "Дождь при морозе",
    "precip": "Осадки",
    "freezing_rain": "Гололёдная ситуация",
    "blizzard_like": "Метелевая ситуация",
    "prior": "Историческая частота предупреждений",
}


def http_get(url, timeout=180, attempts=8):
    last = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode()
        except Exception as e:  # noqa: BLE001 — ретраим любой сетевой сбой
            last = e
            time.sleep(min(60, 8 * (attempt + 1)))
    raise SystemExit(f"HTTP не удалось: {last}")


def add_doy(df):
    import numpy as np
    import pandas as pd

    doy = pd.to_datetime(df["date"]).dt.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365)
    return df


def load_dataset():
    """Район×день с target'ом: join фичей и предупреждений по (область, дата)."""
    import pandas as pd

    if not FEATURES_CSV.exists() or not LABELS_CSV.exists():
        sys.exit(f"Нет данных: сначала scripts/winter_fetch_daily.py и scripts/winter_labels_storm_archive.py\n({FEATURES_CSV}\n {LABELS_CSV})")

    df = add_doy(pd.read_csv(FEATURES_CSV))
    labels = pd.read_csv(LABELS_CSV)
    labels["danger"] = labels[list(TARGET_FLAGS)].max(axis=1)
    danger_days = labels[labels.danger > 0].groupby(["region_iso", "date"]).size()
    df["target"] = [int((iso, day) in danger_days.index) for iso, day in zip(df.region_iso, df.date)]
    return df


def attach_prior(df):
    """Частота опасных дней района по train-сезонам (без утечки в тест), 0–100."""
    train_mask = df.season < TEST_SEASON
    prior = (df[train_mask].groupby("district_id").target.mean() * 100).to_dict()
    df["prior"] = df.district_id.map(prior).fillna(0)
    return df, prior


def baseline_score(df):
    """Формульный baseline на тех же строках — дневной аналог зимнего индекса."""
    cold = ((-10 - df.tmin) / 20).clip(0, 1)
    return 45 * df.blizzard_like + 35 * df.freezing_rain + 20 * cold


def top_factors(contrib_row, n=3):
    """Топ-факторы по |SHAP-вкладу|; сезонность (doy) — служебная, не показываем."""
    pairs = [(name, float(value)) for name, value in contrib_row.items() if name in FACTOR_LABELS]
    pairs.sort(key=lambda p: -abs(p[1]))
    return [{"name": FACTOR_LABELS[name], "impact": round(value, 2)} for name, value in pairs[:n]]


def cmd_train():
    import lightgbm as lgb
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score

    df, prior = attach_prior(load_dataset())
    train, test = df[df.season < TEST_SEASON], df[df.season == TEST_SEASON]
    print(f"train: {len(train)} строк ({train.target.mean():.3%} позитивов), test-{TEST_SEASON}: {len(test)} ({test.target.mean():.3%})")

    model = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=31, class_weight="balanced", random_state=42, verbose=-1)
    model.fit(train[FEATURES], train.target)
    proba = model.predict_proba(test[FEATURES])[:, 1]
    baseline = baseline_score(test)

    k = int(0.2 * len(test))

    def capture(scores):
        idx = np.argsort(-scores)[:k]
        return test.target.values[idx].sum() / max(1, test.target.sum())

    metrics = {
        "rows_train": int(len(train)),
        "rows_test": int(len(test)),
        "positives_test": int(test.target.sum()),
        "model_auc": round(float(roc_auc_score(test.target, proba)), 3),
        "baseline_auc": round(float(roc_auc_score(test.target, baseline)), 3),
        "model_ap": round(float(average_precision_score(test.target, proba)), 3),
        "baseline_ap": round(float(average_precision_score(test.target, baseline)), 3),
        "model_capture_top20": round(float(capture(proba)), 3),
        "baseline_capture_top20": round(float(capture(baseline.values)), 3),
        "split": f"train — сезоны до {TEST_SEASON - 1}, test — {TEST_SEASON - 1}–{str(TEST_SEASON)[2:]} (nov–mar, район×день)",
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=1))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(MODEL_PATH))
    METRICS_PATH.write_text(json.dumps({**metrics, "prior": prior}, ensure_ascii=False), encoding="utf-8")
    print(f"Модель → {MODEL_PATH}, метрики → {METRICS_PATH}")


def cmd_seasons():
    import lightgbm as lgb
    import pandas as pd

    booster = lgb.Booster(model_file=str(MODEL_PATH))
    prior = json.loads(METRICS_PATH.read_text(encoding="utf-8"))["prior"]
    df = add_doy(pd.read_csv(FEATURES_CSV))
    df["prior"] = df.district_id.map(prior).fillna(0)

    features = df[FEATURES].to_numpy()
    df["proba"] = booster.predict(features)
    contrib = booster.predict(features, pred_contrib=True)[:, : len(FEATURES)]
    contrib_df = pd.DataFrame(contrib, columns=FEATURES, index=df.index)

    result = {}
    for (season, district), group in df.groupby(["season", "district_id"]):
        mean_contrib = contrib_df.loc[group.index].mean()
        result.setdefault(str(season), {})[district] = {
            "proba": round(float(group.proba.mean()) * 100, 1),
            "factors": top_factors(mean_contrib),
        }

    # Скор для карты — процентиль района внутри сезона (0–100). Сырая средняя
    # вероятность опасного дня мала (базовая частота ~3%) — на общей шкале 0–100
    # карта выглядела бы пустой. Ранг сопоставим с индексом и отвечает на вопрос
    # приоритизации «какие районы рискованнее остальных»; вероятность остаётся
    # в поле proba и показывается в карточке района.
    for season_key, districts in result.items():
        probas = pd.Series({district: v["proba"] for district, v in districts.items()})
        ranks = probas.rank(pct=True)
        for district, v in districts.items():
            v["score"] = round(float(ranks[district]) * 100)

    SEASONS_JSON.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    seasons = ", ".join(sorted(result))
    print(f"Сезоны [{seasons}] → {SEASONS_JSON}")


def cmd_today():
    import lightgbm as lgb
    import pandas as pd

    # Модель обучена только на днях ноября–марта: летний прогноз — экстраполяция
    # вне области применимости (сезононезависимый приор + «холодная ночь» дают
    # ложные скоры). Вне сезона файл не генерируем; фронт дублирует эту проверку.
    month = datetime.now(timezone.utc).month
    if 4 <= month <= 10:
        sys.exit("Сейчас не зимний сезон (ноябрь–март) — прогноз «сегодня» вне области применимости модели, файл не сгенерирован.")

    sys.path.insert(0, str(REPO / "scripts"))
    from winter_fetch_daily import DAILY_VARS, load_districts  # noqa: E402

    booster = lgb.Booster(model_file=str(MODEL_PATH))
    prior = json.loads(METRICS_PATH.read_text(encoding="utf-8"))["prior"]
    districts = load_districts()

    payload = []
    for i in range(0, len(districts), 60):  # батчи + паузы — щадим минутный лимит
        chunk = districts[i : i + 60]
        lats = ",".join(f"{d['lat']:.3f}" for d in chunk)
        lons = ",".join(f"{d['lon']:.3f}" for d in chunk)
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&daily={DAILY_VARS}&forecast_days=1&wind_speed_unit=ms&timezone=UTC"
        part = json.loads(http_get(url, attempts=10))
        payload.extend(part if isinstance(part, list) else [part])
        time.sleep(20)

    doy = datetime.now(timezone.utc).timetuple().tm_yday
    rows = []
    for d, w in zip(districts, payload):
        daily = {var: (w["daily"].get(var) or [0])[0] or 0.0 for var in DAILY_VARS.split(",")}
        tmin, rain = daily["temperature_2m_min"], daily["rain_sum"]
        snowfall, wmax = daily["snowfall_sum"], daily["wind_speed_10m_max"]
        rows.append({
            "tmin": tmin, "tmax": daily["temperature_2m_max"], "wmax": wmax,
            "gusts": daily["wind_gusts_10m_max"], "snowfall": snowfall, "rain": rain,
            "precip": daily["precipitation_sum"],
            "freezing_rain": int(rain >= 0.5 and tmin < 0),
            "blizzard_like": int(snowfall >= 1 and wmax >= 10),
            "doy_sin": math.sin(2 * math.pi * doy / 365), "doy_cos": math.cos(2 * math.pi * doy / 365),
            "prior": prior.get(d["id"], 0),
        })
    frame = pd.DataFrame(rows)[FEATURES]
    proba = booster.predict(frame.to_numpy())
    contrib = booster.predict(frame.to_numpy(), pred_contrib=True)[:, : len(FEATURES)]

    values, factors = {}, {}
    for i, d in enumerate(districts):
        values[d["id"]] = round(float(proba[i]) * 100)
        factors[d["id"]] = top_factors(dict(zip(FEATURES, contrib[i])))

    TODAY_JSON.write_text(json.dumps({
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "values": values,
        "factors": factors,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"Прогноз на сегодня (макс {max(values.values())}) → {TODAY_JSON}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"train": cmd_train, "seasons": cmd_seasons, "today": cmd_today}.get(cmd, lambda: sys.exit(__doc__))()
