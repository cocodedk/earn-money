# Task 10: Runtime Dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Modify: `docker-compose.yml`

---

- [ ] **Step 1: Add runtime deps to requirements.txt**

Add after the `# Cookbook stub runners` section in `backend/requirements.txt`:

```
# V3 Agent runtime
playwright>=1.49
anthropic>=0.40
openai>=1.60
```

- [ ] **Step 2: Add Playwright browser install to Dockerfile**

In `backend/Dockerfile`, add after `RUN pip install -r requirements.txt`:

```dockerfile
RUN playwright install --with-deps chromium
```

The full Dockerfile should look like:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt
RUN playwright install --with-deps chromium

COPY . /app/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

- [ ] **Step 3: Add LLM API keys to worker environment in docker-compose.yml**

In `docker-compose.yml`, add to the `worker:` service `environment:` section:

```yaml
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
```

- [ ] **Step 4: Verify requirements install locally**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && pip install playwright anthropic openai 2>&1 | tail -5`
Expected: Successfully installed (or already satisfied)

- [ ] **Step 5: Run full test suite to confirm nothing broke**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest --tb=short -q`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/Dockerfile docker-compose.yml
git commit -m "feat(agent): add playwright/anthropic/openai runtime deps + Dockerfile browser install"
```
