"""Bind entry/BSS observations to both exact internal-compiler ELFs."""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from test_entry_handoff import ROOT, symbols
from test_entry_memory_reference import fixture
from test_pi_kernel_entry import build_adapter, observe_bss
from probe_entry_machines import probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-report', type=Path, required=True)
    args = parser.parse_args()
    recorded = json.loads(args.compiler_report.read_text())
    folder = ROOT/'target'/f'pi-compiler-entry-{time.time_ns()}'
    folder.mkdir()
    adapter = build_adapter(folder)
    results = []
    for variant in recorded['variants']:
        kernel = Path(variant['elf'])
        digest = hashlib.sha256(kernel.read_bytes()).hexdigest()
        if digest != variant['sha256']:
            raise ValueError('Compiler output hash changed')
        linked = symbols(kernel.read_bytes())
        cases = []
        for name, data, accepted, pool in [
            ('no_pool',fixture([(0,0x8000000)]),True,(0,0)),
            ('cma_pool',fixture([(0,0x8000000)],dynamic=True),True,(0x4000000,0x4000000)),
            ('cma_no_space',fixture([(0,0x2000000)],dynamic=True),False,None),
            ('zero_ram',fixture([(0,0)]),False,None),
            ('reserved_stack',fixture([(0,0x8000000)],reserved=(0x3ffff0,1)),False,None),
        ]:
            dtb = folder/f'{variant["variant"]}-{name}.dtb'
            dtb.write_bytes(data)
            observed = observe_bss(kernel,adapter,dtb,linked,accepted,pool)
            cases.append({'name':name,**observed})
        dtb = folder/f'{variant["variant"]}-cma_pool.dtb'
        serial = folder/f'{variant["variant"]}-serial.log'
        extra = ['-device',f'loader,file={kernel}']
        for cpu in range(4):
            extra += ['-device',f'loader,file={adapter},cpu-num={cpu}']
        extra += ['-device',f'loader,file={dtb},addr=0x1000000,force-raw=on']
        qemu = probe('C:/Program Files/qemu/qemu-system-aarch64.exe','raspi3b',extra,run=True,cpus=range(4),serial='file:'+str(serial))
        checks = {}
        for cpu in range(4):
            text = qemu['cpu_registers'][str(cpu)]
            def reg(name):
                match = re.search(r'\b'+name+r'=([0-9a-fA-F]+)',text)
                return int(match[1],16) if match else None
            park = linked['secondary_park' if cpu else 'pi_console_failed']
            checks[f'cpu{cpu}_terminal'] = f'CPU#{cpu}' in text and reg('PC') in (park,park+4)
            if cpu:
                checks[f'cpu{cpu}_no_stack'] = reg('SP') == 0
            else:
                checks['el1'] = 'EL1h' in text
                checks['explicit_clock_rejection'] = reg('X10') == 0xc10c and reg('X14') == 4
        checks['no_success_serial'] = serial.read_bytes() == b''
        checks['artifact_unchanged'] = hashlib.sha256(kernel.read_bytes()).hexdigest() == digest
        results.append({'variant':variant['variant'],'sha256':digest,'cases':cases,'checks':checks,'qemu':qemu,
                        'passed':all(c['passed'] for c in cases) and all(checks.values())})
    report = {'passed':len(results)==2 and all(v['passed'] for v in results),'variants':results,
              'compiler_report':str(args.compiler_report),'compiler_report_sha256':hashlib.sha256(args.compiler_report.read_bytes()).hexdigest(),
              'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),
              'scope':'Exact unmodified compiler outputs with synthetic DTBs and separate EL3 reset adapter. BSS gates observed on CPU0; secondary cores parked. Current QEMU rejects measured clock; no UART success or physical boot claim.'}
    path = folder/'report.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'report':str(path)}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
