"""Synthetic successful build and strict dispatch cases."""
import copy
import hashlib
import unittest
from jsonschema import ValidationError
from m2_index_dispatch import validate_index_record
import test_m2_session_contracts as session_fixtures
from test_m2_failure_contracts import failure
import json


class Dispatch(unittest.TestCase):
    def setUp(self):
        fixture = session_fixtures.Sessions(); fixture.setUp()
        self.raw = fixture.raw
        self.verify = fixture.index; self.report = fixture.report_bytes
        self.build = dict(schema_version=2, record_kind='completed-build', id='e-1-4', input_path='E:/fixture/rustos.toml', manifest_path='E:/fixture/bundle/manifest.json',
                          manifest_sha256=hashlib.sha256(self.raw).hexdigest(), verification_status='not_run',
                          cli=dict(schema_version=1, operation='build', status='passed', target='rpi-zero2w-a53', build_ready=True, diagnostics=[], evidence=[],
                                   result=dict(manifest_path='E:/fixture/bundle/manifest.json', manifest_sha256=hashlib.sha256(self.raw).hexdigest())))

    def test_dispatch_build_verify_failure(self):
        validate_index_record(self.build, manifest_bytes=self.raw)
        validate_index_record(self.verify, manifest_bytes=self.raw, record_bytes=self.report)
        raw = json.dumps(failure()).encode()
        index = dict(schema_version=2, record_kind='failed-operation', id='e-1-5', input_path='E:/fixture/manifest.json', failure_path='E:/fixture/failure.json',
                     failure_sha256=hashlib.sha256(raw).hexdigest(), operation='verify', method='image', status='failed', run_id='synthetic-only')
        validate_index_record(index, record_bytes=raw)

    def test_build_cannot_claim_verification(self):
        self.build['verification_status'] = 'passed'
        with self.assertRaises(ValidationError): validate_index_record(self.build, manifest_bytes=self.raw)

    def test_build_wrong_bytes_or_result(self):
        with self.assertRaises(ValueError): validate_index_record(self.build, manifest_bytes=self.raw+b' ')
        self.build['cli']['result']['manifest_path'] = 'E:/other/manifest.json'
        with self.assertRaises(ValueError): validate_index_record(self.build, manifest_bytes=self.raw)

    def test_build_unknown_fields_and_error(self):
        b = copy.deepcopy(self.build); b['method'] = 'hardware'
        with self.assertRaises(ValidationError): validate_index_record(b, manifest_bytes=self.raw)
        self.build['cli']['diagnostics'] = [dict(severity='error', code='FAIL', message='fixture', stage='build', input=None, field=None, dependency_chain=[])]
        with self.assertRaises(ValueError): validate_index_record(self.build, manifest_bytes=self.raw)

    def test_unknown_version_kind_or_missing_bytes(self):
        for patch in ({'schema_version': 1}, {'schema_version': True}, {'record_kind': 'other'}):
            b = copy.deepcopy(self.build); b.update(patch)
            with self.assertRaises(ValueError): validate_index_record(b, manifest_bytes=self.raw)
        with self.assertRaises(ValueError): validate_index_record(self.build)
        with self.assertRaises(ValueError): validate_index_record(self.verify, manifest_bytes=self.raw)


if __name__ == '__main__':
    unittest.main()
