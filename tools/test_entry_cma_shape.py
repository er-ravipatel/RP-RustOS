"""D20 request shape only: pool placement is intentionally deferred."""
import hashlib
import json
import struct
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, run_case
from test_entry_memory_reference import fixture


def main():
    folder=ROOT/'target'/f'entry-cma-shape-{time.time_ns()}'; folder.mkdir(parents=True)
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/Cargo.toml'),
                    '--example','inspect_memory','--locked','--offline'],check=True,capture_output=True,timeout=60)
    checker=ROOT/'bsp/rpi-zero2w/target/debug/examples/inspect_memory.exe'
    sysroot=Path(subprocess.check_output(['rustc','--print','sysroot'],text=True).strip())
    linker=sysroot/'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    source=ROOT/'tools/entry-harness/handoff.S'
    ram=[(0,0x8000000)]
    variants=[
        ('cma_valid',{},'success','OK'),
        ('cma_phandle',{'phandle':struct.pack('>I',61)},'success','OK'),
        ('cma_wrong_compatible',{'compatible':b'other\0'},'failure','ERR DynamicReservation'),
        ('cma_missing_compatible',{'compatible':None},'failure','ERR DynamicReservation'),
        ('cma_missing_reusable',{'reusable':None},'failure','ERR DynamicReservation'),
        ('cma_bad_reusable',{'reusable':b'\0'},'failure','ERR Node'),
        ('cma_missing_default',{'linux,cma-default':None},'failure','ERR DynamicReservation'),
        ('cma_bad_default',{'linux,cma-default':b'\0'},'failure','ERR DynamicReservation'),
        ('cma_zero_size',{'size':struct.pack('>I',0)},'failure','ERR DynamicReservation'),
        ('cma_large_size',{'size':struct.pack('>I',0x20000001)},'failure','ERR DynamicReservation'),
        ('cma_bad_size_width',{'size':b'\0'*8},'failure','ERR DynamicReservation'),
        ('cma_alignment',{'alignment':struct.pack('>I',4096)},'failure','ERR DynamicReservation'),
        ('cma_alloc_ranges',{'alloc-ranges':b'\0'*8},'failure','ERR DynamicReservation'),
        ('cma_no_map',{'no-map':b''},'failure','ERR DynamicReservation'),
        ('cma_reg',{'reg':b'\0'*8},'failure','ERR DynamicReservation'),
        ('cma_bad_phandle',{'phandle':b'\0'*4},'failure','ERR DynamicReservation'),
        ('cma_unknown',{'vendor,unknown':b''},'failure','ERR DynamicReservation'),
    ]
    cases=[(name,fixture(ram,dynamic=True,dynamic_props=props),1,expected,host) for name,props,expected,host in variants]
    cases += [('cma_two_cells',fixture(ram,cells=2,dynamic=True),2,'success','OK'),
              ('cma_wrong_node',fixture(ram,dynamic=True,dynamic_name='other'),1,'failure','ERR DynamicReservation')]
    results=[]
    for name,data,cells,expected,host_expected in cases:
        result=run_case(folder,source,linker,name,0x3c9,0x30c50830,8,fixture=data,expected=expected,
                        tree=True,root=True,root_cells=(cells,cells),ram=True,static=True,cma=True)
        host=subprocess.run([str(checker),str(folder/f'{name}.dtb'),'1000000'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
        match=host.startswith('OK ') if host_expected=='OK' else host==host_expected
        result['reference']={'expected':host_expected,'actual':host,'passed':match,'fixture_sha256':hashlib.sha256(data).hexdigest()}
        result['passed'] &= match
        results.append(result)
    report={'passed':all(c['passed'] for c in results),'cases':results,
            'scope':'Request shape only; no pool allocation, first stack write or production startup',
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    path=folder/'report.json'; path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'case_count':len(results),
                      'failed_cases':{c['name']:{'checks':c['checks'],'reference':c['reference']} for c in results if not c['passed']},'report':str(path)}))
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__': main()
