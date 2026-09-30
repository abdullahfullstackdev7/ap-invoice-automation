.PHONY: up down logs seed test demo lint typecheck backend-install frontend-install dataset

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

backend-install:
	cd backend && uv sync

frontend-install:
	cd frontend && npm install

seed:
	docker compose exec api python -m scripts.seed

dataset:
	cd dataset && bash download_fatura.sh
	cd dataset && python scripts/inspect_fatura.py
	cd dataset && python scripts/build_truth.py
	cd dataset && python scripts/select_demo_set.py
	cd dataset && python scripts/generate_synthetic.py
	cd dataset && python scripts/augment_scans.py
	cd dataset && python scripts/validate_dataset.py

test:
	cd backend && uv run pytest
	cd frontend && npm run test

demo:
	docker compose exec api python -m scripts.export_demo

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint

typecheck:
	cd backend && uv run mypy app
	cd frontend && npm run typecheck
