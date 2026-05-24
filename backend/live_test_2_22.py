import os, sys
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.programs.loader import Program
from apps.programs.roe import RoE
from apps.programs.scope import Scope

project, _ = Project.objects.get_or_create(name='fixture-test-2-22')
target, _ = ScanTarget.objects.get_or_create(
    project=project,
    base_url='http://tenant-org-join-abuse-lab:3000',
    defaults={'host': 'tenant-org-join-abuse-lab'},
)
scan_run = ScanRun.objects.create(project=project, stub_slug='2.22')
target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)

roe = RoE(
    max_requests_per_second=10,
    allow_registration_probes=True,
    authorized_test_accounts=['outside'],
)
scope = Scope(
    platform='fixture', slug='tenant-lab',
    policy='rate-limited-OK',
    in_scope=['tenant-org-join-abuse-lab'],
    out_of_scope=[],
)
prog = Program(platform='fixture', slug='tenant-lab', scope=scope, roe=roe)

from apps.stubs.tenant_org_join_abuse import runner as runner_mod
fn = runner_mod.run.__wrapped__

os.environ['FIXTURE_TENANT_ID'] = 'acme'
os.environ['FIXTURE_TENANT_LAB_URL'] = 'http://tenant-org-join-abuse-lab:3000'

fn(scan_run=scan_run, target_run=target_run, program=prog)

from apps.findings.models import Finding
findings = list(Finding.objects.filter(scan_run=scan_run).values('title', 'category', 'confidence', 'data'))
events = list(scan_run.events.values('type', 'subject_type', 'data'))
print("FINDINGS:", findings)
print("EVENTS:", events)
