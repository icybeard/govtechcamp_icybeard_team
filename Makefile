.PHONY: up upd down clean logs db backend frontend build demo-data

## make demo-data — загрузить данные пилота (НП СКО + ML-скоры + сезоны 2010–2024) в запущенный стек
demo-data:
	python3 scripts/load_settlements.py KZ-SEV data/raw/settlements_kz-sev.csv
	python3 scripts/load_scores.py KZ-SEV data/processed/scores_ml_kz-sev.csv
	@for y in $$(seq 2010 2026); do \
		python3 scripts/load_scores.py KZ-SEV data/processed/scores_$${y}_kz-sev.csv --period $$y | tail -1; \
	done

## .env создаётся из примера при первом запуске (креды суперпользователя, JWT-ключ)
.env:
	cp .env.example .env
	@echo "[env] создан .env из .env.example — поменяйте пароли при необходимости"

## make up — весь стек в docker: PostgreSQL + API (:5080) + веб (:5173). Ctrl+C — остановить.
up: .env
	docker compose up --build

## make upd — то же, но в фоне
upd: .env
	docker compose up --build -d

## make down — остановить контейнеры (данные БД сохраняются в volume)
down:
	docker compose down

## make clean — остановить и удалить volume БД (полный сброс данных)
clean:
	docker compose down -v

## make logs — логи всех контейнеров
logs:
	docker compose logs -f

## ---- Локальная разработка с hot-reload (вне docker) ----

## make db — только PostgreSQL в docker
db:
	docker compose up -d db

## make backend — API локально с hot-reload (нужна БД: make db)
backend: .env
	cd backend/src/Api && dotnet watch

## make frontend — веб-клиент локально с hot-reload (vite проксирует /api на :5080)
frontend:
	npm --prefix frontend run dev

## make fire-today — ML-прогноз пожаров на сегодня (Open-Meteo; при 429 подождать сброса лимита)
fire-today:
	.venv/bin/python ml/i9-fire-risk/fire_ml.py today

## make winter-ml — зимний ML целиком: данные (ERA5 + архив Казгидромета) → обучение →
## ретроспектива сезонов для фронтенда. Один раз, результат коммитится (как скоры паводков):
## frontend/public/data/winter-ml-seasons.json + data/processed/winter_lgbm.txt + metrics.json
winter-ml:
	python3 scripts/winter_fetch_daily.py 2020 2026
	python3 scripts/winter_labels_storm_archive.py 2020 2026
	.venv/bin/python ml/i-winter-risk/winter_ml.py train
	.venv/bin/python ml/i-winter-risk/winter_ml.py seasons

## make winter-today — зимний ML-прогноз на сегодня (Open-Meteo; аналог fire-today)
winter-today:
	.venv/bin/python ml/i-winter-risk/winter_ml.py today

## make build — проверить, что всё собирается локально
build:
	cd backend && dotnet build
	npm --prefix frontend run build
