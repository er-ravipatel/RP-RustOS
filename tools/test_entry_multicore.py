"""Run all four actual QEMU cores through the EL3 adapter and EL2 gate."""
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
    folder = ROOT / 'target' / f'entry-multicore-{time.time_ns()}'
    folder.mkdir(parents=True)
    paths = [ROOT / 'tools/entry-harness' / n for n in
             ['handoff.S', 'cpu-guards.S', 'el1-transition.S']]
    source = paths[0].read_text()
    early = '    mrs x9, mpidr_el1\n    and x9, x9, #0xff\n    cbnz x9, secondary_park\n'
    assert source.count(early) == 1
    # Let every core traverse the adapter: exercise the EL2 gate itself.
    source = source.replace(early, '')
    gate = '.ifdef TEST_HEADER\n'
    assert source.count(gate) == 1
    source = source.replace(gate, paths[1].read_text()+'\n'+gate)
    boundary = '    mov x12, x0\n'
    assert source.count(boundary) == 1
    source = source.replace(boundary, paths[2].read_text()+'\n'+boundary)
    constants = '\n'.join('.equ TEST_'+key+', 1' for key in ['HEADER','TREE','ROOT','RAM','STATIC','CMA'])
    rust, obj, elf, dtb = [folder / ('multicore'+suffix) for suffix in ['.rs','.o','.elf','.dtb']]
    rust.write_text('#![no_std]\ncore::arch::global_asm!('+json.dumps('.arch armv8-a+simd\n'+constants+'\n'+source)+');\n')
    sysroot = Path(subprocess.check_output(['rustc','--print','sysroot'], text=True).strip())
    linker = sysroot / 'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    subprocess.run(['rustc',str(rust),'--crate-type','lib','--target','aarch64-unknown-none-softfloat','--emit=obj','-o',str(obj)],check=True)
    subprocess.run([str(linker),'-flavor','gnu','-T',str(ROOT/'tools/entry-harness/link.ld'),str(obj),'-o',str(elf)],check=True)
    dtb.write_bytes(fixture([(0,0x8000000)]))
    linked = symbols(elf.read_bytes())
    extra = []
    for cpu in range(4):
        extra += ['-device',f'loader,file={elf},cpu-num={cpu}']
    extra += ['-device',f'loader,file={dtb},addr=0x1000000,force-raw=on']
    result = probe('C:/Program Files/qemu/qemu-system-aarch64.exe','raspi3b',extra,run=True,cpus=range(4))
    checks = {}
    for cpu in range(4):
        registers = result['cpu_registers'][str(cpu)]
        def reg(key):
            m = re.search(r'\b'+key+r'=([0-9a-fA-F]+)',registers)
            return int(m.group(1),16) if m else None
        park = linked['success_park' if cpu == 0 else 'secondary_park']
        checks[str(cpu)] = {'cpu_identity': f'CPU#{cpu}' in registers,
                            'park':reg('PC') in (park,park+4),
                            'level':('EL1h' if cpu == 0 else 'EL2h') in registers,
                            'stack':reg('SP') == (0x400000 if cpu == 0 else 0),
                            'marker':reg('X10') == (0x50415353 if cpu == 0 else 0),
                            'dtb_access_gate':reg('X19') == (0x1000000 if cpu == 0 else 0)}
    report = {'passed':all(all(c.values()) for c in checks.values()),'checks':checks,'qemu':result,
              'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              'scope':'Four QEMU raspi3b cores really execute EL3 adapter; primary reaches EL1, others park at EL2 before DTB/stack; no physical firmware proof'}
    path = folder/'report.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'checks':checks,'report':str(path)}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
