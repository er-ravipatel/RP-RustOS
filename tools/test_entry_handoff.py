"""Build and run a test-only, stackless QEMU EL3-to-EL2 adapter."""
import hashlib
import json
import re
import subprocess
import struct
import time
from pathlib import Path
from probe_entry_machines import probe

ROOT = Path(__file__).resolve().parents[1]
READ_ONLY_MNEMONICS = {'msr', 'mrs', 'and', 'bic', 'lsl', 'sub', 'subs', 'cbnz', 'cbz', 'mov', 'movz', 'movk', 'cmp', 'b.eq', 'b.ne', 'b.lo', 'b.hs', 'b.cs', 'b.hi', 'ldr', 'ldrb', 'adr', 'eret', 'tst', 'wfe', 'b', 'rev', 'add', 'adds', 'orr', 'isb', 'brk'}


def symbols(data):
    if data[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('Expected ELF64 little endian')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, header[6] + i * header[11]) for i in range(header[12])]
    result = {}
    for section in sections:
        if section[1] != 2:
            continue
        names = sections[section[6]]
        strings = data[names[4]:names[4]+names[5]]
        for offset in range(section[4], section[4]+section[5], section[9]):
            name, _, _, _, value, _ = struct.unpack_from('<IBBHQQ', data, offset)
            end = strings.index(0, name)
            result[strings[name:end].decode()] = value
    return result


def virtual_bytes(data, address, size):
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    for i in range(header[12]):
        section = struct.unpack_from('<IIQQQQIIQQ', data, header[6]+i*header[11])
        if section[1] == 1 and section[3] <= address and address+size <= section[3]+section[5]:
            offset = section[4]+address-section[3]
            return data[offset:offset+size]
    raise ValueError('Missing linked code bytes')


