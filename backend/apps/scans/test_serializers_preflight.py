"""Tests for ScanRunSerializer.validate — preflight ValueError path.

The preflight gate raises ValueError when a target URL is malformed
(empty, non-HTTP scheme, no hostname). This exercises lines 95-96 of
serializers.py which re-raise as a DRF ValidationError with the key
"target_ids" and prefix "malformed target URL".
"""
from __future__ import annotations

import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from django.test import override_settings, TestCase

from apps.projects.models import Project
from apps.stubs.tests import write_stub
from apps.targets.models import ScanTarget
from apps.scans.serializers import ScanRunSerializer


def _cookbook_dir():
    d = tempfile.mkdtemp()
    write_stub(
        Path(d),
        phase=1, spec=1, phase_slug="information-gathering",
        slug="framework-detection",
        title="Framework detection",
        phase_title="Information gathering",
    )
    return d


class ScanRunSerializerPreflightValueErrorTests(TestCase):
    """ValueError from preflight_scan_run surfaces as a 400 field error."""

    def setUp(self):
        self.cookbook_dir = _cookbook_dir()
        self._override = override_settings(COOKBOOK_ROOT=self.cookbook_dir)
        self._override.enable()
        self.project = Project.objects.create(name="acme")
        self.target = ScanTarget.objects.create(
            project=self.project,
            base_url="https://x.example",
            host="x.example",
        )

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self.cookbook_dir, ignore_errors=True)

    def test_preflight_value_error_becomes_validation_error(self):
        """When preflight_scan_run raises ValueError (malformed URL),
        the serializer converts it to a DRF ValidationError with the
        'target_ids' key and 'malformed target URL' prefix."""
        data = {
            "project": str(self.project.id),
            "stub_slug": "1.1",
            "target_ids": [str(self.target.id)],
        }
        with patch(
            "apps.scans.serializers.preflight_scan_run",
            side_effect=ValueError("URL has no hostname: 'ftp://bad'"),
        ):
            serializer = ScanRunSerializer(data=data)
            assert not serializer.is_valid()
            assert "target_ids" in serializer.errors
            msg = str(serializer.errors["target_ids"])
            assert "malformed target URL" in msg
