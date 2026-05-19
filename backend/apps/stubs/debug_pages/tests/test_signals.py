"""Pure-function tests for stub 1.10 signal detectors.

Three signal families per spec §Detection logic:
- match_framework_signature: returns the (kind, confidence_hint)
  for the strongest matching framework marker, or None.
- find_stack_trace_markers: returns spec leaked_data_classes labels
  found in the body (stack_trace, absolute_path).
- find_env_leak_markers: returns spec leaked_data_classes labels for
  environment-variable / secret-like markers.
"""
from __future__ import annotations

import unittest

from ..signals import (
    find_env_leak_markers,
    find_stack_trace_markers,
    match_framework_signature,
)


class PhpInfoTests(unittest.TestCase):
    def test_title_and_version_marker_matches_phpinfo_high(self) -> None:
        body = "<title>phpinfo()</title>\n<h1>PHP Version 8.2.5</h1>"
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "phpinfo"
        assert match.confidence == "high"

    def test_version_alone_does_not_match_phpinfo(self) -> None:
        # Generic blog post mentioning PHP Version — not phpinfo.
        body = "<p>Upgrade your site to PHP Version 8 today.</p>"
        match = match_framework_signature(body, content_type="text/html")
        assert match is None or match.kind != "phpinfo"


class SymfonyProfilerTests(unittest.TestCase):
    def test_sf_toolbar_marker_matches_high(self) -> None:
        body = '<div class="sf-toolbar"><span>Symfony Profiler</span></div>'
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "symfony_profiler"
        assert match.confidence == "high"


class DjangoDebugToolbarTests(unittest.TestCase):
    def test_djdebug_marker_matches_high(self) -> None:
        body = '<div id="djDebug" data-store-id="abc">SQLPanel</div>'
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "django_debug_toolbar"
        assert match.confidence == "high"


class WerkzeugTests(unittest.TestCase):
    def test_werkzeug_debugger_marker_matches_high(self) -> None:
        body = "<title>Werkzeug Debugger</title>\nConsole Locked"
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "werkzeug_debugger"
        assert match.confidence == "high"


class GoPprofTests(unittest.TestCase):
    def test_pprof_index_matches_high(self) -> None:
        body = (
            "<h1>/debug/pprof/</h1>\n"
            "<p>Types of profiles available:</p>\n"
            "goroutine heap threadcreate cmdline"
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "go_pprof"
        assert match.confidence == "high"


class SpringActuatorTests(unittest.TestCase):
    def test_actuator_json_links_matches_high(self) -> None:
        body = '{"_links":{"self":{"href":"/actuator"},"health":{"href":"/actuator/health"}}}'
        match = match_framework_signature(
            body, content_type="application/json",
        )
        assert match is not None
        assert match.kind == "spring_actuator"
        assert match.confidence == "high"


class ApacheServerStatusTests(unittest.TestCase):
    def test_apache_server_status_matches_high(self) -> None:
        body = (
            "<h1>Apache Server Status for localhost</h1>\n"
            "Server Version: Apache/2.4\nCurrent Time: ..."
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "apache_server_status"
        assert match.confidence == "high"


class LaravelTests(unittest.TestCase):
    def test_telescope_marker_matches_high(self) -> None:
        body = '<div id="telescope"><span>Laravel Telescope</span></div>'
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "laravel_telescope"
        assert match.confidence == "high"

    def test_ignition_marker_matches_high(self) -> None:
        body = '<div class="ignition"><h1>Whoops</h1>_ignition</div>'
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "laravel_ignition"


class RailsInfoTests(unittest.TestCase):
    def test_rails_routes_marker_matches_high(self) -> None:
        body = (
            "<title>Routes</title>\n"
            "Controller#Action: rails/info/routes\n"
            "Rails::InfoController"
        )
        match = match_framework_signature(body, content_type="text/html")
        assert match is not None
        assert match.kind == "rails_info"


class NoMatchTests(unittest.TestCase):
    def test_generic_marketing_page_no_match(self) -> None:
        body = "<h1>Welcome to our site</h1><p>Buy our products!</p>"
        match = match_framework_signature(body, content_type="text/html")
        assert match is None

    def test_empty_body_no_match(self) -> None:
        match = match_framework_signature("", content_type="text/html")
        assert match is None


class StackTraceMarkerTests(unittest.TestCase):
    def test_python_traceback_yields_stack_trace_marker(self) -> None:
        body = (
            'Traceback (most recent call last):\n'
            '  File "/app/views.py", line 12, in handle\n'
            "    raise ValueError"
        )
        markers = find_stack_trace_markers(body)
        assert "stack_trace" in markers
        assert "absolute_path" in markers

    def test_java_stack_trace_yields_stack_trace_marker(self) -> None:
        body = (
            "Exception in thread main java.lang.NullPointerException\n"
            "    at org.example.Foo.bar(Foo.java:42)"
        )
        markers = find_stack_trace_markers(body)
        assert "stack_trace" in markers

    def test_generic_body_yields_no_stack_trace_marker(self) -> None:
        markers = find_stack_trace_markers("<h1>Welcome</h1>")
        assert markers == []

    def test_empty_body_returns_empty_list(self) -> None:
        assert find_stack_trace_markers("") == []

    def test_node_modules_path_yields_absolute_path(self) -> None:
        # Path leakage without an explicit traceback header is still
        # an absolute_path leak per spec leaked_data_classes.
        body = "Error: cannot find /home/app/node_modules/express/index.js"
        markers = find_stack_trace_markers(body)
        assert "absolute_path" in markers


class EnvLeakMarkerTests(unittest.TestCase):
    def test_database_url_yields_secret_marker(self) -> None:
        body = "DATABASE_URL=postgres://user:pass@localhost/db\nDEBUG=True"
        markers = find_env_leak_markers(body)
        assert "secret_like_value" in markers
        assert "environment_variable" in markers

    def test_secret_key_yields_secret_marker(self) -> None:
        body = 'SECRET_KEY="abc123"\nAPP_ENV=production'
        markers = find_env_leak_markers(body)
        assert "secret_like_value" in markers

    def test_aws_access_key_yields_secret_marker(self) -> None:
        body = "AWS_ACCESS_KEY_ID=AKIAFAKE\nNODE_ENV=development"
        markers = find_env_leak_markers(body)
        assert "secret_like_value" in markers
        assert "environment_variable" in markers

    def test_node_env_alone_yields_env_var_only(self) -> None:
        # NODE_ENV is an env var, not a secret-like value.
        body = "NODE_ENV=development"
        markers = find_env_leak_markers(body)
        assert "environment_variable" in markers
        assert "secret_like_value" not in markers

    def test_generic_body_yields_no_env_markers(self) -> None:
        markers = find_env_leak_markers("<h1>Welcome</h1>")
        assert markers == []

    def test_empty_body_returns_empty_list(self) -> None:
        assert find_env_leak_markers("") == []
