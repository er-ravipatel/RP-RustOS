"""Read-only mapping of explicit assembler execution indexes into dashboard rows."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re

TERMINAL = {'passed', 'failed', 'timed_out', 'cancelled'}
ROOT = Path(__file__).resolve().parents[2]


def need(condition, message):
    if not condition:
        raise ValueError(message)


def read(path, limit=1024 * 1024):
    path = Path(path)
    need(path.is_file() and path.stat().st_size <= limit, 'Missing or excessive indexed file')
    data = path.read_bytes()
    need(len(data) <= limit, 'Indexed file grew beyond limit')
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def contained(base, relative):
    need(isinstance(relative, str) and relative and not re.search(r'[:\\\x00]', relative), 'Unsafe report reference')
    need(not relative.startswith('/') and not any(part in ('.', '..') for part in relative.split('/')), 'Escaping report reference')
    result = (base / relative).resolve()
    need(result.is_relative_to(base.resolve()), 'Escaping report reference')
    return result


def report_record(index):
    cli = index['cli']
    need(cli['operation'] in ('build', 'verify') and cli['status'] in TERMINAL, 'Unknown execution outcome')
    need(cli.get('schema_version') == 1 and isinstance(cli.get('diagnostics'), list), 'Invalid CLI record')
    evidence = ['docs/p5-verification.md']
    details = []
    scope = 'none'
    artifact = index['input_path']
    cleanup = 'No emulator cleanup result: preflight failure or build-only operation.'
    updated = 'not-recorded'
    kind = 'assembler-' + cli['operation']
    result = cli.get('result')
    if cli['operation'] == 'build':
        if cli['status'] == 'passed':
            need(cli.get('build_ready') is True and isinstance(result, dict), 'Passing build lacks readiness/result')
            data = read(result['manifest_path'])
            manifest = json.loads(data)
            need(digest(data) == result['manifest_sha256'] and manifest.get('complete') is True, 'Build manifest identity mismatch')
            artifact = result['manifest_path'] + ' sha256:' + result['manifest_sha256']
            updated = manifest['created_at']
        details.append({'name': 'Build/package operation', 'status': cli['status'], 'evidence': []})
    elif result is not None:
        path = Path(index['report_path'])
        report = json.loads(read(path))
        need(report == result, 'CLI and retained report differ')
        expected_fields = {'schema_version', 'run_id', 'complete', 'operation', 'target', 'manifest_sha256', 'verification_scope', 'started_at', 'finished_at', 'status', 'steps', 'cleanup', 'diagnostics', 'evidence'}
        need(set(report) == expected_fields and report['schema_version'] == 1 and report['operation'] == 'verify' and report['complete'] is True, 'Incomplete/unknown report structure')
        need(report['status'] == cli['status'] and report['status'] in TERMINAL and report['verification_scope'] == 'emulator', 'CLI/report outcome mismatch')
        manifest_bytes = read(path.parent / 'input-manifest.json')
        manifest = json.loads(manifest_bytes)
        need(digest(manifest_bytes) == report['manifest_sha256'], 'Verification manifest binding mismatch')
        need(report['target'] == cli['target'] == manifest['target']['id'], 'Target mismatch')
        artifacts = {a['id']: a for a in manifest['artifacts']}
        need(len(artifacts) == 2 and {a['variant'] for a in artifacts.values()} == {'normal', 'panic-test'}, 'Invalid artifact variants')
        steps = report['steps']
        need(len(steps) == 2 and {s['id'] for s in steps} == {'startup', 'panic'}, 'Missing or duplicate scenarios')
        diagnostics = list(report['diagnostics']) + list(report['cleanup']['diagnostics']) + list(cli['diagnostics'])
        for step in steps:
            need(set(step) == {'id','artifact_id','artifact_sha256','status','deadline_ms','observed_marker','stop_requested','logs','diagnostics'} and step['deadline_ms'] == 10000, 'Unknown scenario structure/deadline')
            need(step['status'] in TERMINAL | {'skipped'}, 'Unresolved final scenario')
            source = artifacts[step['artifact_id']]
            need(source['sha256'] == step['artifact_sha256'] and source['variant'] == ('normal' if step['id'] == 'startup' else 'panic-test'), 'Scenario artifact mismatch')
            diagnostics += step['diagnostics']
            streams = set()
            serial = None
            for log in step['logs']:
                need(set(log) == {'stream','path','sha256'}, 'Unknown log structure')
                need(log['stream'] in ('stdout', 'stderr') and log['stream'] not in streams, 'Duplicate/unknown log stream')
                streams.add(log['stream'])
                captured = read(contained(path.parent, log['path']))
                need(digest(captured) == log['sha256'], 'Log hash mismatch')
                if log['stream'] == 'stdout' and step['status'] == 'passed':
                    serial = captured.decode('utf-8')
            if step['status'] == 'passed':
                expected = 'RUSTOS_BOOT_OK' if step['id'] == 'startup' else 'RUSTOS_EXPECTED_PANIC'
                need(step['observed_marker'] == expected and step['stop_requested'] is True and streams == {'stdout', 'stderr'}, 'Missing success marker/stop/logs')
                need(any(line.removesuffix('\r') == expected for line in serial.split('\n')[:-1]), 'Captured log lacks complete exact marker')
                need(all(len(line.encode('utf-8')) <= 4096 for line in serial.split('\n')), 'Captured serial line exceeds limit')
                need(not any(marker in serial for marker in ('RUSTOS_BOOT_OK','RUSTOS_EXPECTED_PANIC','RUSTOS_UNEXPECTED_PANIC','RUSTOS_EXCEPTION') if marker != expected), 'Capture contradicts passing scenario')
            details.append({'name': step['id'], 'status': step['status'], 'evidence': []})
        cleanup_data = report['cleanup']
        need(set(cleanup_data) == {'status','stop_budget_ms','kill_budget_ms','processes_settled','diagnostics'} and cleanup_data['stop_budget_ms'] == cleanup_data['kill_budget_ms'] == 5000 and isinstance(cleanup_data['processes_settled'], bool), 'Invalid cleanup structure')
        need(cleanup_data['status'] in ('passed', 'failed'), 'Unresolved cleanup')
        if report['status'] == 'passed':
            need(all(s['status'] == 'passed' for s in steps) and cleanup_data['status'] == 'passed' and cleanup_data['processes_settled'] is True, 'False passing verification')
            need(not any(d['severity'] == 'error' for d in diagnostics), 'Passing report contains an error')
        if any(d.get('code') == 'CONTROL_TIMER_PROPOSAL' for d in diagnostics):
            kind += '-provisional'
        if any(d.get('code') == 'TEST_FAULT_INJECTION' for d in diagnostics):
            kind += '-fault-fixture'
        scope = 'emulator'
        artifact += ' sha256:' + report['manifest_sha256']
        cleanup = cleanup_data['status'] + '; processes_settled=' + str(cleanup_data['processes_settled'])
        updated = report['finished_at']
        evidence.append('execution/' + index['id'] + '/report')
    else:
        need(cli['status'] != 'passed', 'Passing execution lacks a result')
        details.append({'name': 'Preflight/reporting', 'status': cli['status'], 'evidence': []})
        if index.get('report_path'):
            failure = json.loads(read(index['report_path']))
            need(failure.get('schema_version') == 1 and failure.get('operation') == 'verify' and failure.get('complete') is False and failure.get('status') == 'failed', 'Invalid incomplete failure evidence')
            evidence.append('execution/' + index['id'] + '/report')
    for diagnostic in cli['diagnostics']:
        state={'COMPILATION_PASSED':'passed','PACKAGING_PASSED':'passed','PACKAGING_SKIPPED':'skipped','VERIFICATION_NOT_RUN':'not_run'}.get(diagnostic['code'],cli['status'])
        details.append(dict(name=diagnostic['code'] + ': ' + diagnostic['message'], status=state, evidence=[]))
    return dict(id=index['id'], kind=kind, target=cli.get('target') or 'unselected', artifact=artifact, updated_at=updated, status=cli['status'], verification_scope=scope, cleanup=cleanup, steps=details, evidence=evidence)


def load_indexes(root=ROOT):
    records, errors = [], []
    directory = Path(root) / '.rustos/executions'
    files = sorted(directory.glob('*.json'), key=lambda path: path.stat().st_mtime_ns) if directory.exists() else []
    for path in files[-500:]:
        try:
            index = json.loads(read(path))
            need(set(index) == {'schema_version', 'id', 'input_path', 'report_path', 'cli'} and index['schema_version'] == 1, 'Invalid execution index')
            need(re.fullmatch(r'e-[a-f0-9]+-[a-f0-9]+', index['id']) and path.stem == index['id'], 'Invalid index identity')
            record = report_record(index)
            if record['updated_at'] == 'not-recorded':
                record['updated_at'] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')
            records.append(record)
        except (ValueError, KeyError, TypeError, OSError) as error:
            errors.append(path.name + ': ' + str(error))
    return records, errors


def report_path(identifier, root=ROOT):
    need(re.fullmatch(r'e-[a-f0-9]+-[a-f0-9]+', identifier), 'Invalid execution identity')
    index = json.loads(read(Path(root) / '.rustos/executions' / (identifier + '.json')))
    report_record(index)
    need(index['report_path'] is not None, 'Execution has no report')
    return Path(index['report_path'])
