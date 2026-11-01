"""M2 output design contracts; validation is not execution or evidence authentication."""
import hashlib
import json
from datetime import datetime

from jsonschema import Draft202012Validator, FormatChecker
from m2_input_contracts import obj, _path

VARIANTS = ('normal', 'panic-test')
ROLES = ('elf', 'flat-kernel', 'sd-image')
CHECKS = ('geometry', 'allocation', 'directory', 'content-hashes')


def make_schema():
    text = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
    path = {'type': 'string', 'pattern': r'^[A-Za-z0-9_-]+(?:[./][A-Za-z0-9_-]+)*$'}
    stamp = {'type': 'string', 'format': 'date-time', 'pattern': r'(Z|\+00:00)$'}
    boolean = {'type': 'boolean'}
    def arr(item, minimum=0, maximum=4096):
        return {'type': 'array', 'items': item, 'minItems': minimum, 'maxItems': maximum}
    recipe = obj({'id': text, 'version': text, 'sha256': sha})
    identity = obj({'id': text, 'version': text})
    file = obj({'path': path, 'sha256': sha, 'size_bytes': {'type': 'integer', 'minimum': 1}})
    content = obj({**file['properties'], 'origin': {'enum': ['generated', 'kernel', 'locked-asset']}, 'origin_id': text})
    artifact = obj({**file['properties'], 'id': text, 'variant': {'enum': list(VARIANTS)},
                    'role': {'enum': list(ROLES)}, 'derived_from': arr(text, maximum=1),
                    'contents': arr(content, maximum=64)})
    manifest = obj({'schema_version': {'type': 'integer', 'const': 2}, 'bundle_id': text,
                    'created_at': stamp, 'complete': {'type': 'boolean', 'const': True},
                    'target': obj({'id': {'const': 'rpi-zero2w-a53'}, 'kind': {'const': 'raspberry-pi-zero2w'},
                                   'version': {'const': '0.1.0'}, 'architecture': {'const': 'aarch64'},
                                   'rust_target': {'const': 'aarch64-unknown-none-softfloat'}}),
                    'requested_features': {'const': ['serial-console', 'boot-diagnostics']},
                    'resolved_modules': arr(identity, 1), 'inputs': arr(file, 1), 'tools': arr(identity, 1),
                    'firmware_lock_sha256': sha, 'packaging_recipe': recipe,
                    'verification_recipes': obj({'image': recipe, 'hardware': recipe}),
                    'artifacts': arr(artifact, 6, 6)})
    log = obj({'path': path, 'sha256': sha, 'size_bytes': {'type': 'integer', 'minimum': 0}})
    image_step = obj({'artifact_id': text, 'artifact_sha256': sha,
                      'status': {'enum': ['passed', 'failed', 'skipped']},
                      'checks': arr(obj({'id': {'enum': list(CHECKS)}, 'status': {'enum': ['passed', 'failed', 'skipped']}}), 4, 4)})
    hardware_step = obj({'artifact_id': text, 'artifact_sha256': sha, 'variant': {'enum': list(VARIANTS)},
                         'status': {'enum': ['passed', 'failed', 'timed_out', 'cancelled', 'skipped']},
                         'capture_id': text, 'started_at': stamp, 'finished_at': stamp,
                         'deadline_ms': {'type': 'integer', 'minimum': 1, 'maximum': 120000},
                         'operator_declared_image_written': boolean, 'operator_declared_power_cycle': boolean,
                         'buffer_discarded_before_arm': boolean,
                         'observed_marker': {'type': ['string', 'null']}, 'logs': arr(log, 1, 2)})
    common = {'schema_version': {'type': 'integer', 'const': 2}, 'operation': {'const': 'verify'},
              'run_id': text, 'complete': {'type': 'boolean', 'const': True},
              'target': {'const': 'rpi-zero2w-a53'}, 'manifest_sha256': sha,
              'recipe': recipe, 'started_at': stamp, 'finished_at': stamp,
              'status': {'enum': ['passed', 'failed', 'timed_out', 'cancelled']},
              'diagnostics': arr(obj({'severity': {'enum': ['info', 'warning', 'error']}, 'code': text, 'message': text})),
              'cleanup': obj({'serial_closed': boolean, 'helpers_settled': boolean}), 'evidence': arr(log, 1)}
    image = obj({**common, 'method': {'const': 'image'}, 'verification_scope': {'const': 'image'},
                 'payload': obj({'inspector': identity, 'images': arr(image_step, 2, 2)})})
    hardware = obj({**common, 'method': {'const': 'hardware'}, 'verification_scope': {'const': 'hardware'},
                    'payload': obj({'session_id': text, 'board_id': text, 'adapter_id': text, 'port': text,
                                    'serial_settings': {'const': '115200-8N1-no-flow-control'},
                                    'identity_basis': {'const': 'operator-declaration-not-cryptographic-attestation'},
                                    'scenarios': arr(hardware_step, 2, 2)})})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'M2 output design contracts; not runtime support',
            '$defs': {'manifest': manifest, 'image_report': image, 'hardware_report': hardware}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(records, field):
    values = [r[field].casefold() for r in records]
    require(len(values) == len(set(values)), 'Duplicate ' + field)


