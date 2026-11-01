"""Synthetic contract tests only: no firmware, assembler or hardware execution."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from m2_input_contracts import make_schema, validate, validate_pair

ROOT = Path(__file__).resolve().parents[1]


class M2Inputs(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'docs/examples/m2-contracts'
        self.profile = json.loads((base / 'profile.json').read_text())
        self.lock = json.loads((base / 'firmware-lock.json').read_text())

    def reject(self, kind, value):
        with self.assertRaises((ValueError, ValidationError)):
            validate(kind, value)

    def test_schema_is_valid_and_generated_file_matches(self):
        Draft202012Validator.check_schema(make_schema())
        self.assertEqual(make_schema(), json.loads((ROOT / 'docs/schemas/m2-inputs.schema.json').read_text()))

    def test_positive_profile_and_lock(self):
        validate('profile', self.profile)
        validate('firmware_lock', self.lock)

    def test_exact_lock_byte_binding(self):
        raw = (ROOT / 'docs/examples/m2-contracts/firmware-lock.json').read_bytes()
        validate_pair(self.profile, raw)
        with self.assertRaises(ValueError):
            validate_pair(self.profile, raw + b' ')

    def test_profile_rejects_emulator_unknown_and_mixed_boards(self):
        for field, value in [('emulator', {}), ('base_modules', ['kernel', 'bsp-rpi-zero2w', 'bsp-qemu-virt'])]:
            with self.subTest(field=field):
                p = copy.deepcopy(self.profile)
                p[field] = value
                self.reject('profile', p)

    def test_profile_rejects_changed_boot_assumptions(self):
        for field, value in [('load_address', 0x80000), ('active_cores', 4), ('reserved_end', 0x800000), ('kind', 'qemu')]:
            p = copy.deepcopy(self.profile)
            p['target'][field] = value
            self.reject('profile', p)

    def test_unknown_versions_and_wrong_types(self):
        for kind, record in [('profile', self.profile), ('firmware_lock', self.lock)]:
            for version in (1, 3, '2', True):
                p = copy.deepcopy(record)
                p['schema_version'] = version
                self.reject(kind, p)

    def test_unsafe_profile_paths(self):
        for path in ('../lock.json', '/lock.json', 'C:/lock.json', 'locks\\lock.json', 'locks/CON.json', 'locks//lock.json'):
            p = copy.deepcopy(self.profile)
            p['target']['firmware_lock']['path'] = path
            self.reject('profile', p)

    def test_duplicates_case_collisions(self):
        for field in ('id', 'path', 'url'):
            p = copy.deepcopy(self.lock)
            p['assets'][1][field] = p['assets'][0][field].upper()
            self.reject('firmware_lock', p)

    def test_mutable_wrong_commit_and_path_url(self):
        for url in ('https://example.com/start.elf', self.lock['assets'][0]['url'].replace(self.lock['commit'], 'master'), self.lock['assets'][1]['url']):
            p = copy.deepcopy(self.lock)
            p['assets'][0]['url'] = url
            self.reject('firmware_lock', p)

    def test_missing_or_wrong_role_boot_asset(self):
        p = copy.deepcopy(self.lock)
        p['assets'].pop(0)
        self.reject('firmware_lock', p)
        p = copy.deepcopy(self.lock)
        p['assets'][0]['role'] = 'device-tree'
        self.reject('firmware_lock', p)

    def test_license_required_known_and_not_recursive(self):
        for binding in ([], ['missing'], ['bootcode']):
            p = copy.deepcopy(self.lock)
            p['assets'][0]['license_ids'] = binding
            self.reject('firmware_lock', p)
        p = copy.deepcopy(self.lock)
        p['assets'][-1]['license_ids'] = ['notice']
        self.reject('firmware_lock', p)

    def test_bad_hash_and_empty_asset(self):
        for field, value in [('sha256', 'ABC'), ('size_bytes', 0), ('command', 'run')]:
            p = copy.deepcopy(self.lock)
            p['assets'][0][field] = value
            self.reject('firmware_lock', p)

    def test_source_binding_and_licence_type(self):
        p = copy.deepcopy(self.lock)
        next(a for a in p['assets'] if a['role'] == 'device-tree')['source_package_id'] = None
        self.reject('firmware_lock', p)
        p = copy.deepcopy(self.lock)
        next(a for a in p['assets'] if a['role'] == 'device-tree')['license_ids'] = ['notice']
        self.reject('firmware_lock', p)

    def test_source_commit_and_path_collisions(self):
        p = copy.deepcopy(self.lock); p['source_packages'][0]['commit'] = '3' * 40
        self.reject('firmware_lock', p)
        p = copy.deepcopy(self.lock); p['source_packages'][0]['build_materials'][0] = p['source_packages'][0]['archive']
        self.reject('firmware_lock', p)


if __name__ == '__main__':
    unittest.main()
