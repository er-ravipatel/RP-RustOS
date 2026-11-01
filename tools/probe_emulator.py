"""Check the M1 emulator contract using a tiny synthetic AArch64 ELF.

This fixture is not RustOS and does not satisfy its startup/panic acceptance tests.
Only the QEMU process started here is terminated. No guest disks are attached.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile


def fixture():
    marker = b'RUSTOS_ENV_PROBE_OK\n'
    # ldr x1, UART literal; repeated movz w0 / str w0,[x1]; branch to itself.
    words = [0] + [word for byte in marker for word in (0x52800000 | (byte << 5), 0xB9000020)] + [0x14000000]
    words[0] = 0x58000001 | (len(words) << 5)
    code = struct.pack('<' + 'I' * len(words), *words) + struct.pack('<Q', 0x09000000)
    header = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF\x02\x01\x01' + bytes(9), 2, 183, 1, 0x40080000, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    segment = struct.pack('<IIQQQQQQ', 1, 5, 0x1000, 0x40080000, 0x40080000, len(code), len(code), 0x1000)
    return (header + segment).ljust(0x1000, b'\0') + code, marker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', default=r'C:\Program Files\qemu\qemu-system-aarch64.exe')
    args = parser.parse_args()
    executable = str(Path(args.qemu).resolve(strict=True))
    version = subprocess.run([executable, '--version'], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    artifact, marker = fixture()
    with tempfile.TemporaryDirectory(prefix='rustos-env-probe-') as directory:
        path = Path(directory) / 'probe.elf'
        path.write_bytes(artifact)
        command = [executable, '-machine', 'virt-11.1,secure=off,virtualization=off,gic-version=2', '-cpu', 'cortex-a53', '-accel', 'tcg', '-smp', '1', '-m', '128M', '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-nic', 'none', '-kernel', str(path)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timeout_reached = False
        try:
            output, error = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            timeout_reached = True
            process.terminate()
            try:
                output, error = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                output, error = process.communicate(timeout=5)
        passed = timeout_reached and marker in output
        result = {'scope': 'synthetic environment probe, not RustOS verification', 'passed': passed, 'qemu': version, 'machine': 'virt-11.1', 'cpu': 'cortex-a53', 'ram': '128M', 'artifact_sha256': hashlib.sha256(artifact).hexdigest(), 'entry': '0x40080000', 'uart': '0x09000000', 'serial_output': output.decode(errors='replace'), 'stderr': error.decode(errors='replace'), 'expected_halt_loop_reached_deadline': timeout_reached, 'process_settled': process.poll() is not None}
        print(json.dumps(result, indent=2))
        return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
