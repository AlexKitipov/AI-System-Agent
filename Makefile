.PHONY: install install-dev run smoke-test

PYTHON ?= python
HOST ?= 127.0.0.1
PORT ?= 8765

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn gateway.server:app --host $(HOST) --port $(PORT)

smoke-test:
	$(PYTHON) -c "import gateway.server; print('import gateway.server ok')"
	$(PYTHON) -m uvicorn gateway.server:app --host $(HOST) --port $(PORT) > /tmp/ai-system-agent-smoke.log 2>&1 & \
	pid=$$!; \
	trap 'kill $$pid >/dev/null 2>&1 || true' EXIT; \
	for i in $$(seq 1 20); do \
		$(PYTHON) -c "import urllib.request; urllib.request.urlopen('http://$(HOST):$(PORT)/health', timeout=1).read()" && break; \
		sleep 0.25; \
	done; \
	$(PYTHON) -c "import json, urllib.request; print(json.loads(urllib.request.urlopen('http://$(HOST):$(PORT)/health', timeout=3).read().decode()))"
