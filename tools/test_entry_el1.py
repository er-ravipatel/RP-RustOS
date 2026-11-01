"""D21 EL1 experiment after the existing complete stackless preflight."""
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, symbols
from test_entry_memory_reference import fixture
from probe_entry_machines import probe


def main():
    folder = ROOT / 'target' / f'entry-el1-{time.time_ns()}'
    folder.mkdir(parents=True)
    original = (ROOT / 'tools/entry-harness/handoff.S').read_text()
    guard_boundary = '.ifdef TEST_HEADER\n'
    assert original.count(guard_boundary) == 1
    guards = (ROOT / 'tools/entry-harness/cpu-guards.S').read_text()
    original = original.replace(guard_boundary, guards+'\n'+guard_boundary)
    transition = (ROOT / 'tools/entry-harness/el1-transition.S').read_text()
    boundary = '    mov x12, x0\n'
    assert original.count(boundary) == 1
    source = original.replace(boundary, transition + '\n' + boundary)
    sysroot = Path(subprocess.check_output(['rustc', '--print', 'sysroot'], text=True).strip())
    linker = sysroot / 'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    cases = []
    definitions = [
        ('normal', 0x8000000, False, None, None, 'success'),
        ('el1_fault', 0x8000000, True, None, None, 'fault'),
        ('invalid_ram', 0, False, None, None, 'failure'),
        ('wrong_cpu', 0x8000000, False, 'MIDR', 0x410fd070, 'failure'),
        ('a53_variant_revision', 0x8000000, False, 'MIDR', 0x412fd033, 'success'),
        ('mpidr_non_affinity_flags', 0x8000000, False, 'AFFINITY', 0xc0000000, 'success'),
    ]
    definitions += [(f'affinity_{i}', 0x8000000, False, 'AFFINITY', 1 << shift, 'secondary')
                    for i, shift in enumerate([0, 8, 16, 32])]
    definitions += [(name, 0x8000000, False, 'CONTROL', 0x30c50830 | bit, 'failure')
                    for name, bit in [('modeled_mmu_on', 1), ('modeled_data_cache_on', 4),
                                      ('modeled_instruction_cache_on', 0x1000), ('modeled_big_endian', 0x2000000)]]
    for name, ram_size, fault, key, value, expected in definitions:
        rust, obj, elf, dtb = [folder / (name + suffix) for suffix in ('.rs', '.o', '.elf', '.dtb')]
        constants = '\n'.join('.equ TEST_' + key + ', 1' for key in
                              ['HEADER', 'TREE', 'ROOT', 'RAM', 'STATIC', 'CMA'])
        if key is not None:
            constants += f'\n.equ TEST_{key}, {value}'
        if fault:
            constants += '\n.equ TEST_EL1_FAULT, 1'
        rust.write_text('#![no_std]\ncore::arch::global_asm!(' + json.dumps('.arch armv8-a+simd\n' + constants + '\n' + source) + ');\n')
        subprocess.run(['rustc', str(rust), '--crate-type', 'lib', '--target',
                        'aarch64-unknown-none-softfloat', '--emit=obj', '-o', str(obj)], check=True)
        subprocess.run([str(linker), '-flavor', 'gnu', '-T', str(ROOT / 'tools/entry-harness/link.ld'),
                        str(obj), '-o', str(elf)], check=True)
        dtb.write_bytes(fixture([(0, ram_size)]))
        linked = symbols(elf.read_bytes())
        result = probe('C:/Program Files/qemu/qemu-system-aarch64.exe', 'raspi3b',
                       ['-device', f'loader,file={elf},cpu-num=0', '-device',
                        f'loader,file={dtb},addr=0x1000000,force-raw=on'], run=True)
        registers = result['observed_registers']
        def reg(key):
            match = re.search(r'\b' + key + r'=([0-9a-fA-F]+)', registers)
            return int(match.group(1), 16) if match else None
        park = {'fault':'fault_park', 'failure':'failure_park', 'success':'success_park', 'secondary':'secondary_park'}[expected]
        early = expected in ('failure', 'secondary')
        checks = {'marker': reg('X10') == {'fault':0xf00d,'failure':0xffff,'secondary':0,'success':0x50415353}[expected],
                  'park': reg('PC') in (linked[park], linked[park]+4),
                  'level': ('EL2h' if early else 'EL1h') in registers,
                  'stack': reg('SP') == (0 if early else 0x400000)}
        if fault:
            checks['el1_brk_syndrome'] = reg('X14') is not None and reg('X14') >> 26 == 0x3c
        cases.append({'name': name, 'passed': all(checks.values()), 'checks': checks,
                      'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(), 'qemu': result})
    report = {'passed': all(c['passed'] for c in cases), 'cases': cases,
              'scope': 'EL1 readbacks/fault and injected MIDR, affinity, SCTLR inputs; injected values test guard logic, not actual alternate hardware or live MMU/cache changes'}
    path = folder / 'report.json'
    path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': report['passed'], 'report': str(path),
                      'checks': {c['name']:c['checks'] for c in cases}}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

