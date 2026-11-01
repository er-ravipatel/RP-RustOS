"""Black-box acceptance checks for the compiled P3 CLI; no OS builds or guest runs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from check_design_contracts import validate

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'tools/assembler/target/debug' / ('rustos.exe' if os.name == 'nt' else 'rustos')


class CliAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rustos-p3-cli-')
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / 'docs/examples', self.repo / 'inputs')
        for directory in ('profiles', 'catalog', 'recipes'):
            shutil.copytree(ROOT / directory, self.repo / directory)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, config='inputs/m1.toml', operation='plan', extra=None):
        command = [str(BINARY), operation, '--repo', str(self.repo), '--config', str(self.repo / config), '--format', 'json'] + (extra or [])
        snapshot = {p.relative_to(self.repo): p.read_bytes() for p in self.repo.rglob('*') if p.is_file() and '.rustos' not in p.parts}
        environment = dict(os.environ, PATH='')
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, env=environment, cwd=ROOT)
        record = json.loads(result.stdout)
        validate('cli', record)
        self.assertEqual(snapshot, {p.relative_to(self.repo): p.read_bytes() for p in self.repo.rglob('*') if p.is_file() and '.rustos' not in p.parts})
        if operation in ('validate', 'plan'):
            self.assertFalse((self.repo / '.rustos').exists())
        self.assertFalse((self.repo / 'inputs/out').exists())
        self.assertEqual(result.stderr, '')
        return result, record

    def test_all_documented_fixtures(self):
        cases = json.loads((ROOT / 'docs/examples/fixture-expectations.json').read_text())['cases']
        original = (self.repo / 'catalog/modules.toml').read_text()
        for case in cases:
            with self.subTest(case=case['id']):
                catalog = original
                if case['id'] == 'missing-module':
                    start = catalog.index('[[modules]]\nid = "hal"')
                    end = catalog.index('[[modules]]', start + 1)
                    catalog = catalog[:start] + catalog[end:]
                elif case['id'] == 'dependency-cycle':
                    catalog = catalog.replace('requires = []', 'requires = ["kernel"]', 1)
                elif case['id'] in ('selected-conflict', 'architecture-mismatch'):
                    start = catalog.index('id = "console-pl011"')
                    end = catalog.index('[[modules]]', start)
                    block = catalog[start:end]
                    block = block.replace('conflicts = []', 'conflicts = ["kernel"]') if case['id'] == 'selected-conflict' else block.replace('architectures = ["aarch64"]', 'architectures = ["x86_64"]')
                    catalog = catalog[:start] + block + catalog[end:]
                (self.repo / 'catalog/modules.toml').write_text(catalog)
                result, record = self.run_cli('inputs/' + case['config'])
                if 'expected_error' in case:
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(record['diagnostics'][0]['code'], case['expected_error'])
                else:
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(record['result']['build_order'], case['expected_modules'])
                    self.assertEqual(record['build_ready'], case['expected_build_ready'])

    def test_input_identity_and_recipe_binding(self):
        result, record = self.run_cli()
        self.assertEqual(result.returncode, 0)
        for identity in record['result']['inputs']:
            self.assertEqual(identity['sha256'], hashlib.sha256(Path(identity['path']).read_bytes()).hexdigest())
        self.assertEqual(record['result']['verification_recipe']['sha256'], hashlib.sha256((self.repo / 'recipes/startup-and-panic-v1.toml').read_bytes()).hexdigest())

    def test_validate_and_plan_agree_on_readiness(self):
        result, validation = self.run_cli(operation='validate')
        self.assertEqual(result.returncode, 0)
        _, plan = self.run_cli()
        self.assertEqual(validation['build_ready'], plan['build_ready'])
        self.assertEqual(validation['result']['missing_prerequisites'], plan['result']['missing_prerequisites'])

    def test_build_rejects_missing_sources_and_verify_remains_unimplemented(self):
        result, record = self.run_cli(operation='build')
        self.assertEqual(result.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'PREREQUISITE_MISSING')
        result, record = self.run_cli(operation='verify')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(record['diagnostics'][0]['code'], 'INVOCATION')

    def test_duplicate_cli_option_fails_as_json(self):
        result, record = self.run_cli(extra=['--repo', str(self.repo)])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(record['diagnostics'][0]['code'], 'INVOCATION')


if __name__ == '__main__':
    if not BINARY.is_file():
        raise SystemExit('Build the host tool first: cargo build --manifest-path tools/assembler/Cargo.toml --locked')
    unittest.main()
