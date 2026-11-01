"""Validate the exact ELF outputs recorded by the internal Pi compiler."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from check_entry_stack import audit
from test_entry_handoff import symbols


def layout(data):
    if len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('Expected ELF64 little endian')
    h = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    if h[1:4] != (2, 183, 1) or h[4] != 0x200000 or h[8:10] != (64, 56):
        raise ValueError('Wrong executable architecture, entry or header size')
    if not 0 < h[10] <= 32 or h[5] + h[10]*56 > len(data):
        raise ValueError('Invalid program header table')
    if h[11] != 64 or not 0 < h[12] <= 256 or h[6]+h[12]*64 > len(data):
        raise ValueError('Invalid section header table')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, h[6]+i*64) for i in range(h[12])]
    for section in sections:
        if section[1] != 8 and section[4]+section[5] > len(data):
            raise ValueError('Section outside ELF')
        if section[1] == 2 and (section[9] != 24 or section[5] % 24 or section[6] >= len(sections)):
            raise ValueError('Invalid symbol table')
    loads = []
    for i in range(h[10]):
        kind, flags, offset, va, pa, filesz, memsz, align = struct.unpack_from('<IIQQQQQQ', data, h[5]+i*56)
        if kind != 1:
            continue
        if not memsz or filesz > memsz or offset+filesz > len(data) or va != pa:
            raise ValueError('Invalid load segment')
        if va < 0x200000 or va+memsz > 0x3f0000 or flags & ~7 or flags & 3 == 3:
            raise ValueError('Load segment violates kernel budget or W^X')
        if align not in (0, 1) and (align & (align-1) or va % align != offset % align):
            raise ValueError('Invalid load alignment')
        if any(va < end and start < va+memsz for start, end in loads):
            raise ValueError('Overlapping load segments')
        loads.append((va, va+memsz))
    if not loads or not any(a <= h[4] < b for a, b in loads):
        raise ValueError('Entry outside load segments')
    linked = symbols(data)
    if linked.get('_start') != 0x200000 or linked.get('__stack_bottom') != 0x3f0000 or linked.get('__stack_top') != 0x400000:
        raise ValueError('Wrong linked entry or stack boundary')
    start, end = linked['__bss_start'], linked['__bss_end']
    clock = linked['PI_CLOCK_BUFFERS']
    if not 0x200000 <= start <= end <= 0x3f0000 or start % 16 or end % 16 or clock % 64 or not start <= clock < clock+192 <= end:
        raise ValueError('Invalid BSS or permanent clock buffer extent')
    return {'entry':h[4], 'loads':loads, 'bss':[start,end], 'clock_buffer':[clock,clock+192], 'stack':[0x3f0000,0x400000]}


def check(report_path):
    report = json.loads(report_path.read_text())
    variants = report['variants']
    if [(v['variant'], v['features']) for v in variants] != [('normal', []), ('panic-test', ['panic-test'])]:
        raise ValueError('Unexpected variant features')
    results = []
    for variant in variants:
        elf = Path(variant['elf'])
        data = elf.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != variant['sha256']:
            raise ValueError('Compiled artifact hash changed')
        memory = layout(data)
        stack = audit(elf, include_console=True)
        if not stack['passed'] or stack['elf_sha256'] != digest:
            raise ValueError('Stack audit rejected artifact')
        results.append({'variant':variant['variant'], 'sha256':digest, 'layout':memory, 'stack':stack})
    return {'passed':True, 'compiler_report':str(report_path), 'compiler_report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(), 'variants':results, 'limits':'Exact linked ELF layout and conservative stack analysis only; not physical firmware or full entry-behavior acceptance.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.compiler_report)
    with args.report.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'passed':True, 'variants':[{ 'variant':v['variant'], 'stack_bound':v['stack']['stack_bound']} for v in result['variants']]}))
