"""Validate planning data without asserting that referenced work is complete."""
import json
import re
from pathlib import Path
from check import STAGES, STATES

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_STATES = {'not_run', 'running', 'passed', 'failed', 'cancelled', 'timed_out', 'skipped'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def references(paths):
    require(isinstance(paths, list), 'Evidence must be a list')
    for value in paths:
        require(isinstance(value, str), 'Evidence must contain paths')
        path = (ROOT / value).resolve()
        require(value.startswith('docs/') and path.is_relative_to(ROOT / 'docs') and path.is_file(), 'Missing or unsafe evidence: ' + value)


def validate_tracking(data):
    require(data.get('schema_version') == 1 and data.get('updated_at'), 'Invalid schema/timestamp')
    updates = data.get('work_updates', [])
    require(isinstance(updates, list), 'Invalid work summaries')
    seen_updates = set()
    for record in updates:
        require(isinstance(record, dict), 'Invalid code-work summary')
        require(record.get('id') and record['id'] not in seen_updates, 'Missing/duplicate work-summary ID')
        seen_updates.add(record['id'])
        require(all(isinstance(record.get(key), str) and record[key].strip() for key in ('updated_at', 'title', 'summary', 'validation', 'next_action')), 'Incomplete code-work summary')
        require('commit' in record and (record['commit'] is None or isinstance(record['commit'], str) and re.fullmatch('[a-f0-9]{7,40}', record['commit'])), 'Invalid work-summary commit')
        references(record.get('evidence'))
        require(record['evidence'], 'Work summary needs evidence')
    policy = data.get('work_policy', {})
    require(policy.get('max_active') == 2, 'Expected agreed two-item limit')
    require(policy.get('selected_milestone') in {m['id'] for m in data['milestones']}, 'Unknown selected milestone')
    items = data.get('work_items', [])
    require(items and len({i['id'] for i in items}) == len(items), 'Missing/duplicate work items')
    active = [i for i in items if i['status'] in {'in_progress', 'blocked'}]
    require(len(active) <= 2, 'Active-work limit exceeded')
    require(len({i['milestone'] for i in active}) <= 1, 'Multiple active delivery milestones')
    for kind in ('primary', 'research'):
        require(sum(i['kind'] == kind for i in active) <= 1, 'Active slot exceeded: ' + kind)
    for item in items:
        require(item.get('status') in STATES and item.get('kind') in {'primary', 'research'}, 'Invalid work item')
        require(item.get('milestone') in {m['id'] for m in data['milestones']}, 'Unknown work milestone')
        require(item.get('exit_condition') and item.get('next_action'), 'Missing work exit/next action')
        references(item.get('evidence'))
        require(item['status'] not in {'in_progress', 'blocked'} or item['milestone'] == policy['selected_milestone'], 'Active work outside selected milestone')
    for section in ('decisions', 'gaps', 'milestones', 'workflow', 'requirements', 'environment', 'runs'):
        records = data.get(section)
        require(isinstance(records, list), 'Missing section: ' + section)
        seen = set()
        for record in records:
            identifier = record.get('id')
            require(identifier and identifier not in seen, 'Missing/duplicate ID in ' + section)
            seen.add(identifier)
            if 'evidence' in record:
                references(record['evidence'])
            if section in ('gaps', 'milestones', 'workflow'):
                require(record.get('status') in STATES, 'Invalid planning status')
            if section == 'decisions':
                require(record.get('status') in {'agreed', 'proposed', 'superseded'}, 'Invalid decision status')
                require(record.get('evidence'), 'Decision needs source')
            if section == 'requirements':
                require(record.get('owner') and record.get('next_action') and record.get('acceptance'), 'Missing requirement details')
                require(record.get('milestone') in {m['id'] for m in data['milestones']}, 'Unknown milestone')
                for stage in STAGES:
                    item = record['stages'][stage]
                    require(item['status'] in STATES, 'Invalid requirement stage')
                    references(item['evidence'])
                    require(item['status'] != 'complete' or item['evidence'], 'Completion requires evidence')
                for field in ('design', 'changes', 'tests', 'blockers'):
                    require(isinstance(record.get(field), list), 'Missing traceability list')
            if section == 'runs':
                require(record.get('target') and record.get('artifact') and record.get('updated_at') and record.get('cleanup'), 'Incomplete run metadata')
                require(record.get('verification_scope') in {'emulator', 'hardware', 'none'}, 'Missing verification scope')
                require(record.get('status') in RUNTIME_STATES, 'Invalid run outcome')
                require(isinstance(record.get('steps'), list), 'Missing run steps')
                for step in record['steps']:
                    require(step.get('name') and step.get('status') in RUNTIME_STATES, 'Invalid runtime step')
                    references(step.get('evidence'))
                if record['status'] == 'passed':
                    require(record.get('evidence') and record['steps'], 'Passed run needs evidence and steps')
                    require(not any(s['status'] in {'failed', 'cancelled', 'timed_out', 'running'} for s in record['steps']), 'Passed run has failed/unfinished steps')
    return data


if __name__ == '__main__':
    data = validate_tracking(json.loads((ROOT / 'docs/tracking.json').read_text(encoding='utf-8')))
    print(f"Validated planning: {len(data['decisions'])} decisions, {len(data['requirements'])} requirements, {len(data['runs'])} recorded runs.")
