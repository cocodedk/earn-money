"""Shared test helper for the _try_paths-backed POST loop stubs
(`register_via_api`, `login_via_api`, future logout/password-change).

`patch_client(module_path, queue, seen_urls=None)` returns a
`contextlib.AbstractContextManager` that swaps `Client` inside
``module_path`` for a fake whose `.post(url, **kw)` pulls the next
result off the shared queue. If the popped value is a BaseException
instance, it's raised (transport-failure simulation).
"""
from __future__ import annotations

from unittest.mock import patch


def patch_client(
    module_path: str, post_queue: list, *,
    seen_urls: list | None = None,
):
    """Patch `Client` inside ``module_path`` (the module that uses
    `with Client(...) as c: c.post(...)`)."""
    class _FakeClient:
        def __init__(self, **_kw: object) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def post(self, url: str, **_kw: object):  # type: ignore[no-untyped-def]
            if seen_urls is not None:
                seen_urls.append(url)
            result = post_queue.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

    return patch(module_path, _FakeClient)
