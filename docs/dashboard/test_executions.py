import json
from pathlib import Path
import tempfile
import unittest
from executions import digest, load_indexes, report_record


class ExecutionImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rustos-import-')
        self.root = Path(self.temp.name)
        artifacts = [dict(id='kernel', variant='normal', sha256='a'*64), dict(id='panic-test', variant='panic-test', sha256='b'*64)]
        manifest = dict(target=dict(id='qemu-virt-a53'), artifacts=artifacts)
        manifest_data = json.dumps(manifest).encode()
        (self.root/'input-manifest.json').write_bytes(manifest_data)
        steps = []
        for identity, artifact, marker in [('startup', artifacts[0], 'RUSTOS_BOOT_OK'), ('panic', artifacts[1], 'RUSTOS_EXPECTED_PANIC')]:
            directory = self.root/identity
            directory.mkdir()
            logs = []
            for stream in ('stdout', 'stderr'):
                data = (marker+'\n').encode() if stream == 'stdout' else b''
                (directory/(stream+'.log')).write_bytes(data)
                logs.append(dict(stream=stream, path=identity+'/'+stream+'.log', sha256=digest(data)))
            steps.append(dict(id=identity, artifact_id=artifact['id'], artifact_sha256=artifact['sha256'], status='passed', deadline_ms=10000, observed_marker=marker, stop_requested=True, logs=logs, diagnostics=[]))
        report = dict(schema_version=1, run_id='v-test', complete=True, operation='verify', target='qemu-virt-a53', manifest_sha256=digest(manifest_data), verification_scope='emulator', started_at='2026-11-01T00:00:00.000Z', finished_at='2026-11-01T00:00:01.000Z', status='passed', steps=steps, cleanup=dict(status='passed', processes_settled=True, stop_budget_ms=5000, kill_budget_ms=5000, diagnostics=[]), diagnostics=[], evidence=['input-manifest.json'])
        self.index = dict(schema_version=1, id='e-a-b', input_path=str(self.root/'manifest.json'), report_path=str(self.root/'report.json'), cli=dict(schema_version=1, operation='verify', status='passed', target='qemu-virt-a53', build_ready=None, diagnostics=[], result=report, evidence=[]))
        self.persist()

    def tearDown(self):
        self.temp.cleanup()

    def persist(self):
        Path(self.index['report_path']).write_text(json.dumps(self.index['cli']['result']), encoding='utf-8')

    def test_valid_report_imports_with_link(self):
        row = report_record(self.index)
        self.assertEqual(row['status'], 'passed')
        self.assertIn('execution/e-a-b/report', row['evidence'])

    def test_missing_marker_cannot_import_as_passed(self):
        self.index['cli']['result']['steps'][0]['observed_marker'] = None
        self.persist()
        with self.assertRaises(ValueError):
            report_record(self.index)

    def test_duplicate_scenarios_cannot_import(self):
        self.index['cli']['result']['steps'][1]['id'] = 'startup'
        self.persist()
        with self.assertRaises(ValueError):
            report_record(self.index)

    def test_tampered_capture_cannot_import(self):
        (self.root/'startup/stdout.log').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            report_record(self.index)

    def test_rehashed_log_without_marker_cannot_import_as_passed(self):
        data = b'ordinary diagnostics\n'
        (self.root/'startup/stdout.log').write_bytes(data)
        self.index['cli']['result']['steps'][0]['logs'][0]['sha256'] = digest(data)
        self.persist()
        with self.assertRaises(ValueError):
            report_record(self.index)

    def test_cli_report_mismatch_cannot_import(self):
        self.index['cli']['result']['status'] = 'failed'
        with self.assertRaises(ValueError):
            report_record(self.index)

    def test_escaping_capture_path_cannot_import(self):
        self.index['cli']['result']['steps'][0]['logs'][0]['path'] = '../outside'
        self.persist()
        with self.assertRaises(ValueError):
            report_record(self.index)

    def test_malformed_index_is_visible_as_import_error(self):
        directory = self.root/'.rustos/executions'
        directory.mkdir(parents=True)
        (directory/'broken.json').write_text('{}', encoding='utf-8')
        rows, errors = load_indexes(self.root)
        self.assertEqual(rows, [])
        self.assertEqual(len(errors), 1)

    def test_unapproved_control_timer_stays_provisional(self):
        self.index['cli']['result']['diagnostics'].append(dict(code='CONTROL_TIMER_PROPOSAL', severity='info'))
        self.persist()
        self.assertEqual(report_record(self.index)['kind'], 'assembler-verify-provisional')

    def test_unsettled_cleanup_cannot_import_as_passed(self):
        self.index['cli']['result']['cleanup']['processes_settled'] = False
        self.persist()
        with self.assertRaises(ValueError):
            report_record(self.index)

    def test_incomplete_reporting_failure_has_evidence_link(self):
        self.index['cli'].update(status='failed', result=None, diagnostics=[dict(code='REPORT_FAILED',message='test collision')])
        Path(self.index['report_path']).write_text(json.dumps(dict(schema_version=1,operation='verify',status='failed',complete=False)),encoding='utf-8')
        row=report_record(self.index)
        self.assertEqual(row['status'],'failed')
        self.assertIn('execution/e-a-b/report',row['evidence'])

    def test_fault_injection_is_separately_labelled(self):
        report=self.index['cli']['result']
        report['status']='failed'
        report['steps'][0]['status']='failed'
        report['cleanup'].update(status='failed',processes_settled=False)
        report['diagnostics'].append(dict(code='TEST_FAULT_INJECTION',severity='info'))
        self.index['cli']['status']='failed'
        self.persist()
        self.assertEqual(report_record(self.index)['kind'],'assembler-verify-fault-fixture')

    def test_failed_build_keeps_skipped_and_unrequested_stages_distinct(self):
        self.index['cli'].update(operation='build',status='failed',result=None,diagnostics=[dict(code='PACKAGING_SKIPPED',message='not compiled'),dict(code='VERIFICATION_NOT_RUN',message='not requested')])
        row=report_record(self.index)
        self.assertIn('skipped',{step['status'] for step in row['steps']})
        self.assertIn('not_run',{step['status'] for step in row['steps']})


if __name__ == '__main__':
    unittest.main()
