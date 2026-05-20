# 10. Security rules

Do not hard-code secrets.

Do not expose Redis or Postgres publicly.

Do not add real exploit logic.

Do not make the worker run arbitrary shell commands.

Do not let frontend control raw worker execution.

All scan actions must go through backend API.

PostgreSQL is the source of truth.
