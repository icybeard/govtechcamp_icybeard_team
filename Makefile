.PHONY: up upd down clean logs db backend frontend build

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

## make build — проверить, что всё собирается локально
build:
	cd backend && dotnet build
	npm --prefix frontend run build
