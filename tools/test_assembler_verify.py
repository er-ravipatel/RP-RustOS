"""M1 production-verifier acceptance; retains unique immutable bundles and external reports."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
import unittest
from check_design_contracts import validate

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'tools/assembler/target/debug/rustos.exe'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(operation, path):
    flag = '--manifest' if operation == 'verify' else '--config'
    process = subprocess.run([str(BINARY), operation, '--repo', str(ROOT), flag, str(path), '--format', 'json'], capture_output=True, text=True, timeout=180, cwd=ROOT)
    record = json.loads(process.stdout)
    validate('cli', record)
    if process.stderr:
        raise AssertionError('Unexpected CLI stderr: ' + process.stderr)
    return process, record


def fixture_elf(message=b''):
    words = [0] + [w for byte in message for w in (0x52800000 | (byte << 5), 0xB9000020)] + [0x14000000]
    if len(words) % 2:
        words.append(0xD503201F)
    words[0] = 0x58000001 | (len(words) << 5)
    code = struct.pack('<' + 'I' * len(words), *words) + struct.pack('<Q', 0x09000000)
    header = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF\x02\x01\x01' + bytes(9), 2, 183, 1, 0x40080000, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    segment = struct.pack('<IIQQQQQQ', 1, 5, 0x1000, 0x40080000, 0x40080000, len(code), len(code), 0x1000)
    return (header + segment).ljust(0x1000, b'\0') + code


class VerificationAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ROOT / 'target' / ('verify-' + hex(time.time_ns())[2:])
        cls.root.mkdir(parents=True)
        config = cls.root / 'm1.toml'
        config.write_text('schema_version=1\ntarget="qemu-virt-a53"\nfeatures=["serial-console","boot-diagnostics"]\noutput_dir="bundle"\n', encoding='utf-8')
        process, record = invoke('build', config)
        if process.returncode:
            raise AssertionError(record)
        cls.bundle = cls.root / 'bundle'
        cls.manifest = json.loads((cls.bundle / 'manifest.json').read_bytes())
        cls.checks = []

    @classmethod
    def tearDownClass(cls):
        report = dict(schema_version=1, kind='assembler-production-verifier-acceptance', passed=len(cls.checks) == 8, profile_version='0.1.1', instruction_counting='auto (approved)', checks=cls.checks)
        (cls.root / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print('Retained verifier acceptance:', cls.root)

    def copied(self, name):
        bundle = self.root / name
        bundle.mkdir()
        shutil.copytree(self.bundle / 'source', bundle / 'source')
        for artifact in self.manifest['artifacts']:
            shutil.copyfile(self.bundle / artifact['path'], bundle / artifact['path'])
        shutil.copyfile(self.bundle / 'manifest.json', bundle / 'manifest.json')
        return bundle

    def changed_kernel(self, name, message):
        bundle = self.copied(name)
        manifest = json.loads((bundle / 'manifest.json').read_bytes())
        artifact = next(a for a in manifest['artifacts'] if a['variant'] == 'normal')
        kernel = bundle / artifact['path']
        kernel.write_bytes(fixture_elf(message))
        artifact.update(sha256=digest(kernel), size_bytes=kernel.stat().st_size)
        (bundle / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return bundle, manifest

    def verified(self, bundle, manifest):
        process, record = invoke('verify', bundle / 'manifest.json')
        if record['result'] is not None:
            validate('verification', record['result'], manifest)
            path = bundle.parent / record['evidence'][0]
            self.assertEqual(json.loads(path.read_bytes()), record['result'])
            for step in record['result']['steps']:
                for log in step['logs']:
                    self.assertEqual(digest(path.parent / log['path']), log['sha256'])
        return process, record

    def test_real_bundle_passes_both_scenarios_and_remains_unchanged(self):
        before = {p.relative_to(self.bundle).as_posix(): digest(p) for p in self.bundle.rglob('*') if p.is_file()}
        process, record = self.verified(self.bundle, self.manifest)
        self.assertEqual(process.returncode, 0, record)
        self.assertEqual(self.manifest['target']['version'], '0.1.1')
        self.assertFalse(any(d['code'] == 'CONTROL_TIMER_PROPOSAL' for d in record['result']['diagnostics']))
        report_path = self.bundle.parent / record['evidence'][0]
        launch = json.loads((report_path.parent / 'startup/launch.json').read_bytes())
        self.assertEqual(launch['instruction_counting'], 'auto')
        self.assertIn('shift=auto', launch['arguments'])
        self.assertTrue(record['result']['cleanup']['processes_settled'])
        self.assertEqual(before, {p.relative_to(self.bundle).as_posix(): digest(p) for p in self.bundle.rglob('*') if p.is_file()})
        self.checks.append(dict(name='real snapshot bundle passed both scenarios without bundle mutation', status='passed', report=record))

    def test_artifact_tampering_is_rejected_before_guest(self):
        bundle = self.copied('tampered')
        with (bundle / 'kernel.elf').open('ab') as stream:
            stream.write(b'changed')
        process, record = invoke('verify', bundle / 'manifest.json')
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'ARTIFACT_IDENTITY')
        self.assertIsNone(record['result'])
        self.assertEqual(record['evidence'], [])
        self.checks.append(dict(name='artifact tamper rejected before QEMU', status='passed'))

    def test_unknown_manifest_field_is_rejected(self):
        bundle = self.copied('unknown-field')
        data = json.loads((bundle / 'manifest.json').read_bytes())
        data['executable_command'] = 'untrusted'
        (bundle / 'manifest.json').write_text(json.dumps(data), encoding='utf-8')
        process, record = invoke('verify', bundle / 'manifest.json')
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'MANIFEST_INVALID')
        self.checks.append(dict(name='unknown manifest field rejected', status='passed'))

    def test_duplicate_variants_are_rejected(self):
        bundle = self.copied('duplicate-variant')
        data = json.loads((bundle / 'manifest.json').read_bytes())
        data['artifacts'][1]['variant'] = 'normal'
        (bundle / 'manifest.json').write_text(json.dumps(data), encoding='utf-8')
        process, record = invoke('verify', bundle / 'manifest.json')
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'MANIFEST_INVALID')
        self.checks.append(dict(name='duplicate artifact variant rejected', status='passed'))

    def test_wrong_recipe_is_rejected(self):
        bundle = self.copied('wrong-recipe')
        data = json.loads((bundle / 'manifest.json').read_bytes())
        data['verification_recipe']['sha256'] = '0' * 64
        (bundle / 'manifest.json').write_text(json.dumps(data), encoding='utf-8')
        process, record = invoke('verify', bundle / 'manifest.json')
        self.assertEqual(process.returncode, 3)
        self.assertEqual(record['diagnostics'][0]['code'], 'RECIPE_IDENTITY')
        self.checks.append(dict(name='untrusted recipe identity rejected', status='passed'))

    def test_fault_marker_prevents_success(self):
        bundle, manifest = self.changed_kernel('fault-marker', b'RUSTOS_BOOT_OK\nRUSTOS_UNEXPECTED_PANIC\n')
        process, record = self.verified(bundle, manifest)
        self.assertEqual(process.returncode, 5)
        self.assertEqual(record['result']['steps'][0]['status'], 'failed')
        self.assertEqual(record['result']['steps'][1]['status'], 'skipped')
        self.assertTrue(record['result']['cleanup']['processes_settled'])
        self.checks.append(dict(name='fault marker overrides boot success; owned cleanup settled', status='passed', report=record))

    def test_silent_kernel_times_out_and_skips_panic(self):
        bundle, manifest = self.changed_kernel('silent', b'')
        process, record = self.verified(bundle, manifest)
        self.assertEqual(process.returncode, 6)
        self.assertEqual(record['result']['status'], 'timed_out')
        self.assertEqual(record['result']['steps'][1]['status'], 'skipped')
        self.assertTrue(record['result']['cleanup']['processes_settled'])
        self.checks.append(dict(name='missing marker times out with skipped dependent scenario and settled cleanup', status='passed', report=record))

    def test_unterminated_marker_cannot_pass(self):
        bundle, manifest = self.changed_kernel('unterminated', b'RUSTOS_BOOT_OK')
        process, record = self.verified(bundle, manifest)
        self.assertEqual(process.returncode, 6)
        self.assertIsNone(record['result']['steps'][0]['observed_marker'])
        self.checks.append(dict(name='unterminated marker cannot pass', status='passed', report=record))


if __name__ == '__main__':
    unittest.main(verbosity=2)
