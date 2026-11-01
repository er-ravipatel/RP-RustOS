"""Differential fixtures for the narrow stackless static-reservation pass."""
import hashlib
import json
import struct
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, run_case
from test_entry_memory_reference import fixture


def header_records(data, records):
    data = bytearray(data)
    extra = b''.join(struct.pack('>QQ',start,size) for start,size in records)
    data[40:40] = extra
    for offset in [4,8,12]:
        struct.pack_into('>I',data,offset,struct.unpack_from('>I',data,offset)[0]+len(extra))
    return data


def main():
    folder = ROOT/'target'/f'entry-static-{time.time_ns()}'
    folder.mkdir(parents=True)
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/Cargo.toml'),
                    '--example','inspect_memory','--locked','--offline'],check=True,capture_output=True,timeout=60)
    checker = ROOT/'bsp/rpi-zero2w/target/debug/examples/inspect_memory.exe'
    sysroot = Path(subprocess.check_output(['rustc','--print','sysroot'],text=True).strip())
    linker = sysroot/'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    source = ROOT/'tools/entry-harness/handoff.S'
    ram = [(0,0x8000000)]
    low = fixture(ram,reserved=(0x1000,0x1000))
    cases = [
        ('static_none',fixture(ram),1,'success','OK'),
        ('static_low',low,1,'success','OK'),
        ('static_two_cells',fixture(ram,cells=2,reserved=(0x1000,0x1000)),2,'success','OK'),
        ('static_dtb',fixture(ram,reserved=(0x1000000,0x1000)),1,'success','OK'),
        ('static_kernel',fixture(ram,reserved=(0x200000,1)),1,'failure','ERR Ranges(KernelReserved)'),
        ('static_touch',fixture(ram,reserved=(0x1fffff,1)),1,'success','OK'),
        ('static_zero',fixture(ram,reserved=(0x1000,0)),1,'failure','ERR Ranges(Empty)'),
        ('static_wrap',fixture(ram,cells=2,reserved=(0xfffffffffffffff0,0x20)),2,'failure','ERR Ranges(Overflow)'),
        ('static_outside',fixture(ram,reserved=(0x20000000,1)),1,'failure','ERR Ranges(AddressBounds)'),
        ('static_bad_cells',fixture(ram,reserved=(0x1000,0x1000),reserved_cells=2),1,'failure','ERR ReservedMapping'),
        ('static_translated',fixture(ram,reserved=(0x1000,0x1000),reserved_ranges=b'\0'*12),1,'failure','ERR ReservedMapping'),
        ('static_no_ranges',fixture(ram,reserved=(0x1000,0x1000),reserved_ranges=None),1,'failure','ERR ReservedMapping'),
        ('static_parent_status',fixture(ram,reserved=(0x1000,0x1000),reserved_status=b'okay\0'),1,'failure','ERR ReservedMapping'),
        ('static_header_overlap',header_records(low,[(0x1000,1)]),1,'failure','ERR Ranges(OverlappingReservations)'),
        ('static_header_touch',header_records(low,[(0,0x1000)]),1,'success','OK'),
        ('static_combined_limit',header_records(low,[(i,1) for i in range(127)]),1,'success','OK'),
        ('static_combined_excess',header_records(low,[(i,1) for i in range(128)]),1,'failure','ERR Ranges(Count)'),
        ('static_dynamic_blocked',fixture(ram,dynamic=True),1,'failure','OK'),
    ]
    results = []
    for name,data,cells,expected,host_expected in cases:
        result = run_case(folder,source,linker,name,0x3c9,0x30c50830,8,fixture=data,
                          expected=expected,tree=True,root=True,root_cells=(cells,cells),ram=True,static=True)
        host = subprocess.run([str(checker),str(folder/f'{name}.dtb'),'1000000'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
        matched = host.startswith('OK ') if host_expected=='OK' else host==host_expected
        result['reference']={'actual':host,'expected':host_expected,'passed':matched,
                             'conservative_subset':name=='static_dynamic_blocked',
                             'fixture_sha256':hashlib.sha256(data).hexdigest()}
        result['passed'] &= matched
        results.append(result)
    report={'passed':all(case['passed'] for case in results),'cases':results,
            'scope':'One active static child/tuple; dynamic requests still rejected; no stack authorization',
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'reference_executable_sha256':hashlib.sha256(checker.read_bytes()).hexdigest()}
    path=folder/'report.json'; path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'case_count':len(results),
                      'failed_cases':{c['name']:c['checks'] for c in results if not c['passed']},'report':str(path)}))
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__': main()
