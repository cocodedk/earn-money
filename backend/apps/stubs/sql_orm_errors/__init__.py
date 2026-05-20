"""Stub 1.19 — SQL/ORM error disclosure detector.

Body-signature classifier on HTTP response bodies. Detects exposed
database driver / ORM exception text that reveals backend internals
(table/column names, SQL fragments, stack frames).

Registration of `@register("1.19")` and the `apps.py` `ready()` import
land in slice 19-B per the Phase 1 closeout plan.
"""
from __future__ import annotations