def structural(kind, record):
    schema = make_schema()
    Draft202012Validator(schema['$defs'][kind], format_checker=FormatChecker()).validate(record)
    def paths(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'path':
                    _path(item)
                else:
                    paths(item)
        elif isinstance(value, list):
            for item in value:
                paths(item)
    paths(record)


def validate_manifest(record):
    structural('manifest', record)
    artifacts = record['artifacts']
    unique(artifacts, 'id')
    unique(artifacts, 'path')
    unique(record['resolved_modules'], 'id')
    unique(record['inputs'], 'path')
    unique(record['tools'], 'id')
    require({m['id'] for m in record['resolved_modules']} == {'kernel', 'hal', 'bsp-rpi-zero2w', 'console-pl011'}, 'Wrong module set')
    require(record['packaging_recipe']['id'] == 'zero2w-mbr-fat32-v1', 'Wrong packaging recipe')
    expected_recipes = {'image': 'zero2w-image-inspect-v1', 'hardware': 'zero2w-serial-capture-v1'}
    require(all(record['verification_recipes'][m]['id'] == r for m, r in expected_recipes.items()), 'Wrong verification recipe')
    lookup = {(a['variant'], a['role']): a for a in artifacts}
    require(set(lookup) == {(v, r) for v in VARIANTS for r in ROLES}, 'Duplicate or missing variant/role')
    for variant in VARIANTS:
        elf, flat, image = [lookup[variant, role] for role in ROLES]
        require(elf['derived_from'] == [] and flat['derived_from'] == [elf['id']] and image['derived_from'] == [flat['id']], 'Wrong derivation')
        require(not elf['contents'] and not flat['contents'], 'Only images have boot inventories')
        require(image['size_bytes'] == 67108864, 'Wrong image size')
        require(flat['size_bytes'] <= 2097152, 'Flat kernel exceeds boot reservation')
        contents = image['contents']
        unique(contents, 'path')
        required = {'bootcode.bin', 'start.elf', 'fixup.dat', 'bcm2710-rpi-zero-2-w.dtb', 'LICENCE.broadcom', 'COPYING.linux', 'config.txt', 'kernel8.img'}
        require(required.issubset({f['path'] for f in contents}), 'Incomplete boot inventory')
        kernel = [f for f in contents if f['origin'] == 'kernel']
        require(len(kernel) == 1 and kernel[0]['path'] == 'kernel8.img' and kernel[0]['origin_id'] == flat['id'] and all(kernel[0][k] == flat[k] for k in ('sha256', 'size_bytes')), 'Image kernel identity mismatch')
        require(next(f for f in contents if f['path'] == 'config.txt')['origin'] == 'generated', 'Config must be generated')
    return record


def moment(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def validate_report(report, manifest_bytes):
    manifest = validate_manifest(json.loads(manifest_bytes))
    kind = 'hardware_report' if report.get('method') == 'hardware' else 'image_report'
    structural(kind, report)
    require(hashlib.sha256(manifest_bytes).hexdigest() == report['manifest_sha256'], 'Wrong manifest binding')
    require(report['recipe'] == manifest['verification_recipes'][report['method']], 'Recipe mismatch')
    require(moment(report['started_at']) <= moment(report['finished_at']), 'Reversed report time')
    unique(report['evidence'], 'path')
    evidence = {f['path']: f for f in report['evidence']}
    images = {a['id']: a for a in manifest['artifacts'] if a['role'] == 'sd-image'}
    steps = report['payload']['scenarios' if kind == 'hardware_report' else 'images']
    unique(steps, 'artifact_id')
    require({s['artifact_id'] for s in steps} == set(images), 'Both images required')
    passing = report['status'] == 'passed'
    if passing:
        require(all(report['cleanup'].values()), 'Unsettled owned resources')
        require(not any(d['severity'] == 'error' for d in report['diagnostics']), 'Passing report has errors')
    if kind == 'hardware_report':
        unique(steps, 'capture_id')
    previous_end = None
    capture_paths = set()
    for step in steps:
        artifact = images[step['artifact_id']]
        require(step['artifact_sha256'] == artifact['sha256'], 'Wrong image identity')
        if passing:
            require(step['status'] == 'passed', 'Incomplete passing scenarios')
        if kind == 'image_report':
            unique(step['checks'], 'id')
            require({c['id'] for c in step['checks']} == set(CHECKS), 'Incomplete image checks')
            if step['status'] == 'passed':
                require(all(c['status'] == 'passed' for c in step['checks']), 'False image pass')
        else:
            require(step['variant'] == artifact['variant'], 'Wrong variant')
            begin, end = moment(step['started_at']), moment(step['finished_at'])
            require(moment(report['started_at']) <= begin <= end <= moment(report['finished_at']), 'Capture outside report')
            if step['status'] == 'passed':
                require((end - begin).total_seconds() * 1000 <= step['deadline_ms'], 'Successful capture exceeds deadline')
            require(previous_end is None or previous_end <= begin, 'Overlapping captures')
            previous_end = end
            require(all(log['path'] in evidence and evidence[log['path']] == log for log in step['logs']), 'Unbound capture log')
            unique(step['logs'], 'path')
            for log in step['logs']:
                require(log['path'].casefold() not in capture_paths, 'Reused capture log')
                capture_paths.add(log['path'].casefold())
            if step['status'] == 'passed':
                expected = 'RUSTOS_BOOT_OK' if step['variant'] == 'normal' else 'RUSTOS_EXPECTED_PANIC'
                require(step['observed_marker'] == expected, 'Wrong exact marker')
                require(all(step[k] for k in ('operator_declared_image_written', 'operator_declared_power_cycle', 'buffer_discarded_before_arm')), 'Missing fresh boot declaration')
                require(any(log['size_bytes'] > 0 for log in step['logs']), 'Empty successful capture')
    return report


if __name__ == '__main__':
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'docs/schemas/m2-outputs.schema.json'
    path.write_text(json.dumps(make_schema(), indent=2) + '\n', encoding='utf-8')
    print('Generated', path)
