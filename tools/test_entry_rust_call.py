"""Run the real BSP validator at EL1 through its explicit C ABI."""
import hashlib
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, symbols
from test_entry_memory_reference import fixture
from probe_entry_machines import probe
from test_entry_first_write import Remote
from check_entry_stack import audit


def observe_writes(elf, dtb, linked, panic=False):
    """Watch CPU0 writes outside the entire private stack; stop at success."""
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    command = ['C:/Program Files/qemu/qemu-system-aarch64.exe', '-machine', 'raspi3b',
               '-S', '-display', 'none', '-serial', 'none', '-monitor', 'none',
               '-gdb', f'tcp:127.0.0.1:{port}', '-device', f'loader,file={elf},cpu-num=0',
               '-device', f'loader,file={dtb},addr=0x1000000,force-raw=on']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    connection = None
    try:
        deadline = time.monotonic()+5
        while connection is None:
            try:
                connection = socket.create_connection(('127.0.0.1', port), timeout=0.2)
            except OSError:
                if time.monotonic() > deadline or process.poll() is not None:
                    raise
                time.sleep(0.05)
        remote = Remote(connection)
        for request in ['Hg1', 'Hc1']:
            if remote.request(request) != 'OK':
                raise RuntimeError('Cannot select CPU0')
        sentinel = b'\xa5'*0x10000
        # Initialize in bounded chunks before enabling write observation.
        for offset in range(0, len(sentinel), 1024):
            if remote.request(f'M{0x3f0000+offset:x},400:'+sentinel[offset:offset+1024].hex()) != 'OK':
                raise RuntimeError('Cannot initialize stack sentinel')
        park = linked['harness_panic_park' if panic else 'success_park']
        watches = ['Z2,0,3f0000', 'Z2,400000,1fc00000', f'Z1,{park:x},4']
        for request in watches:
            if remote.request(request) != 'OK':
                raise RuntimeError('Debugger rejected required watch/break point')
        remote.send('c')
        try:
            stop = remote.receive()
        except socket.timeout:
            connection.sendall(b'\x03')
            stop = remote.receive()
        registers = remote.registers()
        memory = bytearray()
        for offset in range(0, 0x10000, 1024):
            memory.extend(bytes.fromhex(remote.request(f'm{0x3f0000+offset:x},400')))
        changed = [i for i, value in enumerate(memory) if value != 0xa5]
        checks = {'no_outside_stack_watch': 'watch:' not in stop,
                  'reached_expected_breakpoint': registers['pc'] == park,
                  'expected_marker': registers['x10'] == (0xface if panic else 0x50415353),
                  'stack_in_budget': 0x3f0000 <= registers['sp'] <= 0x400000,
                  'stack_used': bool(changed), 'bottom_guard': memory[:256] == sentinel[:256]}
        return {'passed': all(checks.values()), 'checks': checks, 'stop': stop,
                'observed_stack_write_extent': 0x10000-min(changed) if changed else 0,
                'scope': 'CPU0 writes in 0..512 MiB outside stack watched; finite fixtures, not a static stack bound or DMA/MMIO proof'}
    finally:
        if connection is not None:
            connection.close()
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)


