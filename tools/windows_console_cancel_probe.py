"""Private hidden-console helper: deliver real Windows console events only to owned tests."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--operation', choices=('build','verify'), default='verify')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--event', choices=('ctrl-c', 'ctrl-break'), required=True)
    args = parser.parse_args()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    handler = callback_type(lambda event: True)
    kernel.SetConsoleCtrlHandler.argtypes = [callback_type, wintypes.BOOL]
    kernel.SetConsoleCtrlHandler.restype = wintypes.BOOL
    kernel.GetConsoleProcessList.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    kernel.GetConsoleProcessList.restype = wintypes.DWORD
    kernel.GenerateConsoleCtrlEvent.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.GenerateConsoleCtrlEvent.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    if not kernel.SetConsoleCtrlHandler(handler, True):
        raise ctypes.WinError(ctypes.get_last_error())
    if args.operation=='verify':
        manifest = json.loads(args.manifest.read_bytes())
        reports = args.manifest.parent.parent / '.rustos-reports' / manifest['bundle_id']
        before = set(reports.glob('*')) if reports.exists() else set()
        command = [str(args.binary),'verify','--repo',str(args.repo),'--manifest',str(args.manifest),'--format','json']
    else:
        reports = args.config.parent
        before = set(reports.glob('.rustos-staging-*'))
        command = [str(args.binary),'build','--repo',str(args.repo),'--config',str(args.config),'--format','json']
    stdout = args.output.with_suffix('.stdout.json')
    stderr = args.output.with_suffix('.stderr.log')
    handles = []
    with stdout.open('xb') as out, stderr.open('xb') as err:
        child = subprocess.Popen(command, stdout=out, stderr=err, cwd=args.repo)
        try:
            start = time.monotonic()
            launch = None
            while time.monotonic() - start < 10:
                candidates = reports.glob('*') if args.operation=='verify' else reports.glob('.rustos-staging-*')
                for directory in set(candidates) - before:
                    if args.operation=='build':
                        ready=list(directory.glob('c/n/**/cancel-ready.txt'))
                        if not ready:
                            continue
                        build_script_pid=int(ready[0].read_text(encoding='utf-8'))
                        path=directory/'logs/normal/process.json'
                    else:
                        path = directory/'startup/launch.json'
                    if path.is_file():
                        try:
                            launch = json.loads(path.read_bytes())
                        except json.JSONDecodeError:
                            continue
                if launch is not None:
                    break
                if child.poll() is not None:
                    raise RuntimeError('Verifier exited before a live scenario started')
                time.sleep(.01)
            if launch is None:
                raise RuntimeError('Live scenario was not reached within the probe budget')
            pids = [launch['owned_pid']] + ([build_script_pid] if args.operation=='build' else [])
            for pid in pids:
                handle = kernel.OpenProcess(0x00100000, False, pid)
                if not handle:
                    raise ctypes.WinError(ctypes.get_last_error())
                handles.append(handle)
            time.sleep(.25)
            clients = (wintypes.DWORD * 32)()
            count = kernel.GetConsoleProcessList(clients, 32)
            owned_clients = {os.getpid(), child.pid}
            if count != 2 or set(clients[:count]) != owned_clients:
                raise RuntimeError('Refusing console broadcast: private console ownership is not established')
            event = 0 if args.event == 'ctrl-c' else 1
            if not kernel.GenerateConsoleCtrlEvent(event, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            child.wait(timeout=15)
            settled = all(kernel.WaitForSingleObject(handle,5000)==0 for handle in handles)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            for handle in handles:
                kernel.CloseHandle(handle)
    cli = json.loads(stdout.read_bytes())
    result = dict(operation=args.operation,event=args.event,console_clients=sorted(owned_clients),verifier_exit=child.returncode,owned_pids=pids,owned_processes_settled=settled,qemu_pid=launch['owned_pid'] if args.operation=='verify' else None,qemu_settled=settled if args.operation=='verify' else None,cli=cli)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
