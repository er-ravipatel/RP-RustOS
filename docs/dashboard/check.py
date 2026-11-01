import json
import re
from pathlib import Path

STAGES = ('requirements', 'analysis', 'design', 'review', 'documentation', 'implementation', 'verification')
STATES = {'draft', 'not_started', 'in_progress', 'blocked', 'complete'}


def validate(data):
    assert data.get('updated_at'), 'Missing register timestamp'
    assert data.get('features'), 'Missing features'
    ids = set()
    for feature in data['features']:
        assert feature['id'] not in ids, 'Duplicate feature ID'
        ids.add(feature['id'])
        assert feature.get('updated_at') and feature.get('next_action'), 'Missing feature metadata'
        assert isinstance(feature.get('blockers'), list), 'Blockers must be a list'
        assert re.fullmatch(r'docs/features/[a-z0-9-]+\.md', feature.get('spec', '')), 'Invalid feature spec path'
        for stage in STAGES:
            record = feature['stages'][stage]
            assert record['status'] in STATES, f"Invalid state: {feature['id']}/{stage}"
            assert isinstance(record['evidence'], list), 'Evidence must be a list'
            assert record['status'] != 'complete' or record['evidence'], 'Completion requires evidence'
    return data


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    data = validate(json.loads((root / 'docs/progress.json').read_text(encoding='utf-8')))
    for feature in data['features']:
        assert (root / feature['spec']).is_file(), f"Missing spec: {feature['spec']}"
    print(f"Validated {len(data['features'])} features and {len(data['features']) * len(STAGES)} stage records.")
