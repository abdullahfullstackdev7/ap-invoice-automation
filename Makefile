.PHONY: up down logs migrate load-data seed verify-audit ocr-bakeoff evaluate-extraction evaluate-matching test demo lint typecheck backend-install frontend-install dataset coverage contract-test loadtest security-audit

up:
	docker compose up -d --build
	$(MAKE) migrate

down:
	docker compose down

logs:
	docker compose logs -f

backend-install:
	cd backend && uv sync

frontend-install:
	cd frontend && npm install

migrate:
	docker compose exec api uv run alembic upgrade head

load-data:
	docker compose exec api uv run python /dataset/scripts/load_to_db.py

seed:
	docker compose exec api uv run python -m scripts.seed

verify-audit:
	docker compose exec api uv run python -m scripts.verify_audit

ocr-bakeoff:
	docker compose exec api uv run python -m scripts.ocr_bakeoff

evaluate-extraction:
	docker compose exec api uv run python -m scripts.evaluate_extraction

evaluate-matching:
	docker compose exec api uv run python -m scripts.evaluate_matching

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
	cd backend && uv run mypy app tests scripts
	cd frontend && npm run typecheck

coverage:
	cd backend && uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
	cd backend && uv run pytest tests/test_matching_rules.py tests/test_matching_engine.py tests/test_matching_property.py tests/test_matching_duplicate.py tests/test_matching_pipeline.py --cov=app.matching --cov-fail-under=95 -q

contract-test:
	cd backend && uv run pytest tests/test_api_contract.py -q

loadtest:
	cd backend && uv run locust -f loadtest/locustfile.py --host http://localhost:8000 --headless -u 50 -r 10 -t 2m --user-classes ReadUser

security-audit:
	cd backend && uv run bandit -r app -q
	cd backend && uv run pip-audit -r <(uv export --no-hashes --format requirements-txt) --progress-spinner off
	cd frontend && npm audit --omit=dev --audit-level=high
