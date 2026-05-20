"""Title + JSON-error extraction helpers for `normalize`."""
from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup


def extract_title(body: str) -> str | None:
    """Pull `<title>` text via BeautifulSoup; None when absent or empty."""
    if not body:
        return None
    soup = BeautifulSoup(body, "html.parser")
    title_tag = soup.find("title")
    if title_tag is None:
        return None
    text = title_tag.get_text(strip=True)
    return text or None


def parse_json_errors(
    body: str, content_type: str,
) -> tuple[str | None, dict[str, str]]:
    """Extract `error_code` and field-level `errors` from a JSON body."""
    if "json" not in content_type.lower() or not body:
        return None, {}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None, {}
    if not isinstance(data, dict):
        return None, {}
    code = data.get("error_code") or data.get("code")
    code_str = str(code) if isinstance(code, str) else None
    errors = data.get("errors") if isinstance(data.get("errors"), dict) else {}
    safe_errors = {
        str(k): str(v) for k, v in errors.items()
        if isinstance(v, (str, int, float))
    }
    return code_str, safe_errors


def coerce_str(value: Any) -> str:
    return str(value) if value is not None else ""


def coerce_optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
