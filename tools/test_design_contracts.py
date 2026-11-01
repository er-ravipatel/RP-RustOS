"""Synthetic design fixtures, never recorded as assembler runs."""
import copy
import unittest
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        from pip._vendor import tomli as tomllib
from jsonschema import ValidationError
from check_design_contracts import ROOT, SCHEMA, validate
from jsonschema import Draft202012Validator


def passing_fixture():
    return {'schema_version': 1, 'run_id': 'fixture-only', 'complete': True, 'operation': 'verify', 'target': 'qemu-virt-a53', 'manifest_sha256': 'a' * 64, 'verification_scope': 'emulator', 'started_at': '2026-10-31T12:00:00Z', 'finished_at': '2026-10-31T12:00:01Z', 'status': 'passed', 'steps': [{'id': name, 'artifact_id': name, 'artifact_sha256': digit * 64, 'status': 'passed', 'deadline_ms': 10000, 'observed_marker': marker, 'stop_requested': True, 'logs': [{'stream': 'stdout', 'path': name + '.log', 'sha256': 'c' * 64}], 'diagnostics': []} for name, digit, marker in [('startup', '1', 'RUSTOS_BOOT_OK'), ('panic', '2', 'RUSTOS_EXPECTED_PANIC')]], 'cleanup': {'status': 'passed', 'stop_budget_ms': 5000, 'kill_budget_ms': 5000, 'processes_settled': True, 'diagnostics': []}, 'diagnostics': [], 'evidence': ['startup.log', 'panic.log']}


class ContractTests(unittest.TestCase):
    def test_schema_definition(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_toml_examples(self):
        for name, kind in [('m1.toml', 'config'), ('qemu-virt-a53.toml', 'profile'), ('modules.toml', 'catalog')]:
            validate(kind, tomllib.loads((ROOT / 'docs/examples' / name).read_text(encoding='utf-8')))

    def test_structural_invalid_configs(self):
        for name in ('unknown-key', 'schema-version', 'unsafe-output'):
            with self.subTest(name=name), self.assertRaises((ValueError, ValidationError)):
                validate('config', tomllib.loads((ROOT / 'docs/examples/invalid' / (name + '.toml')).read_text(encoding='utf-8')))

    def test_malformed_toml(self):
        with self.assertRaises(tomllib.TOMLDecodeError):
            tomllib.loads((ROOT / 'docs/examples/invalid/malformed.toml').read_text(encoding='utf-8'))

    def test_synthetic_passing_record(self):
        validate('verification', passing_fixture())

    def test_rejects_false_success_cases(self):
        mutations = [
            lambda d: d.update(extra=True),
            lambda d: d.update(complete=False),
            lambda d: d.update(manifest_sha256='bad-hash'),
            lambda d: d.update(finished_at='2026-10-30T12:00:00Z'),
            lambda d: d['steps'].pop(),
            lambda d: d['steps'].__setitem__(1, copy.deepcopy(d['steps'][0])),
            lambda d: d['steps'][0].update(observed_marker='wrong'),
            lambda d: d['steps'][0].update(status='timed_out'),
            lambda d: d['steps'][0].update(stop_requested=False),
            lambda d: d['steps'][0].update(logs=[]),
            lambda d: d['steps'][0]['logs'][0].update(path='../outside.log'),
            lambda d: d['cleanup'].update(status='failed'),
            lambda d: d['cleanup'].update(processes_settled=False),
            lambda d: d['steps'][0].update(deadline_ms=True),
        ]
        for index, mutate in enumerate(mutations):
            data = passing_fixture()
            mutate(data)
            with self.subTest(case=index), self.assertRaises((ValueError, ValidationError)):
                validate('verification', data)

    def test_failed_report_is_not_a_false_pass(self):
        data = passing_fixture()
        data.update(status='failed')
        data['steps'][1].update(status='failed', observed_marker=None, stop_requested=False)
        validate('verification', data)

    def test_final_report_cannot_keep_running_step(self):
        data = passing_fixture()
        data.update(status='failed')
        data['steps'][0]['status'] = 'running'
        with self.assertRaises(ValueError):
            validate('verification', data)

    def test_catalog_duplicate_id(self):
        data = tomllib.loads((ROOT / 'docs/examples/modules.toml').read_text(encoding='utf-8'))
        data['modules'].append(copy.deepcopy(data['modules'][0]))
        with self.assertRaises(ValueError):
            validate('catalog', data)

    def test_artifact_binding_and_variants(self):
        data = passing_fixture()
        manifest = {'schema_version': 1, 'bundle_id': 'fixture-only', 'created_at': data['started_at'], 'complete': True, 'target': {'id': data['target'], 'version': '0.1.0', 'architecture': 'aarch64', 'rust_target': 'aarch64-unknown-none-softfloat'}, 'requested_features': ['boot-diagnostics'], 'resolved_modules': [{'id': 'kernel', 'version': '0.1.0', 'reasons': [{'kind': 'base', 'from': data['target']}]}], 'inputs': [{'path': 'fixture.rs', 'sha256': 'd' * 64}], 'tools': [{'name': 'rustc', 'version': '1.88.0'}], 'artifacts': [{'id': name, 'variant': variant, 'path': name + '.elf', 'sha256': digit * 64, 'size_bytes': 64} for name, variant, digit in [('startup', 'normal', '1'), ('panic', 'panic-test', '2')]], 'verification_recipe': {'id': 'startup-and-panic-v1', 'version': '0.1.0', 'sha256': 'e' * 64}}
        validate('verification', data, manifest)
        wrong = copy.deepcopy(data)
        wrong['steps'][1]['artifact_sha256'] = 'f' * 64
        with self.assertRaises(ValueError):
            validate('verification', wrong, manifest)
        manifest['artifacts'][1]['variant'] = 'normal'
        with self.assertRaises(ValueError):
            validate('manifest', manifest)

    def test_cli_cannot_claim_pass_over_failed_verification(self):
        report = passing_fixture()
        report['status'] = 'failed'
        record = {'schema_version': 1, 'operation': 'verify', 'status': 'passed', 'target': report['target'], 'build_ready': None, 'diagnostics': [], 'result': report, 'evidence': []}
        with self.assertRaises(ValueError):
            validate('cli', record)

    def test_cli_must_use_operation_specific_result(self):
        record = {'schema_version': 1, 'operation': 'build', 'status': 'passed', 'target': 'qemu-virt-a53', 'build_ready': True, 'diagnostics': [], 'result': passing_fixture(), 'evidence': []}
        with self.assertRaises(ValidationError):
            validate('cli', record)


if __name__ == '__main__':
    unittest.main()
