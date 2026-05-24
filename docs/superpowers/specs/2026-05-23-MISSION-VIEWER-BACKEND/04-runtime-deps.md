# Runtime Dependencies

## New Dependencies

Add to `backend/requirements.txt`:

```
playwright>=1.49
anthropic>=0.40
openai>=1.60
```

These are already used in agent code but were never added to the
requirements file (they were installed manually for live testing).

## Dockerfile Changes

After `pip install`, add Playwright browser installation:

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium
```

Only Chromium is needed — the PlaywrightDriver uses Chromium exclusively.

## Docker Compose

The Celery worker service needs the same image (it already uses the
same Dockerfile), so browser deps are available automatically.

No new services needed — Redis and Celery worker are already configured.

## System Dependencies

Playwright's `--with-deps` flag installs system libraries (libglib,
libnss, libatk, etc.) automatically inside the Docker image. No
manual apt-get needed.

## Environment Variables

The Celery worker needs access to LLM provider keys. These should be
set in the worker service's environment in docker-compose.yml:

- `ANTHROPIC_API_KEY` — for AnthropicProvider
- `OPENROUTER_API_KEY` — for OpenRouterProvider (reads from env or
  `~/.config/openrouter/openrouter_api_key`)

The mission profile's `model_policy.provider` selects which key is
used at runtime.
