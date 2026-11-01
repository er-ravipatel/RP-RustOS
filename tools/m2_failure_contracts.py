"""Design-only terminal failures, recovery evidence and failed execution indexes."""
import hashlib
import json
from datetime import datetime

from jsonschema import Draft202012Validator, FormatChecker
from m2_input_contracts import obj, _path
from m2_output_contracts import require, validate_report, moment
from m2_session_contracts import windows_absolute


def make_schema():
    text = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
    timestamp = {'type': 'string', 'format': 'date-time', 'pattern': r'(Z|\+00:00)$'}
    nullable_sha = {'anyOf': [sha, {'type': 'null'}]}
    failure = obj({'schema_version': {'const': 2, 'type': 'integer'},
                   'record_kind': {'enum': ['preflight-failure', 'build-failure', 'report-recovery']},
                   'run_id': text, 'operation': {'enum': ['build', 'verify']},
                   'method': {'enum': [None, 'image', 'hardware']},
                   'target': {'enum': [None, 'rpi-zero2w-a53']},
                   'complete': {'const': False, 'type': 'boolean'},
                   'terminal': {'const': True, 'type': 'boolean'},
                   'status': {'enum': ['failed', 'timed_out', 'cancelled']},
                   'started_at': timestamp, 'finished_at': timestamp,
                   'manifest_sha256': nullable_sha,
                   'diagnostics': {'type': 'array', 'minItems': 1, 'items': obj({'severity': {'enum': ['info', 'warning', 'error']}, 'code': text, 'message': text})},
                   'cleanup': obj({'serial': {'enum': ['not_acquired', 'closed', 'unconfirmed']},
                                   'helpers': {'enum': ['not_started', 'settled', 'unconfirmed']}}),
                   'build_stages': {'anyOf': [{'type': 'null'}, obj({k: {'enum': ['passed', 'failed', 'timed_out', 'cancelled', 'skipped']} for k in ('compilation', 'packaging', 'publication')})]},
                   'attempted_report': {'type': ['object', 'null']},
                   'evidence': {'type': 'array', 'items': obj({'path': text, 'sha256': sha, 'size_bytes': {'type': 'integer', 'minimum': 0}})}})
    index = obj({'schema_version': {'const': 2, 'type': 'integer'}, 'record_kind': {'const': 'failed-operation'},
                 'id': {'type': 'string', 'pattern': '^e-[a-f0-9]+-[a-f0-9]+$'},
                 'input_path': text, 'failure_path': text, 'failure_sha256': sha,
                 'operation': {'enum': ['build', 'verify']}, 'status': {'enum': ['failed', 'timed_out', 'cancelled']},
                 'method': {'enum': [None, 'image', 'hardware']}, 'run_id': text})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'M2 failed-operation design contracts', '$defs': {'failure': failure, 'failed_index': index}}


def structural(kind, value):
    Draft202012Validator(make_schema()['$defs'][kind], format_checker=FormatChecker()).validate(value)


def validate_failure(value, manifest_bytes=None):
    structural('failure', value)
    start = datetime.fromisoformat(value['started_at'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(value['finished_at'].replace('Z', '+00:00'))
    require(start <= end, 'Reversed terminal failure time')
    require(any(d['severity'] == 'error' for d in value['diagnostics']), 'Failure needs error diagnostic')
    require((value['operation'] == 'build') == (value['method'] is None), 'Wrong operation/method')
    paths = []
    for item in value['evidence']:
        _path(item['path']); paths.append(item['path'].casefold())
    require(len(paths) == len(set(paths)), 'Duplicate failure evidence')
    if value['record_kind'] == 'preflight-failure':
        require(value['attempted_report'] is None and value['build_stages'] is None, 'Preflight cannot claim execution')
        require(value['cleanup'] == {'serial': 'not_acquired', 'helpers': 'not_started'}, 'Preflight acquired resources')
    elif value['record_kind'] == 'build-failure':
        require(value['operation'] == 'build' and value['attempted_report'] is None, 'Wrong build failure')
        stages = value['build_stages']
        require(stages is not None, 'Missing build stages')
        values = list(stages.values())
        require(any(s in ('failed', 'timed_out', 'cancelled') for s in values), 'Build failure needs failed stage')
        first = next(i for i, s in enumerate(values) if s != 'passed')
        require(values[first] in ('failed', 'timed_out', 'cancelled') and all(s == 'skipped' for s in values[first+1:]), 'Invalid stage order')
        require(value['cleanup']['serial'] == 'not_acquired', 'Build cannot own serial')
    else:
        require(value['operation'] == 'verify' and value['build_stages'] is None, 'Wrong recovery operation')
        require(manifest_bytes is not None and value['attempted_report'] is not None, 'Recovery needs original report and manifest')
        report = validate_report(value['attempted_report'], manifest_bytes)
        require(report['manifest_sha256'] == value['manifest_sha256'] and report['method'] == value['method'] and report['run_id'] == value['run_id'], 'Recovery identity mismatch')
        require(value['target'] == report['target'], 'Recovery target mismatch')
        require(start <= moment(report['started_at']) <= moment(report['finished_at']) <= end, 'Attempted report outside recovery interval')
        require(value['status'] == 'failed', 'Report publication failure is failed')
    if value['manifest_sha256'] is not None and manifest_bytes is not None:
        require(value['manifest_sha256'] == hashlib.sha256(manifest_bytes).hexdigest(), 'Failure manifest mismatch')
    return value


def validate_failed_index(index, failure_bytes, manifest_bytes=None):
    structural('failed_index', index)
    windows_absolute(index['input_path']); windows_absolute(index['failure_path'])
    require(index['input_path'].casefold() != index['failure_path'].casefold(), 'Input/failure path collision')
    require(index['failure_sha256'] == hashlib.sha256(failure_bytes).hexdigest(), 'Changed failure bytes')
    failure = validate_failure(json.loads(failure_bytes), manifest_bytes)
    require(all(index[k] == failure[k] for k in ('operation', 'method', 'status', 'run_id')), 'Failure index contradicts terminal record')
    return index


if __name__ == '__main__':
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'docs/schemas/m2-failures.schema.json'
    path.write_text(json.dumps(make_schema(), indent=2) + '\n', encoding='utf-8')
    print('Generated', path)
