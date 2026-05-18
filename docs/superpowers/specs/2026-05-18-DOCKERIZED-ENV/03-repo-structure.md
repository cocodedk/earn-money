# 3. Suggested repo structure

Use this structure unless the repo already has a better one.

```text
.
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/
│   ├── apps/
│   │   ├── projects/
│   │   ├── targets/
│   │   ├── scans/
│   │   ├── findings/
│   │   └── evidence/
│   └── scanner/
│       ├── stubs/
│       ├── runners/
│       └── control.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
└── nginx/
    └── default.conf
```