def main():
    folder = ROOT / 'target' / f'entry-handoff-{time.time_ns()}'
    folder.mkdir(parents=True)
    source = ROOT / 'tools/entry-harness/handoff.S'
    sysroot = Path(subprocess.check_output(['rustc', '--print', 'sysroot'], text=True).strip())
    linker = sysroot / 'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    cases = []
    for name, spsr, sctlr, level in [('normal', 0x3c9, 0x30c50830, 8), ('unexpected_el1', 0x3c5, 0x30c50830, 4), ('instruction_cache_on', 0x3c9, 0x30c51830, 8)]:
        cases.append(run_case(folder, source, linker, name, spsr, sctlr, level))
    valid = bytearray(72)
    for offset, value in [(0,0xd00dfeed),(4,72),(8,56),(12,72),(16,40),(20,17),(24,16),(32,0),(36,16)]:
        struct.pack_into('>I', valid, offset, value)
    # Header fixtures are not claimed to contain a validated token tree.
    for name, offset, value in [('header_valid',None,None),('bad_magic',0,0),('oversized',4,0x200001),('bad_version',20,15),('bad_block',8,57),('bad_strings',32,1)]:
        fixture = valid.copy()
        if offset is not None:
            struct.pack_into('>I',fixture,offset,value)
        cases.append(run_case(folder, source, linker, name, 0x3c9, 0x30c50830, 8, fixture=fixture, expected='success' if name=='header_valid' else 'failure'))
    for name, pointer in [('misaligned_pointer',0x1000001),('kernel_pointer',0x200000),('ceiling_pointer',0x1ffffff0),('low_pointer',0),('overflow_pointer',0xfffffffffffffff8)]:
        cases.append(run_case(folder, source, linker, name, 0x3c9, 0x30c50830, 8, pointer=pointer, expected='failure', header=True))
    cases.append(run_case(folder, source, linker, 'synchronous_brk', 0x3c9, 0x30c50830, 8, expected='fault', header=True))
    map_cases = [
        ('reserved_low', [(0,0x1000)], True, 'success'),
        ('reserved_kernel', [(0x200000,1)], True, 'failure'),
        ('reserved_touch', [(0x1fffff,1)], True, 'success'),
        ('reserved_overlap', [(0,0x2000),(0x1000,0x2000)], True, 'failure'),
        ('reserved_wrap', [(0xfffffffffffffff0,0x20)], True, 'failure'),
        ('reserved_outside', [(0x20000000,1)], True, 'failure'),
        ('reserved_unterminated', [(0,0x1000)], False, 'failure'),
        ('reserved_limit', [(i*0x1000,1) for i in range(128)], True, 'success'),
        ('reserved_excess', [(i*0x1000,1) for i in range(129)], True, 'failure'),
        ('reserved_zero_size', [(0x1000,0)], True, 'success'),
    ]
    for name, records, terminated, expected in map_cases:
        begin = 40 + 16*(len(records)+int(terminated))
        fixture = bytearray(begin+16)
        for offset,value in [(0,0xd00dfeed),(4,len(fixture)),(8,begin),(12,len(fixture)),(16,40),(20,17),(24,16),(32,0),(36,16)]:
            struct.pack_into('>I',fixture,offset,value)
        for i,(address,size) in enumerate(records):
            struct.pack_into('>QQ',fixture,40+i*16,address,size)
        cases.append(run_case(folder, source, linker, name, 0x3c9, 0x30c50830, 8, fixture=fixture, expected=expected))
    tree_cases = [
        ('tree_minimal',[1,0,2,9],b'\0','success'),
        ('tree_nested',[1,0,1,0x78000000,2,2,9],b'\0','success'),
        ('tree_property',[1,0,3,4,0,42,2,9],b'value\0','success'),
        ('tree_unknown',[1,0,5,2,9],b'\0','failure'),
        ('tree_no_end',[1,0,2,4],b'\0','failure'),
        ('tree_extra_end',[1,0,2,2,9],b'\0','failure'),
        ('tree_name_offset',[1,0,3,0,20,2,9],b'x\0','failure'),
        ('tree_property_length',[1,0,3,0xffffffff,0,2,9],b'x\0','failure'),
        ('tree_padding',[1,0,3,1,0,0x01ff0000,2,9],b'x\0','failure'),
        ('tree_after_child',[1,0,1,0x78000000,2,3,0,0,2,9],b'x\0','failure'),
        ('tree_depth',[1,0]+[1,0x78000000]*16+[2]*17+[9],b'\0','failure'),
        ('tree_duplicate_offset',[1,0,3,0,0,3,0,0,2,9],b'x\0','failure'),
        ('tree_duplicate_bytes',[1,0,3,0,0,3,0,2,2,9],b'x\0x\0','failure'),
        ('tree_name_prefix',[1,0,3,0,0,4,3,0,2,2,9],b'x\0xx\0','success'),
        ('tree_sibling_names',[1,0,1,0x61000000,3,0,0,2,1,0x62000000,3,0,0,2,2,9],b'x\0','success'),
        ('tree_token_boundary',[4]*16381+[1,0,2,9],b'\0','success'),
        ('tree_token_excess',[4]*16382+[1,0,2,9],b'\0','failure'),
    ]
    for name, count, prefix, expected in [('tree_property_boundary',256,'p','success'),('tree_property_limit',257,'p','failure'),('tree_duplicate_work_limit',256,'a'*120,'failure')]:
        strings = bytearray()
        tokens = [1,0]
        for i in range(count):
            tokens.extend([3,0,len(strings)])
            strings.extend(f'{prefix}{i:03d}'.encode()+b'\0')
        tokens.extend([2,9])
        tree_cases.append((name,tokens,strings,expected))
    for name,tokens,strings,expected in tree_cases:
        structure = b''.join(struct.pack('>I',token) for token in tokens)
        fixture = bytearray(56+len(structure)+len(strings))
        for offset,value in [(0,0xd00dfeed),(4,len(fixture)),(8,56),(12,56+len(structure)),(16,40),(20,17),(24,16),(32,len(strings)),(36,len(structure))]:
            struct.pack_into('>I',fixture,offset,value)
        fixture[56:56+len(structure)] = structure
        fixture[56+len(structure):] = strings
        cases.append(run_case(folder,source,linker,name,0x3c9,0x30c50830,8,fixture=fixture,expected=expected,tree=True))
    board = b'raspberrypi,model-zero-2-w\0'
    root_cases = [
        ('root_valid',board,1,1,'success'),
        ('root_two_cells',board,2,2,'success'),
        ('root_list',b'brcm,bcm2837\0'+board,1,2,'success'),
        ('root_wrong',b'raspberrypi,5-model-b\0',1,1,'failure'),
        ('root_prefix',board[:-1]+b'-extra\0',1,1,'failure'),
        ('root_unterminated',board[:-1],1,1,'failure'),
        ('root_empty',b'',1,1,'failure'),
        ('root_empty_entry',board+b'\0',1,1,'failure'),
        ('root_bad_tail',board+b'bad\xff\0',1,1,'failure'),
        ('root_missing_board',None,1,1,'failure'),
        ('root_zero_cells',board,0,1,'failure'),
        ('root_large_cells',board,1,3,'failure'),
        ('root_missing_cells',board,None,1,'failure'),
    ]
    for name,compatible,addresses,sizes,expected in root_cases:
        names = bytearray()
        structure = bytearray(struct.pack('>III',4,1,0)) # Leading NOP is valid.
        for key,value in [(b'compatible',compatible),(b'#address-cells',None if addresses is None else struct.pack('>I',addresses)),(b'#size-cells',struct.pack('>I',sizes))]:
            if value is None:
                continue
            offset = len(names); names.extend(key+b'\0')
            structure.extend(struct.pack('>III',3,len(value),offset)); structure.extend(value)
            structure.extend(b'\0'*(-len(structure)%4))
        structure.extend(struct.pack('>II',2,9))
        fixture = bytearray(56+len(structure)+len(names))
        for offset,value in [(0,0xd00dfeed),(4,len(fixture)),(8,56),(12,56+len(structure)),(16,40),(20,17),(24,16),(32,len(names)),(36,len(structure))]:
            struct.pack_into('>I',fixture,offset,value)
        fixture[56:56+len(structure)] = structure
        fixture[56+len(structure):] = names
        cases.append(run_case(folder,source,linker,name,0x3c9,0x30c50830,8,fixture=fixture,expected=expected,tree=True,root=True,root_cells=(addresses,sizes)))
    report = {'passed': all(case['passed'] for case in cases), 'cases': cases,
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'scope': 'Harness structure/root checks; no RAM/reserved-memory tree semantics, safe stack or production kernel'}
    path = folder / 'report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'case_count': len(cases),
                      'failed_cases': {case['name']:case['checks'] for case in cases if not case['passed']}, 'report': str(path)}))
    if not report['passed']:
        raise SystemExit(1)


