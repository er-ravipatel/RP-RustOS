"""Design-only M2 verify request, hardware session and completed-report index contracts."""
import argparse
import copy
import hashlib
import json
from pathlib import PureWindowsPath

from jsonschema import Draft202012Validator
from m2_input_contracts import obj, _path
from m2_output_contracts import require, validate_manifest, validate_report


def make_schema():
    text = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}
    session = obj({'schema_version': {'const': 2, 'type': 'integer'}, 'id': text,
                   'manifest_sha256': sha, 'board_id': text, 'adapter_id': text,
                   'port': {'type': 'string', 'pattern': '^COM[1-9][0-9]{0,3}$'},
                   'serial_settings': {'const': '115200-8N1-no-flow-control'},
                   'image_ids': {'type': 'array', 'items': text, 'minItems': 2, 'maxItems': 2, 'uniqueItems': True}})
    cli = obj({'schema_version': {'const': 1, 'type': 'integer'}, 'operation': {'const': 'verify'},
               'status': {'enum': ['passed', 'failed', 'timed_out', 'cancelled']},
               'target': {'const': 'rpi-zero2w-a53'}, 'build_ready': {'type': 'null'},
               'diagnostics': {'type': 'array', 'items': obj({'severity': {'enum': ['info', 'warning', 'error']}, 'code': text, 'message': text,
                                                           'stage': text, 'input': {'type': ['string', 'null']}, 'field': {'type': ['string', 'null']},
                                                           'dependency_chain': {'type': 'array', 'items': text}})},
               'result': {'type': 'object'}, 'evidence': {'type': 'array', 'items': text, 'minItems': 1}})
    index = obj({'schema_version': {'const': 2, 'type': 'integer'},
                 'id': {'type': 'string', 'pattern': '^e-[0-9a-f]+-[0-9a-f]+$'},
                 'method': {'enum': ['image', 'hardware']}, 'input_path': text,
                 'manifest_sha256': sha, 'report_path': text, 'report_sha256': sha, 'cli': cli})
    build_cli = copy.deepcopy(cli)
    build_cli['properties'].update(operation={'const': 'build'}, status={'const': 'passed'}, build_ready={'type': 'boolean', 'const': True},
                                   result=obj({'manifest_path': text, 'manifest_sha256': sha}))
    build_cli['properties']['evidence']['minItems'] = 0
    build_index = obj({'schema_version': {'const': 2, 'type': 'integer'}, 'record_kind': {'const': 'completed-build'},
                       'id': {'type': 'string', 'pattern': '^e-[0-9a-f]+-[0-9a-f]+$'},
                       'input_path': text, 'manifest_path': text, 'manifest_sha256': sha,
                       'verification_status': {'const': 'not_run'}, 'cli': build_cli})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'M2 session and completed-report index design contracts',
            '$defs': {'session': session, 'completed_index': index, 'completed_build_index': build_index}}


def structural(kind, value):
    Draft202012Validator(make_schema()['$defs'][kind]).validate(value)


def validate_session(session, manifest_bytes):
    structural('session', session)
    manifest = validate_manifest(json.loads(manifest_bytes))
    require(session['manifest_sha256'] == hashlib.sha256(manifest_bytes).hexdigest(), 'Wrong session manifest')
    images = [a['id'] for a in manifest['artifacts'] if a['role'] == 'sd-image']
    require(set(session['image_ids']) == set(images), 'Session needs both exact image IDs')
    return session


def validate_hardware_binding(report, session, manifest_bytes):
    validate_session(session, manifest_bytes)
    validate_report(report, manifest_bytes)
    require(report['method'] == 'hardware', 'Session cannot bind image inspection')
    require(report['payload']['session_id'] == session['id'], 'Wrong session identity')
    for field in ('board_id', 'adapter_id', 'port', 'serial_settings'):
        require(report['payload'][field] == session[field], 'Hardware session mismatch: ' + field)
    return report


def windows_absolute(path):
    parsed = PureWindowsPath(path)
    require(parsed.is_absolute() and len(parsed.drive) == 2 and parsed.drive[1] == ':', 'Require local absolute Windows path')
    require(not path.startswith(('\\\\', '//')), 'UNC/device paths unsupported')
    _path(path[3:].replace('\\', '/'))


def validate_index(index, report_bytes, manifest_bytes):
    """Byte binding only: runtime must additionally check actual opened-file identity."""
    structural('completed_index', index)
    windows_absolute(index['input_path'])
    windows_absolute(index['report_path'])
    require(index['input_path'].casefold() != index['report_path'].casefold(), 'Manifest and report collide')
    report = validate_report(json.loads(report_bytes), manifest_bytes)
    require(index['method'] == report['method'], 'Wrong index method')
    require(index['manifest_sha256'] == report['manifest_sha256'], 'Wrong indexed manifest')
    require(hashlib.sha256(report_bytes).hexdigest() == index['report_sha256'], 'Wrong indexed report bytes')
    cli = index['cli']
    require(cli['result'] == report and cli['target'] == report['target'], 'CLI result differs from report')
    # Reporting/index failures can turn a passed guest report into a failed CLI result.
    require(cli['status'] == report['status'] or cli['status'] == 'failed', 'CLI contradicts report')
    if cli['status'] == 'passed':
        require(not any(d['severity'] == 'error' for d in cli['diagnostics']), 'Passing CLI has error')
    if cli['status'] != report['status']:
        require(any(d['severity'] == 'error' for d in cli['diagnostics']), 'Failed CLI needs failure diagnostic')
    for path in cli['evidence']:
        _path(path)
    require(len(set(p.casefold() for p in cli['evidence'])) == len(cli['evidence']), 'Duplicate CLI evidence')
    return index


def validate_build_index(index, manifest_bytes):
    structural('completed_build_index', index)
    validate_manifest(json.loads(manifest_bytes))
    windows_absolute(index['input_path']); windows_absolute(index['manifest_path'])
    require(index['input_path'].casefold() != index['manifest_path'].casefold(), 'Input/manifest path collision')
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    require(index['manifest_sha256'] == digest, 'Build manifest bytes changed')
    require(index['cli']['result'] == {'manifest_path': index['manifest_path'], 'manifest_sha256': digest}, 'Build result/index mismatch')
    require(not any(d['severity'] == 'error' for d in index['cli']['diagnostics']), 'Passing build has error')
    for path in index['cli']['evidence']:
        _path(path)
    return index


class ContractParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def parse_verify_request(args):
    """Proposed syntax parser for fixtures, not the rustos executable."""
    flags = [a.split('=', 1)[0] for a in args if a.startswith('--')]
    require(len(flags) == len(set(flags)), 'Duplicate option')
    parser = ContractParser(add_help=False, allow_abbrev=False)
    parser.add_argument('operation', choices=['verify'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--method', choices=['image', 'hardware'], default='image')
    parser.add_argument('--session')
    parser.add_argument('--format', choices=['text', 'json'], default='text')
    result = parser.parse_args(args)
    require((result.method == 'hardware') == (result.session is not None), 'Hardware requires session; image forbids session')
    require(all(value.strip() for value in (result.repo, result.manifest)), 'Empty path argument')
    if result.session is not None:
        require(bool(result.session.strip()), 'Empty session path')
    return vars(result)


if __name__ == '__main__':
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'docs/schemas/m2-sessions.schema.json'
    path.write_text(json.dumps(make_schema(), indent=2) + '\n', encoding='utf-8')
    print('Generated', path)
