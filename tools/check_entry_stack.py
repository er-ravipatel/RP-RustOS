"""Conservative stack bound for a specific linked D21 test ELF; fail closed."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from probe_entry_machines import probe
from test_entry_handoff import symbols, virtual_bytes


def function_symbols(data):
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, header[6]+i*header[11])
                for i in range(header[12])]
    functions = {}
    for section in sections:
        if section[1] != 2:
            continue
        names = sections[section[6]]
        strings = data[names[4]:names[4]+names[5]]
        for offset in range(section[4], section[4]+section[5], section[9]):
            name, info, _, _, address, size = struct.unpack_from('<IBBHQQ', data, offset)
            if info & 15 == 2 and size:
                functions[address] = {'name': strings[name:strings.index(0, name)].decode(),
                                      'address': address, 'size': size}
    return functions


def number(text):
    return int(text.removeprefix('#'), 0)


def analyze(functions, instructions, roots, terminal):
    """Sum all allocations per function, then longest acyclic call/tail path.

    Summation deliberately overcounts mutually exclusive allocations and caller
    frames released before tail calls. Allocation-bearing backedges, dynamic SP,
    indirect branches/calls, unknown exits and recursion are rejected.
    """
    audited = {}
    active = set()
    terminals = terminal if isinstance(terminal, dict) else {terminal:'harness_panic_park'}

    def visit(address):
        if address in terminals:
            return 0, [terminals[address]]
        if address in active:
            raise ValueError('Recursive call graph')
        if address in audited:
            record = audited[address]
            return record['bound'], record['path']
        if address not in functions:
            raise ValueError(f'Unknown branch/call target {address:#x}')
        active.add(address)
        function = functions[address]
        end = address+function['size']
        code = [(pc, *instructions[pc]) for pc in range(address, end, 4)]
        allocations, updates, edges, tails, flow, changes = [], [], set(), set(), {}, {}
        for pc, mnemonic, operands in code:
            if mnemonic.startswith('.') or mnemonic in ('unknown', '(bad)'):
                raise ValueError('Undecoded instruction')
            successors = [] if mnemonic in ('ret', 'brk', 'b') else ([pc+4] if pc+4 < end else [])
            if mnemonic in ('br', 'blr', 'eret', 'svc', 'hvc', 'smc', 'msr'):
                raise ValueError(f'Indirect control flow at {pc:#x}')
            if mnemonic == 'ret' and operands not in ('', 'x30'):
                raise ValueError('Nonstandard return register')
            if operands.startswith('wsp,'):
                raise ValueError('Unsupported 32-bit SP operation')
            if operands.startswith('sp,') and mnemonic not in ('cmp', 'cmn', 'tst'):
                match = re.fullmatch(r'sp, sp, (#[\w-]+)(?:, lsl #(\d+))?', operands)
                if mnemonic not in ('add', 'sub') or match is None:
                    raise ValueError(f'Unsupported SP write at {pc:#x}: {mnemonic} {operands}')
                delta = number(match[1]) << int(match[2] or 0)
                updates.append(pc)
                changes[pc] = delta if mnemonic == 'sub' else -delta
                if mnemonic == 'sub' and delta > 0:
                    allocations.append((pc, delta))
                elif delta < 0:
                    raise ValueError('Negative immediate SP arithmetic')
            update = re.search(r'\[sp(?:, (#[\w-]+))?\](!|, (#[\w-]+))', operands)
            if update:
                if mnemonic not in ('stp', 'str', 'ldp', 'ldr'):
                    raise ValueError('Unsupported writeback mnemonic')
                delta = number(update[1] or '#0') if update[2] == '!' else number(update[3])
                updates.append(pc)
                changes[pc] = -delta
                if delta < 0:
                    allocations.append((pc, -delta))
            elif re.search(r'\[sp[^\]]*\](!|,)', operands):
                raise ValueError('Dynamic or unsupported SP writeback')
            elif re.search(r'\[sp, #-', operands):
                raise ValueError('Access below SP without allocation')
            is_branch = mnemonic in ('b', 'bl', 'cbz', 'cbnz', 'tbz', 'tbnz') or mnemonic.startswith('b.')
            if is_branch:
                match = re.search(r'#(0x[0-9a-f]+)$', operands)
                if match is None:
                    raise ValueError('Unknown direct branch encoding')
                target = int(match[1], 16)
                if mnemonic == 'bl' or not address <= target < end:
                    edges.add(target)
                    if mnemonic != 'bl':
                        tails.add(target)
                if mnemonic != 'bl' and address <= target < end:
                    successors.append(target)
            flow[pc] = successors
        # Cold error blocks can branch backwards across a return in address order.
        # Reject actual CFG cycles containing an SP update, not address intervals.
        for update_pc in updates:
            pending, seen = list(flow[update_pc]), set()
            while pending:
                current = pending.pop()
                if current == update_pc:
                    raise ValueError(f'Stack-changing loop in {function["name"]}')
                if current not in seen:
                    seen.add(current)
                    pending.extend(flow[current])
        # A final ordinary instruction could fall through into unreviewed code.
        last = code[-1][1]
        if last not in ('b', 'bl', 'ret', 'brk'):
            raise ValueError(f'Unreviewed function fallthrough: {function["name"]}')
        local = sum(size for _, size in allocations)
        descendants = [visit(target) for target in sorted(edges)]
        def returns(target):
            return False if target in terminals else audited[target]['may_return']
        # Prove each reachable return restores its incoming SP, so repeated calls
        # in loops cannot accumulate stack usage. Reject differing join depths.
        depths, pending = {}, [(address, 0)]
        while pending:
            pc, depth = pending.pop()
            if pc in depths:
                if depths[pc] != depth:
                    raise ValueError('Inconsistent SP depth at control-flow join')
                continue
            depths[pc] = depth
            mnemonic, operands = instructions[pc]
            after = depth+changes.get(pc, 0)
            if after < 0:
                raise ValueError('SP moves above function entry')
            if mnemonic == 'ret' and after != 0:
                raise ValueError('Return does not restore SP')
            if mnemonic == 'bl' and after % 16:
                raise ValueError('Misaligned call stack')
            if mnemonic == 'b' or mnemonic.startswith('b.'):
                target = int(re.search(r'#(0x[0-9a-f]+)$', operands)[1], 16)
                if target in tails and returns(target) and after != 0:
                    raise ValueError('Returning tail does not restore caller SP')
            pending.extend((successor, after) for successor in flow[pc])
        if last == 'bl':
            last_target = int(re.search(r'#(0x[0-9a-f]+)$', code[-1][2])[1], 16)
            if returns(last_target):
                raise ValueError('Returning call can fall through function end')
        child, path = max(descendants, default=(0, []), key=lambda item: item[0])
        record = {**function, 'frame_upper_bound': local,
                  'callees': sorted(edges), 'bound': local+child,
                  'may_return': any(m == 'ret' for _, m, _ in code) or any(returns(t) for t in tails),
                  'path': [function['name']]+path}
        audited[address] = record
        active.remove(address)
        return record['bound'], record['path']

    results = {name: visit(address) for name, address in roots.items()}
    return results, list(audited.values())


def audit(elf, include_console=False):
    data = elf.read_bytes()
    linked = symbols(data)
    functions = function_symbols(data)
    terminal = linked.get('harness_panic_park', linked.get('pi_panic_park'))
    if terminal is None:
        raise ValueError('Missing reviewed panic terminal')
    terminals={terminal:'panic_park'}
    if include_console:
        for name in ['pi_console_ready','pi_console_failed','pi_deliberate_panic_park','pi_marker_committed']:
            if name in linked:terminals[linked[name]]=name
    for address in terminals:
        if virtual_bytes(data, address, 8) != bytes.fromhex('5f2003d5ffffff17'):
            raise ValueError('Terminal must be exactly stackless WFE/branch loop')
    start = min(min(functions), linked['rust_call_begin'])
    end = max(f['address']+f['size'] for f in functions.values())
    observation = probe('C:/Program Files/qemu/qemu-system-aarch64.exe', 'raspi3b',
                        ['-device', f'loader,file={elf.resolve()},cpu-num=0'],
                        disassemble=(start, (end-start+3)//4))
    parsed = re.findall(r'^0x([0-9a-f]+):[ \t]+[0-9a-f]{8}[ \t]+(\S+)[ \t]*([^\r\n]*)',
                        observation['disassembly'], re.MULTILINE)
    instructions = {int(pc, 16): (mnemonic, operands.strip()) for pc, mnemonic, operands in parsed}
    if include_console and 'pi_marker_commit_tail' in linked:
        tail=linked['pi_marker_commit_tail']
        expected=[('dsb','sy'),('mov','x10, #0xc023'),('b',f'#{linked["pi_marker_committed"]:#x}')]
        if [instructions[tail+i*4] for i in range(3)] != expected:
            raise ValueError('Final marker tail must order MMIO and branch directly to park')
    caller_start, caller_end = linked['rust_call_begin'], linked['rust_call_end']
    caller = [(pc, *instructions[pc]) for pc in range(caller_start, caller_end, 4)]
    sp_writes = [(pc, mnemonic, operands) for pc, mnemonic, operands in caller
                 if operands.startswith(('sp,', 'wsp,')) and mnemonic not in ('cmp','cmn','tst')]
    if [(m, o) for _, m, o in sp_writes] != [('sub','sp, sp, #0x30'), ('add','sp, sp, #0x30')]:
        raise ValueError('Assembly caller must allocate/restore exactly 48 bytes')
    for pc, mnemonic, operands in caller:
        if re.search(r'\[sp[^\]]*\](!|,)', operands) or mnemonic in ('br','blr'):
            raise ValueError('Unsupported caller stack/control operation')
        if mnemonic == 'bl':
            target = int(re.search(r'#(0x[0-9a-f]+)$', operands)[1], 16)
            allowed = [linked['rustos_validate_boot_memory'], linked.get('harness_force_panic')]
            if target not in allowed or not sp_writes[0][0] < pc < sp_writes[1][0]:
                raise ValueError('Unreviewed caller function or call frame')
        elif mnemonic in ('b','cbz','cbnz','tbz','tbnz') or mnemonic.startswith('b.'):
            target = int(re.search(r'#(0x[0-9a-f]+)$', operands)[1], 16)
            if target != linked['failed']:
                raise ValueError('Caller branches must only reject to stackless failure park')
    roots = {'validator': linked['rustos_validate_boot_memory']}
    caller_frames={'validator':48}
    if 'harness_force_panic' in linked:
        roots['forced_panic'] = linked['harness_force_panic']
        caller_frames['forced_panic']=48
    if include_console:
        roots['console']=linked['pi_initialize_console']
        dispatch=linked['pi_entry_ready']
        if instructions[dispatch] != ('b', f'#{linked["pi_initialize_console"]:#x}'):
            raise ValueError('Console root must be reached by the reviewed direct dispatch')
        for pc in range(linked['rust_call_end'],dispatch,4):
            mnemonic,operands=instructions[pc]
            if mnemonic in ('bl','blr','br','msr') or (
                operands.startswith(('sp,','wsp,')) and mnemonic not in ('cmp','cmn','tst')) or re.search(r'\[sp[^\]]*\](!|,)',operands):
                raise ValueError('Post-validation dispatch changes stack or calls unreviewed code')
        caller_frames['console']=0 # Assembly restores the validator frame first.
    results, records = analyze(functions, instructions, roots, terminals)
    # The exact linked assembly boundary above allocates 48 bytes before roots.
    root_bounds={name:item[0]+caller_frames[name] for name,item in results.items()}
    bound = max(root_bounds.values())
    return {'passed': bound <= 65536, 'elf': str(elf),
            'elf_sha256': hashlib.sha256(data).hexdigest(), 'stack_budget': 65536,
            'analyzer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'qemu_command': observation['command'], 'qemu_greeting': observation['greeting'],
            'assembly_caller_frame': 48, 'stack_bound': bound, 'roots': results,
            'root_bounds':root_bounds,'root_caller_frames':caller_frames,
            'includes_post_bss_console':include_console,
            'marker_commit_tail_verified':include_console and 'pi_marker_commit_tail' in linked,
            'reachable_functions': records, 'disassembly': observation['disassembly'],
            'limits': 'Specific linked ELF and reviewed validator caller/optional direct console dispatch only; not a proof for future builds, asynchronous handlers, memory aliasing or physical firmware. Unknown control flow and stack-changing loops reject.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--console', action='store_true')
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report destination must be new')
    report = audit(args.elf, include_console=args.console)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ['passed', 'stack_bound', 'elf', 'roots']}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
