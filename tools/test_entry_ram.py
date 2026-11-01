"""Compare the narrow test-only stackless RAM pass with the host reference."""
import hashlib
import json
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, run_case
from test_entry_memory_reference import fixture


def main():
    folder = ROOT/'target'/f'entry-ram-{time.time_ns()}'
    folder.mkdir(parents=True)
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/Cargo.toml'),
                    '--example','inspect_memory','--locked','--offline'], check=True, capture_output=True, timeout=60)
    checker = ROOT/'bsp/rpi-zero2w/target/debug/examples/inspect_memory.exe'
    sysroot = Path(subprocess.check_output(['rustc','--print','sysroot'],text=True).strip())
    linker = sysroot/'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    source = ROOT/'tools/entry-harness/handoff.S'
    ram = [(0,0x8000000)]
    cases = [
        ('ram_one_cell',fixture(ram),1,'success','OK'),
        ('ram_two_cells',fixture(ram,cells=2),2,'success','OK'),
        ('ram_ok',fixture(ram,status=b'ok\0'),1,'success','OK'),
        ('ram_okay',fixture(ram,status=b'okay\0'),1,'success','OK'),
        ('ram_zero',fixture([(0,0)]),1,'failure','ERR Ranges(Empty)'),
        ('ram_partial_kernel',fixture([(0,0x300000)]),1,'failure','ERR Ranges(KernelNotInRam)'),
        ('ram_partial_dtb',fixture([(0,0x1000001)]),1,'failure','ERR Ranges(DtbNotInRam)'),
        ('ram_disabled',fixture(ram,status=b'disabled\0'),1,'failure','ERR Ranges(Count)'),
        ('ram_unknown_status',fixture(ram,status=b'unknown\0'),1,'failure','ERR Status'),
        ('ram_overlapping_banks',fixture(ram+[(0,0x1000)]),1,'failure','ERR Ranges(OverlappingRam)'),
        ('ram_split_kernel',fixture([(0,0x300000),(0x300000,0x5000000)]),1,'failure','ERR Ranges(KernelNotInRam)'),
        ('ram_outside',fixture([(0,0x20000001)]),1,'failure','ERR Ranges(AddressBounds)'),
        ('ram_overflow',fixture([(0xfffffffffffffff0,0x20)],cells=2),2,'failure','ERR Ranges(Overflow)'),
        ('ram_bank_after_kernel',fixture([(0x300000,0x5000000)]),1,'failure','ERR Ranges(KernelNotInRam)'),
        ('ram_multiple_conservative',fixture([(0,0x2000000),(0x4000000,0x1000000)]),1,'failure','OK'),
        ('ram_missing_type',fixture(ram,device_type=None),1,'failure','ERR Node'),
        ('ram_bad_type',fixture(ram,device_type=b'ram\0'),1,'failure','ERR Node'),
        ('ram_unterminated_type',fixture(ram,device_type=b'memory'),1,'failure','ERR Node'),
        ('ram_unterminated_status',fixture(ram,status=b'okay'),1,'failure','ERR Status'),
        ('ram_missing_reg',fixture(ram,reg_override=None),1,'failure','ERR Node'),
        ('ram_truncated_reg',fixture(ram,reg_override=b'\0'*7),1,'failure','ERR Ranges(RegLength)'),
        ('ram_static_tree_guard',fixture(ram,reserved=(0x1000,0x1000)),1,'failure','OK'),
        ('ram_static_kernel_guard',fixture(ram,reserved=(0x200000,1)),1,'failure','ERR Ranges(KernelReserved)'),
        ('ram_dynamic_tree_guard',fixture(ram,dynamic=True),1,'failure','OK'),
        ('ram_misnamed_memory',fixture(ram,extra_memory_name='ram@0'),1,'failure','ERR Node'),
        ('ram_other_device_type',fixture(ram,extra_memory_name='other',extra_memory_type=b'cpu\0'),1,'success','OK'),
    ]
    results = []
    for name,data,cells,expected,host_expected in cases:
        result = run_case(folder,source,linker,name,0x3c9,0x30c50830,8,
                          fixture=data,expected=expected,tree=True,root=True,root_cells=(cells,cells),ram=True)
        path = folder/f'{name}.dtb'
        host = subprocess.run([str(checker),str(path),'1000000'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
        reference_ok = host.startswith('OK ') if host_expected == 'OK' else host == host_expected
        result['reference'] = {'expected':host_expected,'actual':host,'passed':reference_ok,
                               'conservative_subset':name in {'ram_multiple_conservative','ram_static_tree_guard','ram_dynamic_tree_guard'},
                               'fixture_sha256':hashlib.sha256(data).hexdigest()}
        result['passed'] &= reference_ok
        results.append(result)
    report = {'passed':all(case['passed'] for case in results),'cases':results,
              'scope':'One active RAM node/tuple; all reserved-memory trees rejected pending implementation; no stack authorized',
              'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'reference_executable_sha256':hashlib.sha256(checker.read_bytes()).hexdigest()}
    path = folder/'report.json'; path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'case_count':len(results),
                      'failed_cases':{c['name']:c['checks'] for c in results if not c['passed']},'report':str(path)}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
