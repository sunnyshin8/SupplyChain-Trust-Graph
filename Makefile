.PHONY: install backend backend-snowflake frontend test build scorecard verify-submission snowflake-deploy snowflake-validate snowflake-scorecard snowflake-parity live-api-verify coco-analyst-verify coco-analyst-eval

install:
	python3 -m venv .venv
	.venv/bin/pip install -e './backend[dev]'
	npm install --prefix frontend

backend:
	.venv/bin/uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

backend-snowflake:
	SUPPLYCHAIN_DATA_MODE=snowflake SNOWFLAKE_CONNECTION_NAME=supplychain-hackathon .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

frontend:
	npm run dev --prefix frontend

test:
	.venv/bin/pytest backend

build:
	npm run build --prefix frontend

scorecard:
	.venv/bin/python -m backend.app.scorecard

snowflake-deploy:
	.venv/bin/python scripts/deploy_snowflake.py --connection supplychain-hackathon-admin

snowflake-validate:
	.venv/bin/python scripts/validate_snowflake_runtime.py --connection supplychain-hackathon

snowflake-scorecard:
	.venv/bin/python -m scripts.scorecard_snowflake_readonly --connection supplychain-hackathon

snowflake-parity:
	.venv/bin/python -m scripts.verify_delay_parity --connection supplychain-hackathon

live-api-verify:
	.venv/bin/python scripts/verify_live_api.py

coco-analyst-verify:
	.venv/bin/python -m scripts.verify_coco_analyst --connection supplychain-hackathon

coco-analyst-eval:
	.venv/bin/python -m scripts.evaluate_coco_analyst --connection supplychain-hackathon

verify-submission: test build scorecard
