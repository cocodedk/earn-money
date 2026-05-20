"""Tests for stub 1.17 FU-2 framework-hint matcher.

Spec §"Strong disclosure indicators" lists framework/runtime traces
as a strong family. FU-2 detects framework PRESENCE (lightweight
fingerprint) — distinct from stub 1.16's full stack-trace
detection. The hint feeds the spec's medium-confidence branch
(error status + framework hint, no full stack/path).
"""
from __future__ import annotations

import unittest

from ..framework_hints import detect_framework_hints


class PythonFrameworksTests(unittest.TestCase):
    def test_django_module_path_detected(self) -> None:
        body = "django.core.exceptions.ImproperlyConfigured: SECRET_KEY missing"
        assert "django" in detect_framework_hints(body)

    def test_flask_werkzeug_detected(self) -> None:
        body = "werkzeug.routing.exceptions.NotFound at /api/x"
        assert "flask" in detect_framework_hints(body)

    def test_fastapi_detected(self) -> None:
        body = "fastapi.exceptions.RequestValidationError: invalid body"
        assert "fastapi" in detect_framework_hints(body)

    def test_starlette_detected(self) -> None:
        body = "starlette.exceptions.HTTPException: 404"
        assert "starlette" in detect_framework_hints(body)

    def test_sqlalchemy_detected(self) -> None:
        body = "sqlalchemy.exc.OperationalError: connection failed"
        assert "sqlalchemy" in detect_framework_hints(body)


class NodeFrameworksTests(unittest.TestCase):
    def test_express_detected(self) -> None:
        body = "at Layer.handle (/srv/app/node_modules/express/lib/router.js:42)"
        assert "express" in detect_framework_hints(body)

    def test_nestjs_detected(self) -> None:
        body = '"@nestjs/core" error: cannot resolve dependency'
        assert "nestjs" in detect_framework_hints(body)


class JvmFrameworksTests(unittest.TestCase):
    def test_spring_detected(self) -> None:
        body = "org.springframework.beans.factory.UnsatisfiedDependencyException"
        assert "spring" in detect_framework_hints(body)

    def test_spring_whitelabel_detected(self) -> None:
        body = "Whitelabel Error Page — there was an unexpected error"
        assert "spring" in detect_framework_hints(body)

    def test_tomcat_detected(self) -> None:
        body = "org.apache.catalina.core.StandardWrapperValve#invoke"
        assert "tomcat" in detect_framework_hints(body)

    def test_jetty_detected(self) -> None:
        body = "org.eclipse.jetty.server.HttpChannel#handle"
        assert "jetty" in detect_framework_hints(body)


class DotNetTests(unittest.TestCase):
    def test_aspnet_core_detected(self) -> None:
        body = "Microsoft.AspNetCore.Diagnostics.DeveloperExceptionPageMiddleware"
        assert "dotnet" in detect_framework_hints(body)

    def test_system_exception_detected(self) -> None:
        body = "System.NullReferenceException: object reference is null"
        assert "dotnet" in detect_framework_hints(body)


class PhpRubyGoTests(unittest.TestCase):
    def test_laravel_detected(self) -> None:
        body = "Illuminate\\Foundation\\Bootstrap\\HandleExceptions::handleError"
        assert "laravel" in detect_framework_hints(body)

    def test_symfony_detected(self) -> None:
        body = "Symfony\\Component\\HttpKernel\\HttpKernel::handle"
        assert "symfony" in detect_framework_hints(body)

    def test_rails_detected(self) -> None:
        body = "ActionController::RoutingError (No route matches [GET] '/x')"
        assert "rails" in detect_framework_hints(body)

    def test_rack_detected(self) -> None:
        body = "Rack::Lint::LintError: header must respond to #each"
        assert "rack" in detect_framework_hints(body)

    def test_go_panic_detected(self) -> None:
        body = "panic: runtime error: invalid memory address\ngoroutine 1 [running]:"
        assert "go" in detect_framework_hints(body)


class MultipleHintsTests(unittest.TestCase):
    def test_returns_all_matches_in_one_body(self) -> None:
        body = (
            "django.core.exceptions.ImproperlyConfigured\n"
            "sqlalchemy.exc.OperationalError"
        )
        hints = detect_framework_hints(body)
        assert "django" in hints
        assert "sqlalchemy" in hints

    def test_each_framework_returned_once(self) -> None:
        body = "django.x django.y django.z"
        hints = detect_framework_hints(body)
        assert hints.count("django") == 1


class NegativeTests(unittest.TestCase):
    def test_plain_text_no_hints(self) -> None:
        assert detect_framework_hints("404 Not Found") == []

    def test_empty_body_returns_empty(self) -> None:
        assert detect_framework_hints("") == []

    def test_word_django_inside_unrelated_text_not_flagged(self) -> None:
        # The literal word "django" without `django.` or `Django\b`
        # context is not a framework signal — avoid false positives on
        # generic prose.
        body = 'review: "ourdjangoapp is great"'
        assert detect_framework_hints(body) == []
