"""Synthetic request/index cases; no serial port or real runtime indexes are used."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from m2_session_contracts import make_schema, parse_verify_request, validate_session, validate_hardware_binding, validate_index
from test_m2_output_contracts import fixtures


class Sessions(unittest.TestCase):
    def setUp(self):
        self.manifest, self.raw, self.image, self.hardware = fixtures()
        self.session = dict(schema_version=2, id='synthetic-session', manifest_sha256=hashlib.sha256(self.raw).hexdigest(),
                            board_id='synthetic-board', adapter_id='synthetic-adapter', port='COM999', serial_settings='115200-8N1-no-flow-control', image_ids=['normal-image', 'panic-test-image'])
        self.report_bytes = json.dumps(self.image).encode()
        self.index = dict(schema_version=2, id='e-1-2', method='image', input_path='E:/fixture/bundle/manifest.json',
                          manifest_sha256=hashlib.sha256(self.raw).hexdigest(), report_path='E:/fixture/reports/report.json', report_sha256=hashlib.sha256(self.report_bytes).hexdigest(),
                          cli=dict(schema_version=1, operation='verify', status='passed', target='rpi-zero2w-a53', build_ready=None, diagnostics=[], result=copy.deepcopy(self.image), evidence=['report.json']))
        self.args = ['verify', '--repo', 'E:/fixture', '--manifest', 'manifest.json']

    def test_schema_generated_matches(self):
        Draft202012Validator.check_schema(make_schema())
        path = Path(__file__).resolve().parents[1] / 'docs/schemas/m2-sessions.schema.json'
        self.assertEqual(make_schema(), json.loads(path.read_text()))

    def test_valid_session_hardware_and_index(self):
        validate_session(self.session, self.raw)
        validate_hardware_binding(self.hardware, self.session, self.raw)
        validate_index(self.index, self.report_bytes, self.raw)

    def test_default_image_and_explicit_hardware(self):
        self.assertEqual(parse_verify_request(self.args)['method'], 'image')
        self.assertEqual(parse_verify_request(self.args + ['--method', 'hardware', '--session', 'session.json'])['method'], 'hardware')

    def test_cli_missing_session_implicit_hardware_unknown_duplicate(self):
        for extra in (['--method', 'hardware'], ['--session', 'session.json'], ['--method', 'emulator'], ['--timeout', '1'], ['--method', 'image', '--method', 'hardware'], ['--repo', 'other']):
            with self.subTest(extra=extra), self.assertRaises(ValueError): parse_verify_request(self.args + extra)

    def test_session_wrong_port_override_and_version(self):
        for key, value in [('port', 'COM0'), ('port', '//./COM1'), ('command', 'run'), ('schema_version', 1), ('serial_settings', '9600-8N1')]:
            s = copy.deepcopy(self.session); s[key] = value
            with self.assertRaises((ValueError, ValidationError)): validate_session(s, self.raw)

    def test_session_wrong_manifest_and_image_ids(self):
        for key, value in [('manifest_sha256', 'f' * 64), ('image_ids', ['normal-image', 'normal-image'])]:
            s = copy.deepcopy(self.session); s[key] = value
            with self.assertRaises((ValueError, ValidationError)): validate_session(s, self.raw)

    def test_hardware_session_mismatch(self):
        for key in ('session_id', 'board_id', 'adapter_id', 'port'):
            r = copy.deepcopy(self.hardware); r['payload'][key] = 'wrong'
            with self.assertRaises(ValueError): validate_hardware_binding(r, self.session, self.raw)
        with self.assertRaises(ValueError): validate_hardware_binding(self.image, self.session, self.raw)

    def test_changed_report_bytes_and_cli_copy(self):
        with self.assertRaises(ValueError): validate_index(self.index, self.report_bytes + b' ', self.raw)
        self.index['cli']['result']['run_id'] = 'other'
        with self.assertRaises(ValueError): validate_index(self.index, self.report_bytes, self.raw)

    def test_method_and_manifest_mismatch(self):
        for key, value in [('method', 'hardware'), ('manifest_sha256', 'f' * 64)]:
            i = copy.deepcopy(self.index); i[key] = value
            with self.assertRaises(ValueError): validate_index(i, self.report_bytes, self.raw)

    def test_index_bad_paths_and_unknown_fields(self):
        for path in ('../report.json', '//server/share/report.json', 'E:/fixture/../report.json', 'E:/fixture/CON.json'):
            i = copy.deepcopy(self.index); i['report_path'] = path
            with self.assertRaises(ValueError): validate_index(i, self.report_bytes, self.raw)
        self.index['extra'] = True
        with self.assertRaises(ValidationError): validate_index(self.index, self.report_bytes, self.raw)

    def test_failed_cli_can_preserve_passed_report_with_reason(self):
        self.index['cli']['status'] = 'failed'
        with self.assertRaises(ValueError): validate_index(self.index, self.report_bytes, self.raw)
        self.index['cli']['diagnostics'] = [dict(severity='error', code='INDEX_PUBLICATION', message='fixture failure', stage='reporting', input=None, field=None, dependency_chain=[])]
        validate_index(self.index, self.report_bytes, self.raw)


if __name__ == '__main__':
    unittest.main()
