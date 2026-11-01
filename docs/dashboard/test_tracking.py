import copy
import json
import unittest
from check_tracking import ROOT, validate_tracking


class TrackingValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'docs/tracking.json').read_text(encoding='utf-8'))

    def test_current_register(self):
        validate_tracking(self.data)

    def test_work_summaries_reject_missing_validation_and_duplicate_ids(self):
        self.data['work_updates'][0]['validation'] = ''
        with self.assertRaises(ValueError):
            validate_tracking(self.data)
        self.setUp()
        self.data['work_updates'].append(copy.deepcopy(self.data['work_updates'][0]))
        with self.assertRaises(ValueError):
            validate_tracking(self.data)

    def test_work_summary_commit_cannot_be_an_arbitrary_url(self):
        self.data['work_updates'][0]['commit'] = 'https://example.invalid/'
        with self.assertRaises(ValueError):
            validate_tracking(self.data)

    def test_completion_requires_evidence(self):
        stage = self.data['requirements'][0]['stages']['verification']
        stage.update(status='complete', evidence=[])
        with self.assertRaises(ValueError):
            validate_tracking(self.data)

    def test_rejects_missing_evidence_file(self):
        self.data['decisions'][0]['evidence'] = ['docs/nonexistent-evidence.md']
        with self.assertRaises(ValueError):
            validate_tracking(self.data)

    def test_rejects_duplicate_requirement(self):
        self.data['requirements'].append(copy.deepcopy(self.data['requirements'][0]))
        with self.assertRaises(ValueError):
            validate_tracking(self.data)

    def test_rejects_excess_primary_work(self):
        self.data['work_policy']['selected_milestone'] = 'M1'
        for item in self.data['work_items']:
            item['status'] = 'not_started'
        for item in self.data['work_items'][:2]:
            item['status'] = 'in_progress'
        with self.assertRaises(ValueError):
            validate_tracking(self.data)

    def test_rejects_active_work_outside_selected_milestone(self):
        for item in self.data['work_items']:
            item['status'] = 'not_started'
        self.data['work_policy']['selected_milestone'] = 'M1'
        self.data['work_items'][0].update(status='in_progress', milestone='M2')
        with self.assertRaises(ValueError):
            validate_tracking(self.data)

    def test_allows_primary_and_supporting_research(self):
        self.data['work_policy']['selected_milestone'] = 'M1'
        # Isolate this policy case from whichever delivery item is currently active.
        for item in self.data['work_items']:
            item['status'] = 'not_started'
        self.data['work_items'][0]['status'] = 'in_progress'
        self.data['work_items'][1].update(status='in_progress', kind='research')
        validate_tracking(self.data)

    def test_passed_run_cannot_contain_failed_verification(self):
        self.data['runs'].append({'id': 'test-only', 'target': 'emulator', 'artifact': 'test-artifact', 'updated_at': self.data['updated_at'], 'status': 'passed', 'verification_scope': 'emulator', 'cleanup': 'settled', 'evidence': ['docs/assembler-workflows.md'], 'steps': [{'name': 'verification', 'status': 'failed', 'evidence': ['docs/assembler-workflows.md']}]})
        with self.assertRaises(ValueError):
            validate_tracking(self.data)


if __name__ == '__main__':
    unittest.main()
