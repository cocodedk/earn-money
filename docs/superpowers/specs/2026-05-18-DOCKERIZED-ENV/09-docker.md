# 9. Docker requirements

`docker compose up --build` must start everything.

Expected local URLs:

```text
frontend: http://localhost
backend API: http://localhost/api/
django admin: http://localhost/admin/
```

Add `.env.example`.

Include at least:

```text
DJANGO_SECRET_KEY=
DJANGO_DEBUG=true
POSTGRES_DB=scanner
POSTGRES_USER=scanner
POSTGRES_PASSWORD=scanner
DATABASE_URL=postgres://scanner:scanner@postgres:5432/scanner
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
ALLOWED_HOSTS=localhost,127.0.0.1,backend
CORS_ALLOWED_ORIGINS=http://localhost,http://localhost:5173
```
