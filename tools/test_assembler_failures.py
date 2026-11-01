"""M1 cancellation/reporting/cleanup failure acceptance; never writes physical media."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from check_design_contracts import validate
from test_assembler_verify import ROOT, BINARY, fixture_elf, digest, invoke

FAULT_BINARY = ROOT/'target/fault-host/debug/rustos-fault-fixture.exe'


def process_handle(pid,terminate=False):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x00100000 | (1 if terminate else 0), False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def settled(handle):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        return kernel.WaitForSingleObject(handle, 5000) == 0
    finally:
        kernel.CloseHandle(handle)


class FailureAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ROOT/'target'/('fail-'+hex(time.time_ns())[2:])
        cls.root.mkdir(parents=True)
        config = cls.root/'m1.toml'
        config.write_text('schema_version=1\ntarget="qemu-virt-a53"\nfeatures=["serial-console","boot-diagnostics"]\noutput_dir="bundle"\n', encoding='utf-8')
        process, record = invoke('build', config)
        if process.returncode:
            raise AssertionError(record)
        cls.bundle = cls.root/'bundle'
        cls.manifest = json.loads((cls.bundle/'manifest.json').read_bytes())
        cls.checks = []

    @classmethod
    def tearDownClass(cls):
        (cls.root/'acceptance.json').write_text(json.dumps(dict(schema_version=1, kind='assembler-failure-acceptance', passed=len(cls.checks)==8, checks=cls.checks), indent=2)+'\n', encoding='utf-8')
        print('Retained failure acceptance:', cls.root)

    def fixture(self, name, silent=False):
        bundle = self.root/name
        bundle.mkdir()
        shutil.copytree(self.bundle/'source', bundle/'source')
        manifest = json.loads((self.bundle/'manifest.json').read_bytes())
        for artifact in manifest['artifacts']:
            shutil.copyfile(self.bundle/artifact['path'], bundle/artifact['path'])
            if silent and artifact['variant']=='normal':
                (bundle/artifact['path']).write_bytes(fixture_elf())
                artifact.update(sha256=digest(bundle/artifact['path']), size_bytes=(bundle/artifact['path']).stat().st_size)
        (bundle/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return bundle, manifest

    def console_cancel(self, event):
        bundle, manifest = self.fixture(event, silent=True)
        output = self.root/(event+'-probe.json')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        child = subprocess.run([sys.executable, str(ROOT/'tools/windows_console_cancel_probe.py'), '--binary', str(BINARY), '--repo', str(ROOT), '--manifest', str(bundle/'manifest.json'), '--output', str(output), '--event', event], creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup, capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stderr)
        probe = json.loads(output.read_bytes())
        validate('cli', probe['cli'])
        validate('verification', probe['cli']['result'], manifest)
        self.assertEqual(probe['verifier_exit'], 7)
        self.assertEqual(probe['cli']['status'], 'cancelled')
        self.assertTrue(probe['qemu_settled'])
        self.assertTrue(probe['cli']['result']['cleanup']['processes_settled'])
        self.assertEqual(probe['cli']['result']['steps'][1]['status'], 'skipped')
        self.checks.append(dict(name='real isolated console '+event+' cancellation', status='passed', evidence=probe))

    def test_console_ctrl_c(self):
        self.console_cancel('ctrl-c')

    def test_console_ctrl_break(self):
        self.console_cancel('ctrl-break')

    def test_active_build_ctrl_c_settles_cargo_and_build_script(self):
        repo=self.root/'cancel-build-repo'
        shutil.copytree(self.bundle/'source',repo)
        script=repo/'core/kernel/build.rs'
        original=script.read_text(encoding='utf-8')
        delay='let directory=std::env::var("OUT_DIR").unwrap(); std::fs::write(std::path::Path::new(&directory).join("cancel-ready.txt"),std::process::id().to_string()).unwrap(); std::thread::sleep(std::time::Duration::from_secs(30));'
        script.write_text(original.replace('fn main() {','fn main() {\n'+delay,1),encoding='utf-8')
        output=self.root/'build-cancel-probe.json'
        startup=subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow=subprocess.SW_HIDE
        child=subprocess.run([sys.executable,str(ROOT/'tools/windows_console_cancel_probe.py'),'--binary',str(BINARY),'--repo',str(repo),'--operation','build','--config',str(repo/'configuration.toml'),'--output',str(output),'--event','ctrl-c'],creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,capture_output=True,text=True,timeout=30)
        self.assertEqual(child.returncode,0,child.stderr)
        probe=json.loads(output.read_bytes())
        validate('cli',probe['cli'])
        self.assertEqual(probe['verifier_exit'],7)
        self.assertTrue(probe['owned_processes_settled'])
        self.assertEqual(len(probe['owned_pids']),2)
        self.assertFalse((repo/'bundle').exists())
        failure=repo/probe['cli']['evidence'][0]
        self.assertEqual(json.loads(failure.read_bytes())['status'],'cancelled')
        self.checks.append(dict(name='real Ctrl+C during active build settles Cargo and delayed build-script descendants without publication',status='passed',evidence=probe))

    def test_report_publication_failure_retains_original_outcome(self):
        bundle, manifest = self.fixture('report-failure', silent=True)
        reports = bundle.parent/'.rustos-reports'/manifest['bundle_id']
        before = set(reports.glob('*')) if reports.exists() else set()
        child = subprocess.Popen([str(BINARY), 'verify', '--repo', str(ROOT), '--manifest', str(bundle/'manifest.json'), '--format', 'json'], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        handle = None
        try:
            start = time.monotonic()
            directory = None
            while time.monotonic()-start<8:
                for candidate in set(reports.glob('*'))-before:
                    launch = candidate/'startup/launch.json'
                    if launch.is_file():
                        try:
                            data = json.loads(launch.read_bytes())
                        except json.JSONDecodeError:
                            continue
                        directory = candidate
                        handle = process_handle(data['owned_pid'])
                        break
                if directory is not None:
                    break
                time.sleep(.01)
            self.assertIsNotNone(directory)
            (directory/'report.tmp').mkdir()
            stdout, stderr = child.communicate(timeout=20)
            record = json.loads(stdout)
            validate('cli', record)
            self.assertEqual(stderr, '')
            self.assertEqual(child.returncode, 8)
            self.assertEqual(record['status'], 'failed')
            self.assertEqual(record['diagnostics'][0]['code'], 'REPORT_FAILED')
            self.assertIsNone(record['result'])
            recovery = json.loads((directory/'report-recovery.json').read_bytes())
            self.assertFalse(recovery['complete'])
            self.assertEqual(recovery['attempted_report']['status'], 'timed_out')
            self.assertTrue(recovery['attempted_report']['cleanup']['processes_settled'])
            self.assertFalse((directory/'report.json').exists())
            self.assertTrue(settled(handle))
            handle = None
            self.checks.append(dict(name='real report-path collision overrides timeout while retaining original report and settled cleanup', status='passed', cli=record))
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            if handle:
                settled(handle)

    def test_cleanup_confirmation_failure_cannot_pass(self):
        bundle, manifest = self.fixture('cleanup-fixture')
        environment = dict(os.environ, RUSTOS_TEST_CLEANUP_UNCONFIRMED='1')
        child = subprocess.run([str(FAULT_BINARY), 'verify', '--repo', str(ROOT), '--manifest', str(bundle/'manifest.json'), '--format', 'json'], capture_output=True, text=True, timeout=30, env=environment, cwd=ROOT)
        record = json.loads(child.stdout)
        validate('cli', record)
        validate('verification', record['result'], manifest)
        self.assertEqual(child.returncode, 8, record)
        self.assertEqual(record['result']['cleanup']['status'], 'failed')
        self.assertFalse(record['result']['cleanup']['processes_settled'])
        self.assertEqual(record['result']['steps'][1]['status'], 'skipped')
        self.assertTrue(any(d['code']=='TEST_FAULT_INJECTION' for d in record['result']['diagnostics']))
        report = bundle.parent/record['evidence'][0]
        launch = json.loads((report.parent/'startup/launch.json').read_bytes())
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x00100000,False,launch['owned_pid'])
        if handle:
            self.assertTrue(settled(handle))
        else:
            self.assertEqual(ctypes.get_last_error(),87)
        self.checks.append(dict(name='test-only unavailable cleanup confirmation returns failure after real process settlement', status='passed', cli=record))

    def test_unexpected_qemu_exit_prevents_success(self):
        bundle,manifest=self.fixture('unexpected-exit',silent=True)
        reports=bundle.parent/'.rustos-reports'/manifest['bundle_id']
        before=set(reports.glob('*')) if reports.exists() else set()
        child=subprocess.Popen([str(BINARY),'verify','--repo',str(ROOT),'--manifest',str(bundle/'manifest.json'),'--format','json'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        handle=None
        try:
            start=time.monotonic()
            while time.monotonic()-start<8 and handle is None:
                for directory in set(reports.glob('*'))-before:
                    launch=directory/'startup/launch.json'
                    if launch.is_file():
                        try:
                            data=json.loads(launch.read_bytes())
                        except json.JSONDecodeError:
                            continue
                        handle=process_handle(data['owned_pid'],terminate=True)
                        break
                if handle is None:
                    time.sleep(.01)
            self.assertIsNotNone(handle)
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
            self.assertTrue(kernel.TerminateProcess(handle,42))
            stdout,stderr=child.communicate(timeout=15)
            record=json.loads(stdout)
            validate('cli',record)
            validate('verification',record['result'],manifest)
            self.assertEqual(child.returncode,5,record)
            self.assertEqual(record['result']['steps'][0]['status'],'failed')
            self.assertEqual(record['result']['steps'][1]['status'],'skipped')
            self.assertTrue(record['result']['cleanup']['processes_settled'])
            self.assertTrue(settled(handle))
            handle=None
            self.checks.append(dict(name='unexpected exit of the exact owned QEMU process cannot pass',status='passed',cli=record))
        finally:
            if child.poll() is None:
                child.terminate();child.wait(timeout=5)
            if handle:
                settled(handle)

    def test_production_binary_has_no_cleanup_injection_hook(self):
        bundle, manifest = self.fixture('production-control')
        child = subprocess.run([str(BINARY), 'verify', '--repo', str(ROOT), '--manifest', str(bundle/'manifest.json'), '--format', 'json'], capture_output=True, text=True, timeout=30, env=dict(os.environ,RUSTOS_TEST_CLEANUP_UNCONFIRMED='1'), cwd=ROOT)
        record = json.loads(child.stdout)
        validate('verification', record['result'], manifest)
        self.assertEqual(child.returncode,0,record)
        self.assertFalse(any(d['code']=='TEST_FAULT_INJECTION' for d in record['result']['diagnostics']))
        self.checks.append(dict(name='production binary ignores fault-injection environment variable',status='passed',cli=record))

    def test_execution_index_failure_prevents_cli_success(self):
        bundle, manifest = self.fixture('index-failure')
        repo = self.root/'blocked-index-repo'
        shutil.copytree(self.bundle/'source',repo)
        (repo/'.rustos').mkdir()
        (repo/'.rustos/executions').write_bytes(b'occupied index path')
        child = subprocess.run([str(BINARY),'verify','--repo',str(repo),'--manifest',str(bundle/'manifest.json'),'--format','json'],capture_output=True,text=True,timeout=30,cwd=ROOT)
        record = json.loads(child.stdout)
        validate('cli',record)
        self.assertEqual(child.returncode,8)
        self.assertEqual(record['status'],'failed')
        self.assertEqual(record['result']['status'],'passed')
        self.assertEqual(record['diagnostics'][-1]['code'],'EXECUTION_INDEX')
        self.assertEqual((repo/'.rustos/executions').read_bytes(),b'occupied index path')
        self.checks.append(dict(name='unwritable execution-index path prevents final CLI success despite passing guest checks',status='passed',cli=record))


if __name__ == '__main__':
    unittest.main(verbosity=2)
