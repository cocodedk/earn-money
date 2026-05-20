"""Stub 1.10 — extended framework signature tests.

Covers families added to close 1.18 spec gaps: Laravel Debugbar,
ASP.NET tracing, ELMAH, Yii debug toolbar, JBoss/WildFly console,
plus Apache server-info (mod_info) which 1.10 had as a path hint
only.

Spec 1.18: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/18-framework-debug-pages.md
"""
from __future__ import annotations

import unittest

from ..signals import match_framework_signature


class LaravelDebugbarTests(unittest.TestCase):
    def test_debugbar_marker_matches_high(self) -> None:
        body = (
            "<div data-id=\"phpdebugbar\">Laravel Debugbar</div>"
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "laravel_debugbar"
        assert match.confidence == "high"

    def test_word_debugbar_alone_does_not_match(self) -> None:
        # Generic prose mentioning "debugbar" without phpdebugbar/
        # Laravel context must not flag (false-positive control).
        body = "<p>Tips for using a debugbar in your app.</p>"
        match = match_framework_signature(body, content_type="text/html")
        assert match is None or match.kind != "laravel_debugbar"


class AspNetTracingTests(unittest.TestCase):
    def test_application_trace_marker_matches_high(self) -> None:
        body = (
            "<title>Application Trace</title>\n"
            "<h2>Trace Information</h2>"
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "aspnet_tracing"
        assert match.confidence == "high"


class ElmahTests(unittest.TestCase):
    def test_elmah_error_log_marker_matches_high(self) -> None:
        body = "<title>Error Log for /MyApp</title>ELMAH log page"
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "elmah"
        assert match.confidence == "high"


class YiiDebugTests(unittest.TestCase):
    def test_yii_debugger_marker_matches_high(self) -> None:
        body = (
            '<div id="yii-debug-toolbar">Yii Debugger</div>'
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "yii_debug"
        assert match.confidence == "high"


class JbossWildflyConsoleTests(unittest.TestCase):
    def test_hal_console_marker_matches_high(self) -> None:
        body = "<title>HAL Management Console — WildFly 26</title>"
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "jboss_wildfly_console"
        assert match.confidence == "high"

    def test_jboss_branded_console_also_matches(self) -> None:
        # JBoss EAP 6.x ships HAL with JBoss branding, no WildFly
        # token. Signature shape is AND-only, so we ship two
        # entries with the same kind for the vendor split.
        body = (
            "<title>HAL Management Console — JBoss EAP 6.4</title>"
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "jboss_wildfly_console"


class ApacheServerInfoTests(unittest.TestCase):
    def test_mod_info_page_matches_high(self) -> None:
        body = (
            "<title>Apache Server Information</title>\n"
            "<h1>Server Settings</h1>"
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "apache_server_info"
        assert match.confidence == "high"

    def test_apache_phrase_alone_does_not_match(self) -> None:
        # Server-info legend phrase "Server Settings" alone could
        # appear elsewhere; require both markers.
        body = "<p>Edit your server settings under preferences.</p>"
        match = match_framework_signature(body, content_type="text/html")
        assert match is None or match.kind != "apache_server_info"
