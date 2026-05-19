"""Stack-trace signature table for stub 1.16.

14 deterministic families per spec §"Signature families". Each
entry pins a `required_re` (anchor for the family), an optional
`frame_re` (counts frames + identifies the top frame), and an
optional `exception_re` (extracts the exception class name when
present). Ordering matters: more-specific families come first so
django_debug beats python_traceback on a Django page, spring_boot_
error beats java_stack on a Whitelabel page, express_error beats
node_stack on an Express response.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/16-stack-traces.md
"""
from __future__ import annotations

import re
from typing import Literal, NamedTuple


Family = Literal[
    "python_traceback", "django_debug", "flask_werkzeug_debug",
    "node_stack", "express_error", "java_stack",
    "spring_boot_error", "dotnet_stack", "php_stack",
    "rails_error", "go_panic", "rust_panic",
    "generic_stack_trace", "path_line_leak",
]
Language = Literal[
    "python", "javascript", "java", "dotnet",
    "php", "ruby", "go", "rust", "unknown",
]


class Signature(NamedTuple):
    family: Family
    language: Language
    framework: str | None
    required_re: re.Pattern[str]
    frame_re: re.Pattern[str] | None
    exception_re: re.Pattern[str] | None


SIGNATURES: tuple[Signature, ...] = (
    Signature(
        family="django_debug", language="python", framework="django",
        required_re=re.compile(
            r"(?:Django.*Exception Type:|Exception Type:.*Traceback)",
            re.DOTALL,
        ),
        frame_re=re.compile(r'^\s*File "([^"]+)", line (\d+)', re.MULTILINE),
        exception_re=re.compile(
            r"Exception Type:\s*([A-Za-z][A-Za-z0-9_.]+)"
        ),
    ),
    Signature(
        family="flask_werkzeug_debug", language="python", framework="flask",
        required_re=re.compile(r"Werkzeug.*Traceback", re.DOTALL),
        frame_re=re.compile(r'^\s*File "([^"]+)", line (\d+)', re.MULTILINE),
        exception_re=re.compile(
            r"\b([A-Za-z][A-Za-z0-9_]*(?:Error|Exception))\b:"
        ),
    ),
    Signature(
        family="python_traceback", language="python", framework=None,
        required_re=re.compile(r"Traceback \(most recent call last\):"),
        frame_re=re.compile(r'^\s*File "([^"]+)", line (\d+)', re.MULTILINE),
        exception_re=re.compile(
            r"\b([A-Za-z][A-Za-z0-9_.]*"
            r"(?:Error|Exception|DoesNotExist|NotFound))\b"
        ),
    ),
    Signature(
        family="spring_boot_error", language="java", framework="spring",
        required_re=re.compile(
            r"(?:Whitelabel Error Page|org\.springframework)"
        ),
        frame_re=re.compile(
            r"\bat\s+[A-Za-z0-9_$.]+\(([A-Za-z0-9_$.]+\.java):(\d+)\)"
        ),
        exception_re=re.compile(
            r"\b((?:java|javax|jakarta|org)\.[A-Za-z0-9_.]+"
            r"(?:Exception|Error))\b"
        ),
    ),
    Signature(
        family="java_stack", language="java", framework=None,
        required_re=re.compile(
            r"\bat\s+[A-Za-z0-9_$.]+\([A-Za-z0-9_$.]+\.java:\d+\)"
        ),
        frame_re=re.compile(
            r"\bat\s+([A-Za-z0-9_$.]+)\(([A-Za-z0-9_$.]+\.java):(\d+)\)"
        ),
        exception_re=re.compile(
            r"\b((?:java|javax|jakarta|org|com)\.[a-z][A-Za-z0-9_.]+"
            r"(?:Exception|Error))\b"
        ),
    ),
    Signature(
        family="dotnet_stack", language="dotnet", framework=None,
        required_re=re.compile(r"Stack Trace:.*\.cs:line \d+", re.DOTALL),
        frame_re=re.compile(
            r"^\s*at\s+(.+?)\s+in\s+(.+?\.cs):line\s+(\d+)", re.MULTILINE,
        ),
        exception_re=re.compile(
            r"\b(System\.[A-Za-z0-9_.]+(?:Exception|Error))\b"
        ),
    ),
    Signature(
        family="php_stack", language="php", framework=None,
        required_re=re.compile(
            r"(?:Fatal error|Stack trace):.*#\d+\s+", re.DOTALL,
        ),
        frame_re=re.compile(r"^#\d+\s+(/[^\s(]+\.php)\((\d+)\)", re.MULTILINE),
        exception_re=re.compile(
            r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception))\b"
        ),
    ),
    Signature(
        family="rails_error", language="ruby", framework="rails",
        required_re=re.compile(
            r"(?:ActionController::|ActiveRecord::)[A-Z][A-Za-z0-9_]+"
        ),
        frame_re=re.compile(r"^\s*([^:]+):(\d+):in\s+'", re.MULTILINE),
        exception_re=re.compile(
            r"\b((?:ActionController|ActiveRecord)::[A-Z][A-Za-z0-9_]+)\b"
        ),
    ),
    Signature(
        family="go_panic", language="go", framework=None,
        required_re=re.compile(
            r"panic:.*goroutine \d+ \[running\]:", re.DOTALL,
        ),
        frame_re=re.compile(r"^\s*([^\s]+\.go):(\d+)", re.MULTILINE),
        exception_re=re.compile(r"panic:\s*(.+?)(?:\n|$)"),
    ),
    Signature(
        family="rust_panic", language="rust", framework=None,
        required_re=re.compile(r"panicked at .+\.rs:\d+:\d+"),
        frame_re=re.compile(r"([^\s']+\.rs):(\d+):(\d+)"),
        exception_re=re.compile(r"panicked at\s+'(.+?)'"),
    ),
    Signature(
        family="express_error", language="javascript", framework="express",
        required_re=re.compile(
            r"at\s+Layer\.handle.*router|node_modules/express",
            re.DOTALL,
        ),
        frame_re=re.compile(
            r"^\s*at\s+([^(]+)\(([^)]+\.js):(\d+):(\d+)\)", re.MULTILINE,
        ),
        exception_re=re.compile(r"\b([A-Z][A-Za-z]*(?:Error))\b"),
    ),
    Signature(
        family="node_stack", language="javascript", framework=None,
        required_re=re.compile(
            r"^\s*at\s+.+?\(.+?\.js:\d+:\d+\)|"
            r"^\s*at\s+.+?\(.+?\.mjs:\d+:\d+\)",
            re.MULTILINE,
        ),
        frame_re=re.compile(
            r"^\s*at\s+([^(]+)\(([^)]+\.(?:js|mjs)):(\d+):(\d+)\)",
            re.MULTILINE,
        ),
        exception_re=re.compile(r"\b([A-Z][A-Za-z]*(?:Error))\b"),
    ),
    Signature(
        family="generic_stack_trace", language="unknown", framework=None,
        required_re=re.compile(
            r"(?:^\s*at\s+.+?:\d+|\bStack trace:\b|Traceback)",
            re.MULTILINE,
        ),
        frame_re=re.compile(r"^\s*at\s+(.+?):(\d+)", re.MULTILINE),
        exception_re=None,
    ),
    Signature(
        family="path_line_leak", language="unknown", framework=None,
        required_re=re.compile(
            r"(?:^|[\s'\"])(/[a-z][^\s:'\"]*\.[a-z]{1,5}):(\d+)",
            re.MULTILINE,
        ),
        frame_re=re.compile(
            r"(?:^|[\s'\"])(/[a-z][^\s:'\"]*):(\d+)",
            re.MULTILINE,
        ),
        exception_re=None,
    ),
)