def run_case(folder, source, linker, name, spsr, sctlr, level, fixture=None, pointer=0x1000000, expected=None, header=False, tree=False, root=False, root_cells=(1,1), ram=False, static=False, cma=False):
    rust = folder / f'{name}.rs'
    constants = f'.equ TEST_SPSR, {spsr}\n.equ TEST_SCTLR, {sctlr}\n.equ TEST_DTB, {pointer}'
    if header or fixture is not None:
        constants += '\n.equ TEST_HEADER, 1'
    if expected == 'fault':
        constants += '\n.equ TEST_FAULT, 1'
    if tree:
        constants += '\n.equ TEST_TREE, 1'
    if root:
        constants += '\n.equ TEST_ROOT, 1'
    if ram:
        constants += '\n.equ TEST_RAM, 1'
    if static:
        constants += '\n.equ TEST_STATIC, 1'
    if cma:
        constants += '\n.equ TEST_CMA, 1'
    rust.write_text('#![no_std]\ncore::arch::global_asm!(' + json.dumps(constants) + ');\ncore::arch::global_asm!(include_str!(r"' + str(source) + '"));\n')
    obj, elf = folder / f'{name}.o', folder / f'{name}.elf'
    commands = [
        ['rustc', str(rust), '--crate-type', 'lib', '--target', 'aarch64-unknown-none-softfloat', '--emit=obj', '-o', str(obj)],
        [str(linker), '-flavor', 'gnu', '-T', str(ROOT / 'tools/entry-harness/link.ld'), str(obj), '-o', str(elf)],
    ]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    linked_symbols = symbols(elf.read_bytes())
    start = linked_symbols['_start']
    count = (linked_symbols['harness_code_end'] - start) // 4
    extra = ['-device', f'loader,file={elf},cpu-num=0']
    if fixture is not None:
        fixture_path = folder / f'{name}.dtb'
        fixture_path.write_bytes(fixture)
        extra += ['-device', f'loader,file={fixture_path},addr=0x{pointer:x},force-raw=on']
    result = probe('C:/Program Files/qemu/qemu-system-aarch64.exe', 'raspi3b', extra, run=True, disassemble=(start, count))
    registers = result['observed_registers']
    def register(name):
        match = re.search(r'\b' + name + r'=([0-9a-fA-F]+)', registers)
        return int(match.group(1), 16) if match else None
    expected = expected or ('success' if name == 'normal' else 'failure')
    normal = expected == 'success'
    park = linked_symbols[{'success':'success_park','failure':'failure_park','fault':'fault_park'}[expected]]
    checks = {'marker': register('X10') == {'success':0x50415353,'failure':0xffff,'fault':0xf00d}[expected],
              'expected_level': register('X11') == level,
              'park_pc': register('PC') in (park, park+4),
              'pstate': ('EL2h' if level == 8 else 'EL1h') in registers}
    if normal:
        checks.update(dtb_register=register('X12') == pointer,
                      mmu_caches_off=register('X13') is not None and register('X13') & 0x1005 == 0)
        if root:
            checks['decoded_root_cells'] = (register('X29'),register('X30')) == root_cells
    instructions = re.findall(r'^0x[0-9a-fA-F]+:\s+[0-9a-fA-F]{8}\s+(\S+)([^\r\n]*)', result['disassembly'], re.MULTILINE)
    allowed = READ_ONLY_MNEMONICS
    if expected == 'fault':
        checks['brk_syndrome'] = register('X14') is not None and register('X14') >> 26 == 0x3c
    checks['all_instructions_decoded'] = len(instructions) == count
    checks['no_stores_calls_or_stack_operands'] = bool(instructions) and all(
        mnemonic in allowed and not re.search(r'\b(?:sp|wsp)\b', operands)
        for mnemonic, operands in instructions)
    if name == 'tree_duplicate_work_limit':
        checks['work_budget_exhausted'] = register('X14') == 0
    vector_base = linked_symbols['early_vectors']
    vector_data = virtual_bytes(elf.read_bytes(), vector_base, 2048)
    vector_ok = vector_base % 2048 == 0
    for slot in range(16):
        instruction = struct.unpack_from('<I', vector_data, slot*128)[0]
        displacement = instruction & 0x3ffffff
        if displacement & (1<<25):
            displacement -= 1<<26
        vector_ok &= instruction >> 26 == 0b000101 and vector_base+slot*128+displacement*4 == linked_symbols['early_fault']
        vector_ok &= vector_data[slot*128+4:(slot+1)*128] == struct.pack('<I',0xd503201f)*31
    checks['vector_branches_and_padding'] = bool(vector_ok)
    return {'name':name, 'checks': checks, 'passed': all(checks.values()), 'qemu': result,
              'commands': commands, 'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
              'symbols': linked_symbols, 'instruction_count':count}


if __name__ == '__main__':
    main()
