"""Design-contract validation only; does not resolve modules, build, or execute an OS."""
from datetime import datetime
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'docs/schemas/contracts.schema.json').read_text(encoding='utf-8'))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def unique(records, key):
    need(len({r[key] for r in records}) == len(records), 'Duplicate ' + key)


def validate(kind, data, manifest=None):
    schema = {'$schema': SCHEMA['$schema'], '$defs': SCHEMA['$defs'], '$ref': '#/$defs/' + kind}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(data)
    if kind == 'catalog':
        unique(data['modules'], 'id')
        unique(data['features'], 'id')
    if kind in ('plan', 'manifest'):
        unique(data['resolved_modules'], 'id')
        unique(data['inputs'], 'path')
    if kind == 'plan':
        need(set(data['build_order']) == {r['id'] for r in data['resolved_modules']}, 'Build order differs from module set')
    if kind == 'manifest':
        unique(data['artifacts'], 'id')
        unique(data['artifacts'], 'path')
        need({a['variant'] for a in data['artifacts']} == {'normal', 'panic-test'}, 'Both artifact variants required')
    if kind == 'verification':
        unique(data['steps'], 'id')
        all_diagnostics = data['diagnostics'] + data['cleanup']['diagnostics'] + [r for s in data['steps'] for r in s['diagnostics']]
        if data['complete']:
            need(datetime.fromisoformat(data['finished_at'].replace('Z', '+00:00')) >= datetime.fromisoformat(data['started_at'].replace('Z', '+00:00')), 'Reversed timestamps')
            need(data['cleanup']['status'] != 'running' and all(s['status'] != 'running' for s in data['steps']), 'Final report contains running work')
        for step in data['steps']:
            if step['status'] == 'passed':
                expected = 'RUSTOS_BOOT_OK' if step['id'] == 'startup' else 'RUSTOS_EXPECTED_PANIC'
                need(step['observed_marker'] == expected and step['stop_requested'], 'Missing marker/owned stop')
                need(any(log['stream'] == 'stdout' for log in step['logs']), 'Passed step needs serial evidence')
        if data['status'] == 'passed':
            need(data['complete'] and {s['id'] for s in data['steps']} == {'startup', 'panic'}, 'Both completed scenarios required')
            need(all(s['status'] == 'passed' for s in data['steps']), 'Unpassed scenario')
            need(data['cleanup']['status'] == 'passed' and data['cleanup']['processes_settled'], 'Cleanup not established')
            need(not any(r['severity'] == 'error' for r in all_diagnostics), 'Error diagnostics prevent pass')
            need(bool(data['evidence']), 'Passing report needs evidence')
        if manifest is not None:
            validate('manifest', manifest)
            need(data['target'] == manifest['target']['id'], 'Wrong target')
            variants = {a['variant']: a for a in manifest['artifacts']}
            for step in data['steps']:
                artifact = variants['normal' if step['id'] == 'startup' else 'panic-test']
                need(step['artifact_id'] == artifact['id'] and step['artifact_sha256'] == artifact['sha256'], 'Wrong artifact binding')
    if kind == 'cli':
        result = data['result']
        if result is not None:
            result_kind = {'plan': 'plan', 'verify': 'verification'}.get(data['operation'])
            if result_kind:
                validate(result_kind, result, manifest)
        if data['status'] == 'passed':
            need(data['target'] is not None, 'Passed operation needs target')
            need(not any(r['severity'] == 'error' for r in data['diagnostics']), 'Passed operation has error')
            if data['operation'] == 'verify':
                need(result['status'] == 'passed' and result['target'] == data['target'], 'CLI/report mismatch')
            if data['operation'] == 'build':
                need(data['build_ready'] is True, 'Passed build not ready')
    return data


if __name__ == '__main__':
    Draft202012Validator.check_schema(SCHEMA)
    print('Design schema is valid. Use the fixture tests for record checks; no OS verification is implied.')
