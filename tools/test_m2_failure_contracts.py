"""Synthetic failure records only; no execution indexes are published."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from m2_failure_contracts import make_schema, validate_failure, validate_failed_index
from test_m2_output_contracts import fixtures


def failure():
    return dict(schema_version=2, record_kind='preflight-failure', run_id='synthetic-only', operation='verify', method='image',
                target='rpi-zero2w-a53', complete=False, terminal=True, status='failed',
                started_at='2026-11-01T00:00:00Z', finished_at='2026-11-01T00:00:11Z', manifest_sha256=None,
                diagnostics=[dict(severity='error', code='FIXTURE', message='synthetic failure')],
                cleanup=dict(serial='not_acquired', helpers='not_started'), build_stages=None, attempted_report=None, evidence=[])


class Failures(unittest.TestCase):
    def setUp(self):
        self.f = failure()
        self.manifest, self.raw, self.report, _ = fixtures()

    def reject(self, record):
        with self.assertRaises((ValueError, ValidationError)): validate_failure(record, self.raw)

    def build(self):
        self.f.update(record_kind='build-failure', operation='build', method=None,
                      build_stages=dict(compilation='failed', packaging='skipped', publication='skipped'))
        return self.f

    def recovery(self):
        self.f.update(record_kind='report-recovery', attempted_report=self.report, manifest_sha256=self.report['manifest_sha256'])
        return self.f

    def test_schema_generated_matches(self):
        Draft202012Validator.check_schema(make_schema())
        p = Path(__file__).resolve().parents[1] / 'docs/schemas/m2-failures.schema.json'
        self.assertEqual(make_schema(), json.loads(p.read_text()))

    def test_positive_preflight_build_recovery(self):
        validate_failure(self.f)
        validate_failure(self.build())
        self.f = failure()
        validate_failure(self.recovery(), self.raw)

    def test_failure_never_passed_or_complete(self):
        for key, value in [('status', 'passed'), ('complete', True), ('terminal', False), ('schema_version', 1)]:
            f = copy.deepcopy(self.f); f[key] = value; self.reject(f)

    def test_failure_needs_error(self):
        self.f['diagnostics'][0]['severity'] = 'info'; self.reject(self.f)

    def test_preflight_cannot_claim_execution(self):
        self.f['cleanup']['helpers'] = 'settled'; self.reject(self.f)

    def test_stage_order_and_false_build_pass(self):
        self.build()
        for stages in (dict(compilation='failed', packaging='passed', publication='skipped'), dict(compilation='passed', packaging='passed', publication='passed'), dict(compilation='skipped', packaging='failed', publication='skipped')):
            self.f['build_stages'] = stages; self.reject(self.f)

    def test_wrong_build_method(self):
        self.build()['method'] = 'hardware'; self.reject(self.f)

    def test_recovery_preserves_original_report(self):
        f = self.recovery()
        f['attempted_report']['status'] = 'failed'
        # A failed guest report can also suffer publication failure.
        validate_failure(f, self.raw)
        f['attempted_report']['manifest_sha256'] = 'f' * 64; self.reject(f)

    def test_recovery_cannot_lose_identity(self):
        self.recovery()['run_id'] = 'other'; self.reject(self.f)

    def test_recovery_requires_manifest(self):
        with self.assertRaises(ValueError): validate_failure(self.recovery())

    def test_recovery_target_and_time_binding(self):
        self.recovery()['target'] = None; self.reject(self.f)
        self.f['target'] = 'rpi-zero2w-a53'
        self.f['finished_at'] = '2026-11-01T00:00:01Z'; self.reject(self.f)

    def test_failure_index_binding_and_cannot_promote(self):
        raw = json.dumps(self.f).encode()
        index = dict(schema_version=2, record_kind='failed-operation', id='e-1-3', input_path='E:/fixture/manifest.json', failure_path='E:/fixture/failure.json',
                     failure_sha256=hashlib.sha256(raw).hexdigest(), operation='verify', method='image', status='failed', run_id='synthetic-only')
        validate_failed_index(index, raw)
        with self.assertRaises(ValueError): validate_failed_index(index, raw+b' ')
        index['status'] = 'passed'
        with self.assertRaises(ValidationError): validate_failed_index(index, raw)

    def test_reversed_time_unsafe_evidence(self):
        f = copy.deepcopy(self.f); f['finished_at'] = '2026-10-31T00:00:00Z'; self.reject(f)
        self.f['evidence'] = [dict(path='../log.txt', sha256='a'*64, size_bytes=1)]; self.reject(self.f)


if __name__ == '__main__':
    unittest.main()
