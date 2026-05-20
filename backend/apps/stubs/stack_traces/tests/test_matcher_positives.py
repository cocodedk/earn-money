"""Positive tests for stub 1.16 matcher — one class per language.

Mirrors the spec's pass/fail positive assertions: Python, Django,
Java, Spring, Node, .NET, PHP, Go, JSON-with-stack-field.
"""
from __future__ import annotations

import unittest

from ..matcher import detect_stack_traces


def _families(body: str, ct: str = "text/html") -> set[str]:
    return {m.family for m in detect_stack_traces(body, ct)}


class PythonTests(unittest.TestCase):
    def test_traceback_detected(self) -> None:
        body = (
            "Traceback (most recent call last):\n"
            '  File "/app/views.py", line 42, in get\n'
            "    user = User.objects.get(pk=pk)\n"
            "django.core.exceptions.ObjectDoesNotExist: not found\n"
        )
        matches = detect_stack_traces(body, "text/html")
        families = {m.family for m in matches}
        assert "python_traceback" in families
        py = next(m for m in matches if m.family == "python_traceback")
        assert py.language == "python"
        assert py.stack_frame_count >= 1
        assert "ObjectDoesNotExist" in (py.exception_type or "")

    def test_django_debug_strong_match(self) -> None:
        body = (
            "<title>Django Debug</title>"
            "Request Method: GET\n"
            "Exception Type: ValueError\n"
            "Exception Value: bad input\n"
            "Traceback (most recent call last):\n"
            '  File "/app/x.py", line 7, in run\n'
        )
        families = _families(body)
        assert "django_debug" in families


class JavaTests(unittest.TestCase):
    def test_java_stack_with_two_frames(self) -> None:
        body = (
            "java.lang.NullPointerException: thing\n"
            "\tat com.example.App.run(App.java:42)\n"
            "\tat com.example.App.main(App.java:10)\n"
        )
        matches = detect_stack_traces(body, "text/plain")
        java = next(m for m in matches if m.family == "java_stack")
        assert java.language == "java"
        assert java.stack_frame_count >= 2
        assert "NullPointerException" in (java.exception_type or "")

    def test_spring_whitelabel_detected(self) -> None:
        body = (
            "<html><body>Whitelabel Error Page</body></html>\n"
            "org.springframework.web.HttpRequestMethodNotSupportedException\n"
            "\tat org.springframework.web.servlet.DispatcherServlet."
            "doDispatch(DispatcherServlet.java:1099)\n"
        )
        assert "spring_boot_error" in _families(body)


class NodeTests(unittest.TestCase):
    def test_node_stack_with_typeerror(self) -> None:
        body = (
            "TypeError: Cannot read property 'x' of undefined\n"
            "    at handler (/srv/app/server.js:42:13)\n"
            "    at Layer.handle [as handle_request] "
            "(/srv/app/node_modules/express/lib/router/layer.js:95:5)\n"
        )
        matches = detect_stack_traces(body, "text/plain")
        node = next(m for m in matches if m.family == "node_stack")
        assert node.language == "javascript"
        assert "TypeError" in (node.exception_type or "")
        assert node.stack_frame_count >= 1


class DotnetTests(unittest.TestCase):
    def test_dotnet_stack(self) -> None:
        body = (
            "System.InvalidOperationException: thing\n"
            "Stack Trace:\n"
            "   at Acme.Web.Controllers.HomeController.Index() "
            "in /src/HomeController.cs:line 42\n"
        )
        matches = detect_stack_traces(body, "text/html")
        net = next(m for m in matches if m.family == "dotnet_stack")
        assert net.language == "dotnet"
        assert "InvalidOperationException" in (net.exception_type or "")


class PhpTests(unittest.TestCase):
    def test_php_fatal_error(self) -> None:
        body = (
            "Fatal error: Uncaught Exception: thing in /var/www/index.php:7\n"
            "Stack trace:\n"
            "#0 /var/www/index.php(7): trigger()\n"
            "#1 {main}\n"
        )
        matches = detect_stack_traces(body, "text/html")
        php = next(m for m in matches if m.family == "php_stack")
        assert php.language == "php"
        assert php.stack_frame_count >= 1


class GoTests(unittest.TestCase):
    def test_go_panic(self) -> None:
        body = (
            "panic: runtime error: index out of range\n"
            "\n"
            "goroutine 1 [running]:\n"
            "main.run(...)\n"
            "\t/src/main.go:42 +0x42\n"
        )
        matches = detect_stack_traces(body, "text/plain")
        go = next(m for m in matches if m.family == "go_panic")
        assert go.language == "go"


class JsonStackFieldTests(unittest.TestCase):
    def test_json_stack_field_detected(self) -> None:
        body = (
            '{"error": "bad", "message": "fail",'
            ' "stack": "Error: fail\\n    at run (/srv/app.js:1:1)"}'
        )
        matches = detect_stack_traces(body, "application/json")
        families = {m.family for m in matches}
        assert families & {"node_stack", "generic_stack_trace"}
