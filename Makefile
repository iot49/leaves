#!/usr/bin/make

.PHONY: help serve deploy doc serve-doc test


help:
	@echo "make help"
	@echo "    Show help message."
	@echo
	@echo "make serve"
	@echo "    Serve the backend locally."
	@echo "make deploy"
	@echo "    Deploy to balena."
	@echo
	@echo "make doc"
	@echo "    Build documentation."
	@echo
	@echo "make serve-doc"
	@echo "    Serve documentation locally at http://localhost:8000."
	@echo
	@echo "make test"
	@echo "    Run tests."


serve:
	cd server && \
	ENVIRONMENT="dev" \
	rye run uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level error --reload

deploy:
	(cd deploy && set -o allexport && source ../.env && set +o allexport && envsubst < "docker-compose-dev.yml" > "docker-compose.yml";)
	cd deploy && balena push -m boser/leaf
	cd deploy && rm docker-compose.yml

doc:
	jupyter-book build doc

serve-doc:
	cd doc/_build/html && \  
	python -m http.server

test:
	ENVIRONMENT="test" \
	cd lib && \
	rye run pytest -s # -k test_entities --cov="."
	# cd earth/backend && \
	# ENVIRONMENT="test" \
	# rye run pytest -s # -k test_gateway_token # --cov="."	
