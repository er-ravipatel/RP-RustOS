"""Synthetic M2 outputs, never imported as runtime evidence."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from m2_output_contracts import make_schema, validate_manifest, validate_report, CHECKS

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    recipe = lambda name: dict(id=name, version='0.1.0', sha256='a' * 64)
    file = lambda name, size=1: dict(path=name, sha256=hashlib.sha256(name.encode()).hexdigest(), size_bytes=size)
    manifest = dict(schema_version=2, bundle_id='synthetic-only', created_at='2026-11-01T00:00:00Z', complete=True,
                    target=dict(id='rpi-zero2w-a53', kind='raspberry-pi-zero2w', version='0.1.0', architecture='aarch64', rust_target='aarch64-unknown-none-softfloat'),
                    requested_features=['serial-console', 'boot-diagnostics'],
                    resolved_modules=[dict(id=m, version='0.1.0') for m in ('kernel', 'hal', 'bsp-rpi-zero2w', 'console-pl011')],
                    inputs=[file('source.rs')], tools=[dict(id='fixture-compiler', version='0')],
                    firmware_lock_sha256='b' * 64, packaging_recipe=recipe('zero2w-mbr-fat32-v1'),
                    verification_recipes=dict(image=recipe('zero2w-image-inspect-v1'), hardware=recipe('zero2w-serial-capture-v1')), artifacts=[])
    for variant in ('normal', 'panic-test'):
        elf = dict(**file(variant + '.elf'), id=variant + '-elf', variant=variant, role='elf', derived_from=[], contents=[])
        flat = dict(**file(variant + '.bin'), id=variant + '-flat', variant=variant, role='flat-kernel', derived_from=[elf['id']], contents=[])
        names = ('bootcode.bin', 'start.elf', 'fixup.dat', 'bcm2710-rpi-zero-2-w.dtb', 'LICENCE.broadcom', 'COPYING.linux')
        contents = [dict(**file(n), origin='locked-asset', origin_id=n) for n in names]
        contents += [dict(**file('config.txt'), origin='generated', origin_id='boot-config')]
        contents += [dict(path='kernel8.img', sha256=flat['sha256'], size_bytes=flat['size_bytes'], origin='kernel', origin_id=flat['id'])]
        image = dict(**file(variant + '.img', 67108864), id=variant + '-image', variant=variant, role='sd-image', derived_from=[flat['id']], contents=contents)
        manifest['artifacts'] += [elf, flat, image]
    raw = json.dumps(manifest, sort_keys=True).encode()
    base = dict(schema_version=2, operation='verify', run_id='synthetic-only', complete=True, target='rpi-zero2w-a53',
                manifest_sha256=hashlib.sha256(raw).hexdigest(), started_at='2026-11-01T00:00:00Z', finished_at='2026-11-01T00:00:10Z',
                status='passed', diagnostics=[], cleanup=dict(serial_closed=True, helpers_settled=True),
                evidence=[file('normal.log', 100), file('panic.log', 100)])
    images = [a for a in manifest['artifacts'] if a['role'] == 'sd-image']
    image_report = dict(**copy.deepcopy(base), method='image', verification_scope='image', recipe=manifest['verification_recipes']['image'],
                        payload=dict(inspector=dict(id='fixture-inspector', version='0'), images=[dict(artifact_id=a['id'], artifact_sha256=a['sha256'], status='passed', checks=[dict(id=c, status='passed') for c in CHECKS]) for a in images]))
    scenarios = []
    for i, a in enumerate(images):
        scenarios.append(dict(artifact_id=a['id'], artifact_sha256=a['sha256'], variant=a['variant'], status='passed', capture_id=f'capture-{i}',
                              started_at=f'2026-11-01T00:00:0{i*3+1}Z', finished_at=f'2026-11-01T00:00:0{i*3+2}Z', deadline_ms=10000,
                              operator_declared_image_written=True, operator_declared_power_cycle=True, buffer_discarded_before_arm=True,
                              observed_marker='RUSTOS_BOOT_OK' if i == 0 else 'RUSTOS_EXPECTED_PANIC', logs=[base['evidence'][i]]))
    hardware = dict(**copy.deepcopy(base), method='hardware', verification_scope='hardware', recipe=manifest['verification_recipes']['hardware'],
                    payload=dict(session_id='synthetic-session', board_id='synthetic-board', adapter_id='synthetic-adapter', port='COM999', serial_settings='115200-8N1-no-flow-control',
                                 identity_basis='operator-declaration-not-cryptographic-attestation', scenarios=scenarios))
    return manifest, raw, image_report, hardware


class Outputs(unittest.TestCase):
    def setUp(self):
        self.m, self.raw, self.image, self.hardware = fixtures()

    def reject_report(self, r):
        with self.assertRaises((ValueError, ValidationError)):
            validate_report(r, self.raw)

    def test_positive_both_methods(self):
        validate_manifest(self.m)
        validate_report(self.image, self.raw)
        validate_report(self.hardware, self.raw)

    def test_schema_and_generated_file(self):
        Draft202012Validator.check_schema(make_schema())
        self.assertEqual(make_schema(), json.loads((ROOT / 'docs/schemas/m2-outputs.schema.json').read_text()))

    def test_manifest_duplicate_or_missing_variant(self):
        self.m['artifacts'][3]['variant'] = 'normal'
        with self.assertRaises(ValueError): validate_manifest(self.m)

    def test_swapped_derivation(self):
        self.m['artifacts'][2]['derived_from'] = ['panic-test-flat']
        with self.assertRaises(ValueError): validate_manifest(self.m)

    def test_wrong_kernel_hash(self):
        self.m['artifacts'][2]['contents'][-1]['sha256'] = 'f' * 64
        with self.assertRaises(ValueError): validate_manifest(self.m)

    def test_missing_linux_notice(self):
        self.m['artifacts'][2]['contents'] = [f for f in self.m['artifacts'][2]['contents'] if f['path'] != 'COPYING.linux']
        with self.assertRaises(ValueError): validate_manifest(self.m)

    def test_schema1_and_unknown_fields_rejected(self):
        for key, value in [('schema_version', 1), ('qmp', {})]:
            r = copy.deepcopy(self.image); r[key] = value; self.reject_report(r)

    def test_image_cannot_claim_hardware(self):
        self.image['verification_scope'] = 'hardware'; self.reject_report(self.image)

    def test_changed_manifest_bytes(self):
        with self.assertRaises(ValueError): validate_report(self.image, self.raw + b' ')

    def test_wrong_recipe_and_artifact_hash(self):
        r = copy.deepcopy(self.image); r['recipe']['id'] = 'other'; self.reject_report(r)
        self.image['payload']['images'][0]['artifact_sha256'] = 'f' * 64; self.reject_report(self.image)

    def test_failed_or_missing_image_check(self):
        self.image['payload']['images'][0]['checks'][0]['status'] = 'failed'; self.reject_report(self.image)

    def test_cleanup_and_error_prevent_pass(self):
        r = copy.deepcopy(self.hardware); r['cleanup']['serial_closed'] = False; self.reject_report(r)
        self.image['diagnostics'] = [dict(severity='error', code='FAIL', message='fixture')]; self.reject_report(self.image)

    def test_wrong_variant_marker_or_no_fresh_boot(self):
        for key, value in [('variant', 'panic-test'), ('observed_marker', 'RUSTOS_EXPECTED_PANIC'), ('operator_declared_power_cycle', False), ('buffer_discarded_before_arm', False)]:
            r = copy.deepcopy(self.hardware); r['payload']['scenarios'][0][key] = value; self.reject_report(r)

    def test_reused_capture_and_unbound_log(self):
        r = copy.deepcopy(self.hardware); r['payload']['scenarios'][1]['capture_id'] = 'capture-0'; self.reject_report(r)
        self.hardware['payload']['scenarios'][0]['logs'][0]['sha256'] = 'f' * 64; self.reject_report(self.hardware)

    def test_reversed_or_overlapping_capture(self):
        r = copy.deepcopy(self.hardware); r['finished_at'] = r['started_at']; self.reject_report(r)
        self.hardware['payload']['scenarios'][1]['started_at'] = '2026-11-01T00:00:01Z'; self.reject_report(self.hardware)

    def test_deadline_and_reused_log(self):
        r = copy.deepcopy(self.hardware); r['payload']['scenarios'][0]['deadline_ms'] = 1; self.reject_report(r)
        self.hardware['payload']['scenarios'][1]['logs'] = copy.deepcopy(self.hardware['payload']['scenarios'][0]['logs']); self.reject_report(self.hardware)

    def test_unsafe_or_colliding_artifact_paths(self):
        for path in ('../kernel.elf', 'CON.elf', self.m['artifacts'][0]['path'].upper()):
            m = copy.deepcopy(self.m); m['artifacts'][1]['path'] = path
            with self.assertRaises((ValueError, ValidationError)): validate_manifest(m)


if __name__ == '__main__':
    unittest.main()
