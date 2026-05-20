"""Framework / runtime hint detector for stub 1.17 FU-2.

Spec §"Strong disclosure indicators" lists framework debug pages
and runtime exception traces as a strong family. This module
detects PRESENCE of a known framework in a response body and emits
the framework name as a hint. The full stack-trace shape is the
job of stub 1.16 — FU-2 stays lightweight on purpose so the
spec's medium-confidence branch (error status + framework hint,
no full stack/path) becomes reachable.

Hint names match the spec's enumeration: django, flask, fastapi,
starlette, sqlalchemy, express, nestjs, spring, tomcat, jetty,
dotnet, laravel, symfony, rails, rack, go.

The pattern set is intentionally conservative — each pattern
requires a structural signal (module-path dot, namespace separator,
class-method-pair) so generic prose containing the word "django"
or "rails" can't false-positive.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

import re


_FRAMEWORK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Python frameworks — module-path dot anchors avoid prose false
    # positives ("ourdjangoapp" doesn't match `django\.`).
    ("django", re.compile(r"\bdjango\.[a-z]")),
    ("flask", re.compile(r"\b(?:flask\.[a-z]|werkzeug\.[a-z])")),
    ("fastapi", re.compile(r"\bfastapi\.[a-z]")),
    ("starlette", re.compile(r"\bstarlette\.[a-z]")),
    ("sqlalchemy", re.compile(r"\bsqlalchemy\.[a-z]")),
    # Node frameworks
    ("express", re.compile(r"/node_modules/express/")),
    ("nestjs", re.compile(r"@nestjs/")),
    # JVM frameworks — `org.springframework` is universal; Whitelabel
    # is the default Spring-Boot 404 page even without the package
    # name visible. Tomcat/Jetty use distinct package roots.
    ("spring", re.compile(
        r"(?:\borg\.springframework\.|Whitelabel Error Page)",
    )),
    ("tomcat", re.compile(r"\borg\.apache\.catalina\.")),
    ("jetty", re.compile(r"\borg\.eclipse\.jetty\.")),
    # .NET — DeveloperExceptionPage middleware OR a System.* exception
    # class (covers framework + first-party .NET runtime errors).
    ("dotnet", re.compile(
        r"(?:Microsoft\.AspNetCore\.|System\.[A-Z][A-Za-z]*Exception\b)",
    )),
    # PHP frameworks — backslash namespace separator pins them.
    ("laravel", re.compile(r"Illuminate\\[A-Z][A-Za-z]+\\")),
    ("symfony", re.compile(r"Symfony\\[A-Z][A-Za-z]+\\")),
    # Ruby — `Rack::` or `ActionController::` / `ActiveRecord::`.
    ("rails", re.compile(
        r"\b(?:Action(?:Controller|View|Mailer)|ActiveRecord)::",
    )),
    ("rack", re.compile(r"\bRack::[A-Z]")),
    # Go — `panic:` followed by goroutine output.
    ("go", re.compile(r"\bpanic:.*\bgoroutine\s+\d+", re.DOTALL)),
)


def detect_framework_hints(body: str) -> list[str]:
    """Return the ordered list of framework names whose pattern
    fires on ``body``. Each name appears at most once even if its
    pattern matches multiple times — callers want presence per
    framework, not match count."""
    if not body:
        return []
    return [name for name, pat in _FRAMEWORK_PATTERNS if pat.search(body)]
