"""Synthetic DTB reference cases for the future stackless memory pass."""
import hashlib
import json
import struct
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Tree:
    def __init__(self):
        self.structure = bytearray()
        self.strings = bytearray()

    def word(self, value):
        self.structure.extend(struct.pack('>I', value))

    def pad(self):
        self.structure.extend(b'\0' * (-len(self.structure) % 4))

    def begin(self, name):
        self.word(1)
        self.structure.extend(name.encode() + b'\0')
        self.pad()

    def prop(self, name, value):
        self.word(3)
        self.word(len(value))
        self.word(len(self.strings))
        self.strings.extend(name.encode() + b'\0')
        self.structure.extend(value)
        self.pad()

    def finish(self):
        self.word(2)
        self.word(9)
        result = bytearray(56)
        for offset, value in [(0, 0xd00dfeed), (4, 56+len(self.structure)+len(self.strings)),
                              (8, 56), (12, 56+len(self.structure)), (16, 40),
                              (20, 17), (24, 16), (32, len(self.strings)), (36, len(self.structure))]:
            struct.pack_into('>I', result, offset, value)
        return result + self.structure + self.strings


def fixture(banks, cells=1, status=None, reserved=None, dynamic=False,
            device_type=b'memory\0', memory_name='memory@0', reg_override=False,
            reserved_cells=None, reserved_ranges=b'', reserved_status=None,
            dynamic_props=None, dynamic_name='linux,cma', extra_memory_name=None,
            extra_memory_type=b'memory\0'):
    tree = Tree()
    tree.begin('')
    tree.prop('compatible', b'raspberrypi,model-zero-2-w\0')
    tree.prop('#address-cells', struct.pack('>I', cells))
    tree.prop('#size-cells', struct.pack('>I', cells))
    def integer(value):
        return value.to_bytes(cells*4, 'big')
    tree.begin(memory_name)
    if device_type is not None:
        tree.prop('device_type', device_type)
    reg = b''.join(integer(start)+integer(size) for start, size in banks) if reg_override is False else reg_override
    if reg is not None:
        tree.prop('reg', reg)
    if status:
        tree.prop('status', status)
    tree.word(2)
    if extra_memory_name is not None:
        tree.begin(extra_memory_name)
        tree.prop('device_type', extra_memory_type)
        tree.prop('reg', integer(0)+integer(0x1000))
        tree.word(2)
    if reserved is not None or dynamic:
        tree.begin('reserved-memory')
        parent_cells = cells if reserved_cells is None else reserved_cells
        tree.prop('#address-cells', struct.pack('>I', parent_cells))
        tree.prop('#size-cells', struct.pack('>I', parent_cells))
        if reserved_ranges is not None:
            tree.prop('ranges', reserved_ranges)
        if reserved_status is not None:
            tree.prop('status', reserved_status)
        tree.begin(dynamic_name if dynamic else 'region')
        if dynamic:
            properties = {'compatible':b'shared-dma-pool\0', 'size':integer(64*1024*1024),
                          'reusable':b'', 'linux,cma-default':b''}
            properties.update(dynamic_props or {})
            for key,value in properties.items():
                if value is not None:
                    tree.prop(key,value)
        else:
            tree.prop('reg', integer(reserved[0])+integer(reserved[1]))
        tree.word(2)
        tree.word(2)
    return tree.finish()


def main():
    folder = ROOT / 'target' / f'entry-memory-reference-{time.time_ns()}'
    folder.mkdir(parents=True)
    command = ['cargo', 'build', '--manifest-path', str(ROOT/'bsp/rpi-zero2w/Cargo.toml'),
               '--example', 'inspect_memory', '--locked', '--offline']
    build = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (folder/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    executable = ROOT/'bsp/rpi-zero2w/target/debug/examples/inspect_memory.exe'
    ram = [(0, 128*1024*1024)]
    cases = [
        ('one_cell_ram', fixture(ram), 'OK'),
        ('two_cell_ram', fixture(ram, cells=2), 'OK'),
        ('static_zero_placeholder', fixture([(0, 0)]), 'ERR Ranges(Empty)'),
        ('partial_kernel', fixture([(0, 0x300000)]), 'ERR Ranges(KernelNotInRam)'),
        ('partial_dtb', fixture([(0, 0x1000001)]), 'ERR Ranges(DtbNotInRam)'),
        ('disabled_ram', fixture(ram, status=b'disabled\0'), 'ERR Ranges(Count)'),
        ('unknown_status', fixture(ram, status=b'unknown\0'), 'ERR Status'),
        ('overlapping_banks', fixture(ram+[(0,0x1000)]), 'ERR Ranges(OverlappingRam)'),
        ('split_kernel', fixture([(0,0x300000),(0x300000,0x5000000)]), 'ERR Ranges(KernelNotInRam)'),
        ('reserved_kernel_byte', fixture(ram, reserved=(0x200000,1)), 'ERR Ranges(KernelReserved)'),
        ('reserved_dtb', fixture(ram, reserved=(0x1000000,0x1000)), 'OK'),
        ('dynamic_cma', fixture(ram, dynamic=True), 'OK'),
        ('dynamic_no_space', fixture([(0,0x2000000)], dynamic=True), 'ERR Pool(NoSpace)'),
        ('outside_board', fixture([(0,0x20000001)]), 'ERR Ranges(AddressBounds)'),
    ]
    results = []
    for name, data, expected in cases:
        path = folder/f'{name}.dtb'
        path.write_bytes(data)
        output = subprocess.run([str(executable), str(path), '1000000'], capture_output=True,
                                text=True, timeout=10, check=True).stdout.strip()
        passed = output.startswith('OK ') if expected == 'OK' else output == expected
        if name == 'dynamic_cma':
            passed = output == 'OK BootMemoryInfo { cma_pool: Some(MemoryRange { start: 67108864, size: 67108864 }) }'
        results.append({'name':name, 'fixture':str(path), 'sha256':hashlib.sha256(data).hexdigest(),
                        'expected':expected, 'actual':output, 'passed':passed})
    report = {'passed':all(case['passed'] for case in results), 'cases':results,
              'build_command':command, 'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
              'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in [Path(__file__).resolve(), ROOT/'bsp/rpi-zero2w/examples/inspect_memory.rs',
                                            *sorted((ROOT/'bsp/rpi-zero2w/src').glob('*.rs'))]},
              'scope':'Host Rust reference only; no assembly RAM pass, emulator or physical boot'}
    path = folder/'report.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'case_count':len(results),
                      'failed_cases':[case for case in results if not case['passed']], 'report':str(path)}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
