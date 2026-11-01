"""Build-only M1 acceptance. Retains unique test bundles and failed staging for review."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import unittest
from check_design_contracts import validate
from test_kernel import inspect_elf, run_scenario

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'tools/assembler/target/debug/rustos.exe'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(repo, config, environment=None):
    result = subprocess.run([str(BINARY), 'build', '--repo', str(repo), '--config', str(config), '--format', 'json'], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=300)
    record = json.loads(result.stdout)
    validate('cli', record)
    if result.stderr:
        raise AssertionError('Child output contaminated CLI stderr: ' + result.stderr)
    return result, record


class BuildAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ROOT / 'target' / ('p5-build-' + str(time.time_ns()))
        cls.root.mkdir(parents=True)
        cls.config = cls.root / 'm1.toml'
        cls.config.write_text('schema_version = 1\ntarget = "qemu-virt-a53"\nfeatures = ["serial-console", "boot-diagnostics"]\noutput_dir = "bundle"\n', encoding='utf-8')
        environment = dict(os.environ, RUSTFLAGS='--invalid-ambient-flag', RUSTC_WRAPPER='missing-ambient-wrapper.exe', CARGO_PROFILE_RELEASE_PANIC='unwind')
        cls.process, cls.record = invoke(ROOT, cls.config, environment)
        if cls.process.returncode:
            raise AssertionError(json.dumps(cls.record, indent=2))
        cls.bundle = cls.root / 'bundle'
        cls.manifest = json.loads((cls.bundle / 'manifest.json').read_bytes())
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        report = {'schema_version': 1, 'kind': 'assembler-build-development', 'passed': len(cls.results) == 9, 'root': str(cls.root), 'manifest_sha256': digest(cls.bundle / 'manifest.json'), 'checks': cls.results}
        (cls.root / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print('Retained build acceptance evidence:', cls.root)

    def test_manifest_and_snapshot_hashes(self):
        validate('manifest', self.manifest)
        self.assertEqual(self.record['result']['manifest_sha256'], digest(self.bundle / 'manifest.json'))
        self.assertTrue(self.manifest['complete'])
        self.assertIn('VERIFICATION_NOT_RUN',{d['code'] for d in self.record['diagnostics']})
        self.assertEqual({a['variant'] for a in self.manifest['artifacts']}, {'normal', 'panic-test'})
        self.assertFalse((self.bundle / 'incomplete.json').exists())
        for item in self.manifest['inputs']:
            self.assertEqual(item['sha256'], digest(self.bundle / 'source' / item['path']))
        for item in self.manifest['artifacts']:
            path = self.bundle / item['path']
            self.assertEqual(item['sha256'], digest(path))
            self.assertEqual(item['size_bytes'], path.stat().st_size)
            self.assertEqual(path.read_bytes()[:7], b'\x7fELF\x02\x01\x01')
        self.assertNotEqual(self.manifest['artifacts'][0]['sha256'], self.manifest['artifacts'][1]['sha256'])
        self.results.append({'name': 'manifest, source and artifact identities', 'status': 'passed'})

    def test_existing_bundle_is_preserved(self):
        before = {p.relative_to(self.bundle).as_posix(): digest(p) for p in self.bundle.rglob('*') if p.is_file()}
        process, record = invoke(ROOT, self.config)
        self.assertEqual(process.returncode, 4)
        self.assertEqual(record['diagnostics'][0]['code'], 'OUTPUT_EXISTS')
        self.assertEqual(before, {p.relative_to(self.bundle).as_posix(): digest(p) for p in self.bundle.rglob('*') if p.is_file()})
        self.results.append({'name': 'occupied destination preserved', 'status': 'passed'})

    def fixture(self, name):
        repo = self.root / name
        shutil.copytree(self.bundle / 'source', repo)
        return repo, repo / 'configuration.toml'

    def test_failed_compilation_retains_incomplete_evidence(self):
        repo, config = self.fixture('compile-failure')
        with (repo / 'core/kernel/src/main.rs').open('a', encoding='utf-8') as stream:
            stream.write('\ncompile_error!("P5 intentional compile rejection");\n')
        process, record = invoke(repo, config)
        self.assertEqual(process.returncode, 4)
        self.assertEqual(record['diagnostics'][0]['code'], 'TOOL_FAILED')
        self.assertIn('PACKAGING_SKIPPED',{d['code'] for d in record['diagnostics']})
        self.assertFalse((repo / 'bundle').exists())
        evidence = config.parent / record['evidence'][0]
        self.assertFalse(json.loads(evidence.read_bytes())['complete'])
        self.assertTrue((evidence.parent / 'incomplete.json').exists())
        self.assertFalse((evidence.parent / 'manifest.json').exists())
        self.assertIn('P5 intentional compile rejection', (evidence.parent / 'logs/normal/stderr.log').read_text(encoding='utf-8'))
        self.results.append({'name': 'compilation failure retained without published bundle', 'status': 'passed'})

    def test_malformed_workspace_is_rejected_without_panic(self):
        repo, config = self.fixture('workspace-failure')
        (repo / 'Cargo.toml').write_text('[package]\nname = "wrong"\nversion = "0.1.0"\n', encoding='utf-8')
        process, record = invoke(repo, config)
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'UNSUPPORTED_LAYOUT')
        self.assertFalse((repo / 'bundle').exists())
        self.results.append({'name': 'malformed workspace rejected without panic', 'status': 'passed'})

    def test_missing_lockfile_fails_before_creating_staging(self):
        repo, config = self.fixture('missing-lockfile')
        (repo / 'Cargo.lock').unlink()
        process, record = invoke(repo, config)
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'PREREQUISITE_MISSING')
        self.assertEqual(record['evidence'], [])
        self.assertFalse(list(repo.glob('.rustos-staging-*')))
        self.results.append({'name': 'missing lockfile rejected before staging', 'status': 'passed'})

    def test_long_output_path_is_rejected_before_compilation(self):
        repo, config = self.fixture('long-output')
        text = config.read_text(encoding='utf-8')
        config.write_text(text.replace('output_dir = "bundle"', 'output_dir = "' + '/'.join(['deep-output-directory'] * 7) + '/bundle"'), encoding='utf-8')
        process, record = invoke(repo, config)
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'OUTPUT_PATH_TOO_LONG')
        self.assertEqual(record['evidence'], [])
        self.assertFalse(list(repo.rglob('.rustos-staging-*')))
        self.results.append({'name': 'Windows linker path limit rejected before compilation', 'status': 'passed'})

    def test_missing_tool_fails_before_creating_staging(self):
        repo, config = self.fixture('missing-tool')
        process, record = invoke(repo, config, dict(os.environ, PATH=''))
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'TOOL_MISSING')
        self.assertFalse(list(repo.glob('.rustos-staging-*')))
        self.results.append({'name': 'missing host tool rejected before staging', 'status': 'passed'})

    def test_dependency_outside_snapshot_is_rejected(self):
        repo, config = self.fixture('unsafe-dependency')
        manifest = repo / 'core/kernel/Cargo.toml'
        manifest.write_text(manifest.read_text(encoding='utf-8').replace('../../hal', (ROOT / 'hal').as_posix()), encoding='utf-8')
        process, record = invoke(repo, config)
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'UNSAFE_DEPENDENCY')
        self.assertFalse((repo / 'bundle').exists())
        self.results.append({'name': 'dependency escaping snapshot rejected before compiler launch', 'status': 'passed'})

    def test_assembled_artifacts_boot_in_independent_development_harness(self):
        qemu = Path(r'C:\Program Files\qemu\qemu-system-aarch64.exe')
        observations = []
        for artifact in self.manifest['artifacts']:
            path = self.bundle / artifact['path']
            elf = inspect_elf(path)
            marker = 'RUSTOS_BOOT_OK' if artifact['variant'] == 'normal' else 'RUSTOS_EXPECTED_PANIC'
            forbidden = [m for m in ('RUSTOS_BOOT_OK', 'RUSTOS_EXPECTED_PANIC', 'RUSTOS_UNEXPECTED_PANIC', 'RUSTOS_EXCEPTION') if m != marker]
            observed = run_scenario(qemu, path, marker, forbidden)
            self.assertTrue(observed['passed'], observed)
            observations.append({'artifact': artifact['id'], 'elf': elf, **observed})
        self.results.append({'name': 'assembled ELF development emulator smoke checks', 'status': 'passed', 'scope': 'P4 development harness; production verify not implemented', 'observations': observations})


if __name__ == '__main__':
    if os.name != 'nt':
        raise SystemExit('M1 execution currently requires Windows')
    unittest.main(verbosity=2)