def main():
    folder = ROOT / 'target' / f'entry-rust-call-{time.time_ns()}'
    folder.mkdir(parents=True)
    target = 'aarch64-unknown-none-softfloat'
    subprocess.run(['cargo', 'build', '--manifest-path', str(ROOT / 'bsp/rpi-zero2w/Cargo.toml'),
                    '--target', target, '--release'], check=True)
    library = ROOT / 'bsp/rpi-zero2w/target' / target / 'release/librustos_bsp_rpi_zero2w.rlib'
    sysroot = Path(subprocess.check_output(['rustc', '--print', 'sysroot'], text=True).strip())
    linker = sysroot / 'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    sources = [ROOT / 'tools/entry-harness' / name for name in
               ['handoff.S', 'el1-transition.S', 'rust-call.S', 'rust-link.ld']]
    boundary = '    mov x12, x0\n'
    original = sources[0].read_text()
    guard_boundary = '.ifdef TEST_HEADER\n'
    assert original.count(guard_boundary) == 1
    guards = (ROOT / 'tools/entry-harness/cpu-guards.S').read_text()
    original = original.replace(guard_boundary, guards+'\n'+guard_boundary)
    assert original.count(boundary) == 1
    source = original.replace(boundary, sources[1].read_text()+'\n'+sources[2].read_text()+'\n'+boundary)
    cases = []
    for name, size, dynamic, rejected, pool, panic in [
        ('no_pool', 0x8000000, False, False, (0, 0), False),
        ('cma_pool', 0x8000000, True, False, (0x4000000, 0x4000000), False),
        ('cma_no_space', 0x2000000, True, True, (0, 0), False),
        ('rust_panic', 0x8000000, False, False, (0, 0), True),
    ]:
        rust, archive, elf, dtb = [folder / (name+suffix) for suffix in ('.rs', '.a', '.elf', '.dtb')]
        constants = '\n'.join('.equ TEST_'+key+', 1' for key in ['HEADER','TREE','ROOT','RAM','STATIC','CMA'])
        constants += f'\n.equ TEST_POOL_BASE, {pool[0]}\n.equ TEST_POOL_SIZE, {pool[1]}'
        if rejected:
            constants += '\n.equ TEST_REJECT, 1'
        if panic:
            constants += '\n.equ TEST_PANIC, 1'
        rust.write_text('#![no_std]\nextern crate rustos_bsp_rpi_zero2w;\n'
                        '#[panic_handler]\nfn panic(_: &core::panic::PanicInfo) -> ! { unsafe { core::arch::asm!("mov x10, #0xface", "b harness_panic_park", options(noreturn)) } }\n'
                        '#[no_mangle]\npub extern "C" fn harness_force_panic() -> ! { panic!("entry panic experiment") }\n'
                        'core::arch::global_asm!(".section .text.panic_park,\\\"ax\\\"", ".global harness_panic_park", "harness_panic_park:", "wfe", "b harness_panic_park");\n'
                        'core::arch::global_asm!('+json.dumps('.arch armv8-a+simd\n'+constants+'\n'+source)+');\n')
        subprocess.run(['rustc',str(rust),'--crate-type','staticlib','--target',target,
                        '--extern',f'rustos_bsp_rpi_zero2w={library}','-C','panic=abort','-C','opt-level=2',
                        '-o',str(archive)],check=True)
        subprocess.run([str(linker),'-flavor','gnu','--gc-sections','-T',str(sources[3]),
                        str(archive),'-o',str(elf)],check=True)
        dtb.write_bytes(fixture([(0,size)],dynamic=dynamic))
        linked = symbols(elf.read_bytes())
        result = probe('C:/Program Files/qemu/qemu-system-aarch64.exe','raspi3b',
                       ['-device',f'loader,file={elf},cpu-num=0','-device',
                        f'loader,file={dtb},addr=0x1000000,force-raw=on'],run=True)
        registers = result['observed_registers']
        def reg(key):
            match = re.search(r'\b'+key+r'=([0-9a-fA-F]+)',registers)
            return int(match.group(1),16) if match else None
        checks = {'marker':reg('X10')==0x50415353,
                  'park':reg('PC') in (linked['success_park'],linked['success_park']+4),
                  'el1':'EL1h' in registers,'stack_restored':reg('SP')==0x400000,
                  'validator_linked':'rustos_validate_boot_memory' in linked,
                  'scalar_status':reg('X17')==int(rejected),
                  'result':(reg('X23'),reg('X24'))==((0xaaaa,0xaaaa) if rejected else pool)}
        if panic:
            checks = {'panic_marker': reg('X10') == 0xface,
                      'panic_park': reg('PC') in (linked['harness_panic_park'], linked['harness_panic_park']+4),
                      'el1': 'EL1h' in registers,
                      'stack_in_budget': reg('SP') is not None and 0x3f0000 <= reg('SP') <= 0x400000}
        writes = observe_writes(elf, dtb, linked, panic)
        checks['observed_writes_confined_to_stack'] = writes['passed']
        stack_audit = audit(elf)
        stack_report = folder / (name+'.stack.json')
        stack_report.write_text(json.dumps(stack_audit, indent=2)+'\n')
        checks['linked_stack_bound'] = stack_audit['passed']
        cases.append({'name':name,'passed':all(checks.values()),'checks':checks,
                      'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'qemu':result,
                      'write_observation': writes, 'stack_bound': stack_audit['stack_bound'],
                      'stack_report': str(stack_report)})
    report = {'passed':all(c['passed'] for c in cases),'cases':cases,
              'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              'scope':'Actual EL1 C ABI call, guarded result, x19-x29 preservation; no production entry or physical boot'}
    path=folder/'report.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'report':str(path), 'checks':{c['name']:c['checks'] for c in cases}}))
    if not report['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
