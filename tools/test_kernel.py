"""P4 kernel smoke evidence; not the P5 assembler verifier or Job Object runner."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import struct
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'aarch64-unknown-none-softfloat'


def serial_marker(raw, marker, forbidden):
    if len(raw) > 1048576 or any(len(line) > 4096 for line in raw.split(b'\n')):
        raise ValueError('Guest output exceeds line/stream limit')
    output = raw.decode('utf-8')
    if any(bad in output for bad in forbidden):
        raise ValueError('Unexpected fault/scenario marker')
    # Only terminated protocol lines count. A truncated final marker cannot pass.
    lines = [line.removesuffix('\r') for line in output.split('\n')[:-1]]
    return marker is not None and any(line == marker or (marker == 'RUSTOS_EXCEPTION' and line.startswith(marker + ' ')) for line in lines)


def inspect_elf(path):
    data = path.read_bytes()
    if data[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('Expected little-endian ELF64')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    _, kind, machine, _, entry, phoff, shoff, _, _, phsize, phnum, shsize, shnum, _ = header
    if kind != 2 or machine != 183 or entry != 0x40080000:
        raise ValueError('Wrong kernel ELF type/machine/entry')
    segments = []
    for i in range(phnum):
        typ, flags, offset, virtual, physical, size, memory, alignment = struct.unpack_from('<IIQQQQQQ', data, phoff + i * phsize)
        if typ != 1:
            continue
        if not (0x40080000 <= virtual < virtual + memory <= 0x40200000) or offset + size > len(data) or size > memory:
            raise ValueError('Invalid loadable range')
        if physical != virtual or flags & 3 == 3:
            raise ValueError('Unexpected physical mapping or writable executable segment')
        segments.append({'address': hex(virtual), 'file_bytes': size, 'memory_bytes': memory, 'flags': flags})
    if not segments:
        raise ValueError('No loadable segments')
    ranges = sorted((int(s['address'], 16), int(s['address'], 16) + s['memory_bytes']) for s in segments)
    if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
        raise ValueError('Overlapping loadable segments')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * shsize) for i in range(shnum)]
    symbols = {}
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        names = data[strings[4]:strings[4] + strings[5]]
        for offset in range(section[4], section[4] + section[5], section[9]):
            name, _, _, _, value, _ = struct.unpack_from('<IBBHQQ', data, offset)
            end = names.find(b'\0', name)
            symbols[names[name:end].decode(errors='replace')] = value
    if symbols['vectors'] % 2048 or symbols['__stack_top'] % 16:
        raise ValueError('Vector/stack alignment failed')
    if symbols['__stack_top'] - symbols['__stack_bottom'] != 65536 or symbols['__bss_end'] > symbols['__stack_bottom']:
        raise ValueError('Stack/BSS contract failed')
    if not any(s['flags'] & 1 and int(s['address'], 16) <= symbols['vectors'] < int(s['address'], 16) + s['memory_bytes'] for s in segments):
        raise ValueError('Vectors outside executable segment')
    return {'entry': hex(entry), 'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data), 'segments': segments, 'vectors': hex(symbols['vectors']), 'stack_bottom': hex(symbols['__stack_bottom']), 'stack_top': hex(symbols['__stack_top'])}


def run_scenario(qemu, artifact, marker, forbidden, virtualization=False, observe_seconds=10):
    with tempfile.TemporaryDirectory(prefix='rustos-p4-run-') as directory:
        serial = Path(directory) / 'serial.log'
        command = [str(qemu), '-machine', f'virt-11.1,secure=off,virtualization={"on" if virtualization else "off"},gic-version=2', '-cpu', 'cortex-a53', '-accel', 'tcg', '-smp', '1', '-m', '128M', '-display', 'none', '-monitor', 'none', '-serial', 'file:' + str(serial), '-qmp', 'stdio', '-nic', 'none', '-kernel', str(artifact)]
        start = time.monotonic()
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        qmp = queue.Queue()
        def read_qmp():
            try:
                for line in process.stdout:
                    qmp.put(json.loads(line))
            except Exception as error:
                qmp.put({'reader_error': str(error)})
        thread = threading.Thread(target=read_qmp, daemon=True)
        thread.start()
        error = None
        saw_marker = False
        requested_stop = False
        forced_stop = False
        output = ''
        stderr = ''
        try:
            greeting = qmp.get(timeout=5)
            if 'QMP' not in greeting:
                raise RuntimeError('No QMP greeting')
            process.stdin.write('{"execute":"qmp_capabilities"}\n')
            process.stdin.flush()
            while True:
                message = qmp.get(timeout=max(.01, start + observe_seconds - time.monotonic()))
                if 'return' in message:
                    break
                if 'error' in message or 'reader_error' in message:
                    raise RuntimeError(str(message))
            while time.monotonic() - start < observe_seconds:
                if process.poll() is not None:
                    raise RuntimeError('QEMU exited before runner stop')
                if serial.exists():
                    raw = serial.read_bytes()
                    output = raw.decode('utf-8')
                    if serial_marker(raw, marker, forbidden):
                        saw_marker = True
                        break
                time.sleep(.01)
            if marker is not None and not saw_marker:
                raise RuntimeError('Expected marker missing at deadline')
            if marker is None and output:
                raise RuntimeError('Unsupported entry unexpectedly reached serial output')
        except Exception as caught:
            error = str(caught)
        finally:
            if process.poll() is None:
                try:
                    requested_stop = True
                    process.stdin.write('{"execute":"quit"}\n')
                    process.stdin.flush()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    forced_stop = True
                    process.kill()
                    process.wait(timeout=5)
            stderr = process.stderr.read(1048577)
            thread.join(timeout=5)
            if thread.is_alive() or process.poll() is None:
                error = 'Owned process/reader did not settle'
            if serial.exists():
                output = serial.read_bytes()[:1048577].decode(errors='replace')
                try:
                    serial_marker(serial.read_bytes(), marker, forbidden)
                except ValueError as caught:
                    error = str(caught)
            if any(bad in output for bad in forbidden) or len(output.encode()) > 1048576 or len(stderr.encode()) > 1048576:
                error = 'Post-stop fault marker or output overflow'
            if process.returncode != 0 or forced_stop:
                error = error or 'QMP shutdown did not complete normally'
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
        return {'passed': error is None, 'error': error, 'expected_marker': marker, 'observed_marker': saw_marker, 'serial_output': output, 'stderr': stderr, 'stop_requested': requested_stop, 'forced_stop': forced_stop, 'process_settled': process.poll() is not None, 'elapsed_seconds': round(time.monotonic() - start, 3), 'control': 'QMP over owned stdio; P5 named-pipe/Job ownership not implemented'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, default=Path(r'C:\Program Files\qemu\qemu-system-aarch64.exe'))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    results = []
    for variant, feature, marker, forbidden in [
        ('normal', None, 'RUSTOS_BOOT_OK', ['RUSTOS_EXPECTED_PANIC', 'RUSTOS_UNEXPECTED_PANIC', 'RUSTOS_EXCEPTION']),
        ('panic', 'panic-test', 'RUSTOS_EXPECTED_PANIC', ['RUSTOS_BOOT_OK', 'RUSTOS_UNEXPECTED_PANIC', 'RUSTOS_EXCEPTION']),
        ('fault', 'fault-test', 'RUSTOS_EXCEPTION', ['RUSTOS_BOOT_OK', 'RUSTOS_EXPECTED_PANIC', 'RUSTOS_UNEXPECTED_PANIC']),
        ('unexpected-panic', 'unexpected-panic-test', 'RUSTOS_UNEXPECTED_PANIC', ['RUSTOS_BOOT_OK', 'RUSTOS_EXPECTED_PANIC', 'RUSTOS_EXCEPTION']),
    ]:
        build_dir = ROOT / 'target/p4' / variant
        command = ['cargo', 'build', '--locked', '-p', 'rustos-kernel', '--release', '--target', TARGET, '--target-dir', str(build_dir)]
        if feature:
            command += ['--features', feature]
        subprocess.run(command, cwd=ROOT, check=True)
        artifact = build_dir / TARGET / 'release/rustos-kernel'
        elf = inspect_elf(artifact)
        observed = run_scenario(args.qemu.resolve(strict=True), artifact, marker, forbidden)
        if variant == 'fault' and 'ESR=0xf2000000' not in observed['serial_output']:
            observed.update(passed=False, error='Injected BRK did not report expected ESR')
        results.append({'scenario': variant, 'artifact': str(artifact.relative_to(ROOT)), 'elf': elf, **observed})
        print(variant + ': ' + ('PASS' if observed['passed'] else 'FAIL'), flush=True)
    normal = ROOT / 'target/p4/normal' / TARGET / 'release/rustos-kernel'
    wrong_entry = run_scenario(args.qemu.resolve(strict=True), normal, None, ['RUSTOS_BOOT_OK'], virtualization=True, observe_seconds=2)
    results.append({'scenario': 'unsupported-entry-negative', **wrong_entry})
    report = {'scope': 'P4 kernel development evidence; not an assembler bundle or production verification report', 'qemu': subprocess.run([str(args.qemu), '--version'], capture_output=True, text=True, check=True).stdout.splitlines()[0], 'rustc': subprocess.run(['rustc', '--version'], capture_output=True, text=True, check=True).stdout.strip(), 'passed': all(r['passed'] for r in results), 'scenarios': results}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    if args.report.exists():
        raise RuntimeError('Refusing to replace an existing evidence report')
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Evidence: ' + str(args.report), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
