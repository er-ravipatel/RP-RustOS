"""P6 design-only Pi input contracts. Does not enable an assembler backend."""
import json
import hashlib
import re
from pathlib import PurePosixPath

from jsonschema import Draft202012Validator


def obj(fields):
    return dict(type='object', properties=fields, required=list(fields), additionalProperties=False)


def make_schema():
    text = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}
    path = {'type': 'string', 'pattern': r'^[a-zA-Z0-9_-]+(?:[./][a-zA-Z0-9_-]+)*$'}
    def constant(value):
        return {'const': value, 'type': 'integer' if type(value) is int else 'string'}
    asset = obj({
        'id': text, 'path': path, 'size_bytes': {'type': 'integer', 'minimum': 1},
        'sha256': sha, 'role': {'enum': ['firmware', 'device-tree', 'license']},
        'url': {'type': 'string', 'pattern': r'^https://raw\.githubusercontent\.com/raspberrypi/firmware/[0-9a-f]{40}/boot/[A-Za-z0-9_./-]+$'},
        'license_ids': {'type': 'array', 'items': text, 'uniqueItems': True},
        'source_package_id': {'type': ['string', 'null']},
    })
    local_file = obj({'path': path, 'sha256': sha, 'size_bytes': {'type': 'integer', 'minimum': 1}})
    source_package = obj({'id': text, 'repository': constant('https://github.com/raspberrypi/linux'),
                          'commit': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
                          'url': {'type': 'string', 'pattern': '^https://codeload.github.com/raspberrypi/linux/tar.gz/[0-9a-f]{40}$'},
                          'archive': local_file, 'build_materials': {'type': 'array', 'minItems': 1, 'items': local_file},
                          'reproduction_evidence': local_file})
    lock = obj({
        'schema_version': constant(2), 'id': constant('rpi-zero2w-boot-assets'),
        'repository': constant('https://github.com/raspberrypi/firmware'),
        'commit': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
        'cache_root': path,
        'assets': {'type': 'array', 'minItems': 5, 'maxItems': 64, 'items': asset},
        'source_packages': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': source_package},
    })
    profile = obj({
        'schema_version': constant(2), 'id': constant('rpi-zero2w-a53'),
        'version': constant('0.1.0'), 'architecture': constant('aarch64'),
        'rust_target': constant('aarch64-unknown-none-softfloat'),
        'base_modules': {'const': ['kernel', 'bsp-rpi-zero2w'], 'type': 'array'},
        'supported_features': {'const': ['serial-console', 'boot-diagnostics'], 'type': 'array'},
        'target': obj({
            'kind': constant('raspberry-pi-zero2w'),
            'boot_contract': constant('zero2w-el2-to-el1-v1'),
            'load_address': constant(0x200000), 'reserved_end': constant(0x400000),
            'active_cores': constant(1),
            'firmware_lock': obj({'path': path, 'sha256': sha}),
            'packaging_recipe': constant('zero2w-mbr-fat32-v1'),
            'verification_methods': {'const': ['image', 'hardware'], 'type': 'array'},
        }),
    })
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'M2 profile and firmware-lock design contracts',
            '$comment': 'Definition container; use validate() for cross-record checks. Not runtime support.',
            '$defs': {'profile': profile, 'firmware_lock': lock}}


def validate(kind, record):
    schema = make_schema()
    Draft202012Validator({'$schema': schema['$schema'], **schema['$defs'][kind]}).validate(record)
    if kind == 'profile':
        _path(record['target']['firmware_lock']['path'])
        return record
    assets = record['assets']
    _path(record['cache_root'])
    packages = record['source_packages']
    if len({p['id'].casefold() for p in packages}) != len(packages):
        raise ValueError('Duplicate source package')
    source_ids = {p['id'] for p in packages}
    for package in packages:
        if package['url'] != f"https://codeload.github.com/raspberrypi/linux/tar.gz/{package['commit']}":
            raise ValueError('Source URL differs from commit')
        files = [package['archive'], package['reproduction_evidence']] + package['build_materials']
        if len({f['path'].casefold() for f in files}) != len(files):
            raise ValueError('Source package path collision')
        for file in files:
            _path(file['path'])
    for field in ('id', 'path', 'url'):
        values = [a[field].casefold() for a in assets]
        if len(values) != len(set(values)):
            raise ValueError('Duplicate asset ' + field)
    by_id = {a['id']: a for a in assets}
    paths = {a['path'] for a in assets}
    required = {'bootcode.bin', 'start.elf', 'fixup.dat', 'bcm2710-rpi-zero-2-w.dtb', 'LICENCE.broadcom', 'COPYING.linux'}
    if not required.issubset(paths):
        raise ValueError('Missing required boot asset')
    for asset in assets:
        _path(asset['path'])
        expected = f"https://raw.githubusercontent.com/raspberrypi/firmware/{record['commit']}/boot/{asset['path']}"
        if asset['url'] != expected:
            raise ValueError('Asset URL does not match commit and path')
        if asset['role'] == 'device-tree':
            if asset['source_package_id'] not in source_ids:
                raise ValueError('Device tree requires a source package')
        elif asset['source_package_id'] is not None:
            raise ValueError('Unexpected source-package binding')
        if asset['role'] == 'license':
            if asset['license_ids']:
                raise ValueError('License records cannot refer recursively to licenses')
        else:
            if not asset['license_ids']:
                raise ValueError('Asset has no license binding')
            for identifier in asset['license_ids']:
                if identifier not in by_id or by_id[identifier]['role'] != 'license':
                    raise ValueError('Invalid license binding')
        expected_role = 'license' if asset['path'] in ('LICENCE.broadcom', 'COPYING.linux') else 'device-tree' if asset['path'].endswith('.dtb') else 'firmware'
        if asset['path'] in required and asset['role'] != expected_role:
            raise ValueError('Wrong required asset role')
        if asset['role'] != 'license':
            expected_notice = 'COPYING.linux' if asset['role'] == 'device-tree' else 'LICENCE.broadcom'
            if expected_notice not in {by_id[i]['path'] for i in asset['license_ids']}:
                raise ValueError('Wrong asset licence notice')
    return record


def _path(value):
    parts = value.split('/')
    if any(p in ('', '.', '..') or p.endswith(('.', ' ')) for p in parts):
        raise ValueError('Unsafe path')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{n}' for p in ('COM', 'LPT') for n in range(1, 10)}
    if any(p.split('.')[0].upper() in reserved for p in parts):
        raise ValueError('Windows reserved path')
    if PurePosixPath(value).is_absolute() or re.search(r'[:\\\x00]', value):
        raise ValueError('Unsafe path')


def validate_pair(profile, lock_bytes):
    """Check the exact lock bytes referenced by a parsed profile; no filesystem IO."""
    validate('profile', profile)
    if hashlib.sha256(lock_bytes).hexdigest() != profile['target']['firmware_lock']['sha256']:
        raise ValueError('Firmware lock bytes differ from profile binding')
    return validate('firmware_lock', json.loads(lock_bytes))


if __name__ == '__main__':
    from pathlib import Path
    destination = Path(__file__).resolve().parents[1] / 'docs/schemas/m2-inputs.schema.json'
    destination.write_text(json.dumps(make_schema(), indent=2) + '\n', encoding='utf-8')
    print('Generated', destination)
