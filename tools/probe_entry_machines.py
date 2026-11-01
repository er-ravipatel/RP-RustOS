"""Bounded QMP helper; CLI inventories paused machines without loading images."""
import argparse
import json
import subprocess
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def probe(qemu, machine, extra, run=False, disassemble=None, cpus=(), serial=None, memory_words=None):
    command = [qemu, '-machine', machine, *extra, '-S', '-display', 'none',
               '-serial', serial or 'none', '-monitor', 'none', '-qmp', 'stdio']
    requests = [
        {'execute': 'qmp_capabilities', 'id': 'capabilities'},
        {'execute': 'human-monitor-command', 'arguments': {'command-line': 'info mtree'}, 'id': 'memory'},
        {'execute': 'human-monitor-command', 'arguments': {'command-line': 'info registers'}, 'id': 'registers'},
        {'execute': 'quit', 'id': 'quit'},
    ]
    if run:
        requests[1:1] = [{'execute': 'cont', 'id': 'continue'}, {'execute': 'stop', 'id': 'stop'}]
    if disassemble is not None:
        address, count = disassemble
        requests.insert(-1, {'execute': 'human-monitor-command', 'arguments': {'command-line': f'x/{count}i 0x{address:x}'}, 'id': 'disassembly'})
    if memory_words is not None:
        address, count = memory_words
        if not 0 < count <= 256 or address < 0:
            raise ValueError('Invalid bounded physical memory observation')
        requests.insert(-1, {'execute':'human-monitor-command',
                            'arguments':{'command-line':f'xp /{count}wx 0x{address:x}'},'id':'physical_words'})
    for cpu in cpus:
        if not isinstance(cpu, int) or not 0 <= cpu < 256:
            raise ValueError('Invalid CPU observation index')
        requests.insert(-1, {'execute': 'human-monitor-command',
                            'arguments': {'command-line': 'info registers', 'cpu-index': cpu}, 'id': f'cpu_{cpu}'})
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    incoming = queue.Queue()
    def reader():
        for line in process.stdout:
            incoming.put(line)
        incoming.put(None)
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    def receive():
        line = incoming.get(timeout=10)
        if line is None:
            raise RuntimeError('QEMU closed QMP unexpectedly')
        return json.loads(line)
    try:
        greeting = receive()
        if 'QMP' not in greeting:
            raise RuntimeError('Expected QMP greeting')
        replies = {}
        for request in requests:
            if request['id'] == 'stop':
                time.sleep(0.2)
            process.stdin.write(json.dumps(request) + '\n')
            process.stdin.flush()
            for _ in range(64):
                reply = receive()
                if reply.get('id') == request['id']:
                    if 'return' not in reply:
                        raise RuntimeError(f'QMP failed: {reply}')
                    replies[request['id']] = reply
                    break
            else:
                raise RuntimeError('QMP event limit exceeded')
        process.wait(timeout=10)
    except (queue.Empty, subprocess.TimeoutExpired):
        raise RuntimeError(f'Paused machine probe timed out: {machine}') from None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        thread.join(timeout=2)
        process.stdin.close()
        process.stdout.close()
    errors = process.stderr.read()
    process.stderr.close()
    if process.returncode != 0:
        raise RuntimeError(f'QEMU probe failed: {errors}')
    return {'command': command, 'greeting': greeting, 'stderr': errors,
            'disassembly': replies.get('disassembly', {}).get('return'),
            'physical_words': replies.get('physical_words', {}).get('return'),
            'memory_tree': replies['memory']['return'],
            'cpu_registers': {str(cpu): replies[f'cpu_{cpu}']['return'] for cpu in cpus},
            ('observed_registers' if run else 'reset_registers'): replies['registers']['return'],
            'scope': 'Test adapter executed; not production entry' if run else 'Paused reset state only; no kernel/firmware handoff executed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', required=True)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report destination')
    results = [probe(args.qemu, 'virt,virtualization=on', ['-cpu', 'cortex-a53', '-m', '128M']),
               probe(args.qemu, 'raspi3b', [])]
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'machines': results,
              'hardware_verified': False, 'entry_code_executed': False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(f'Recorded {len(results)} paused machine inventories: {args.report}')


if __name__ == '__main__':
    main()
