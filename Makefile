PY ?= python3

.PHONY: help run migrate makemigrations migrations superuser test shell ngrok \
	fe-install fe-dev fe-lint fe-build fe-audit audit

help:
	@echo "Common commands:";
	@echo "  make run              - start Django dev server";
	@echo "  make migrations       - makemigrations + migrate";
	@echo "  make test             - run Django tests";
	@echo "  make superuser        - create Django superuser";
	@echo "  make ngrok            - start ngrok tunnel for callbacks";
	@echo "  make fe-dev           - start frontend (Vite) dev server";
	@echo "  make fe-lint          - lint frontend";
	@echo "  make fe-build         - build frontend";
	@echo "  make audit            - dependency vulnerability scans (pip-audit + npm audit)";

run:
	@echo "Starting server at port 8000 ..."
	$(PY) manage.py runserver

migrate:
	@echo "Running migrations ..."
	$(PY) manage.py migrate

makemigrations:
	@echo "Making migrations ..."
	$(PY) manage.py makemigrations

migrations: makemigrations migrate

superuser:
	@echo "Creating superuser ..."
	$(PY) manage.py createsuperuser

test:
	$(PY) manage.py test

shell:
	$(PY) manage.py shell

ngrok:
	$(PY) ngrok.py

fe-install:
	cd frontend && npm ci

fe-dev: fe-install
	cd frontend && npm run dev

fe-lint: fe-install
	cd frontend && npm run lint

fe-build: fe-install
	cd frontend && npm run build

fe-audit: fe-install
	cd frontend && npm audit --audit-level=high

audit: fe-audit
	$(PY) -m pip install --upgrade pip-audit
	$(PY) -m pip_audit -r requirements.txt