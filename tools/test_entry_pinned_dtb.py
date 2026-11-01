"""Pinned DTB integration using separate simulated firmware-update fixtures."""
import hashlib
import json
import struct
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, run_case

PINNED_SHA = '5b31bc70011e454f482ba323b1eca22bf54fa2fa4682576ee73816a2eccfa277'


def memory_reg_offset(data):
    """Walk only the hash-verified research asset to identify its placeholder."""
    cursor, strings = struct.unpack_from('>II', data, 8)
    end = cursor + struct.unpack_from('>I', data, 36)[0]
    path, matches = [], []
    while cursor < end:
        token = struct.unpack_from('>I', data, cursor)[0]
        cursor += 4
        if token == 1:
            nul = data.index(0, cursor, end)
            path.append(data[cursor:nul].decode())
            cursor = (nul+4) & ~3
        elif token == 2:
            path.pop()
        elif token == 3:
            length, offset = struct.unpack_from('>II', data, cursor)
            cursor += 8
            name = data[strings+offset:data.index(0, strings+offset)].decode()
            if path == ['', 'memory@0'] and name == 'reg':
                if length != 8 or data[cursor:cursor+8] != b'\0'*8:
                    raise ValueError('Unexpected memory placeholder')
                matches.append(cursor)
            cursor = (cursor+length+3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            break
        else:
            raise ValueError('Unexpected token in pinned source asset')
    if len(matches) != 1:
        raise ValueError('Expected exactly one pinned memory placeholder')
    return matches[0]


def main():
    asset = ROOT/'out/research/m2-source-9b488bc7a1e9/boot-assets/bcm2710-rpi-zero-2-w.dtb'
    original = asset.read_bytes()
    if hashlib.sha256(original).hexdigest() != PINNED_SHA:
        raise ValueError('Pinned asset identity mismatch')
    offset = memory_reg_offset(original)
    folder = ROOT/'target'/f'entry-pinned-dtb-{time.time_ns()}'
    folder.mkdir(parents=True)
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/Cargo.toml'),
                    '--example','inspect_memory','--locked','--offline'],capture_output=True,check=True,timeout=60)
    checker = ROOT/'bsp/rpi-zero2w/target/debug/examples/inspect_memory.exe'
    sysroot = Path(subprocess.check_output(['rustc','--print','sysroot'],text=True).strip())
    linker = sysroot/'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    source = ROOT/'tools/entry-harness/handoff.S'
    cases = [
        ('pinned_original',0,'failure','ERR Ranges(Empty)'),
        ('simulated_128m',0x8000000,'success','OK BootMemoryInfo { cma_pool: Some(MemoryRange { start: 67108864, size: 67108864 }) }'),
        ('simulated_partial_kernel',0x300000,'failure','ERR Pool(Map(KernelNotInRam))'),
        ('simulated_cma_no_space',0x2000000,'success','ERR Pool(NoSpace)'),
    ]
    results = []
    for name,size,expected,host_expected in cases:
        model = bytearray(original)
        struct.pack_into('>II',model,offset,0,size)
        if model[:offset] != original[:offset] or model[offset+8:] != original[offset+8:]:
            raise ValueError('Unexpected mutation outside the RAM placeholder')
        result = run_case(folder,source,linker,name,0x3c9,0x30c50830,8,fixture=model,
                          expected=expected,tree=True,root=True,ram=True,static=True,cma=True)
        host = subprocess.run([str(checker),str(folder/f'{name}.dtb'),'1000000'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
        result['reference'] = {'actual':host,'expected':host_expected,'passed':host==host_expected,
                               'deferred_pool_selection':name=='simulated_cma_no_space'}
        result['fixture'] = {'sha256':hashlib.sha256(model).hexdigest(),'ram_size':size,
                             'firmware_update_simulated':size!=0,'changed_property':'/memory@0/reg','value_offset':offset}
        result['passed'] &= host==host_expected
        results.append(result)
    unchanged = asset.read_bytes() == original
    report = {'passed':unchanged and all(c['passed'] for c in results),'asset_unchanged':unchanged,
              'original_sha256':PINNED_SHA,'asset':str(asset),'cases':results,
              'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'scope':'Simulated memory handoff only; firmware was not executed; no production startup or stack write'}
    path = folder/'report.json'; path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'case_count':len(results),
                      'failed_cases':{c['name']:{'checks':c['checks'],'reference':c['reference']} for c in results if not c['passed']},'report':str(path)}))
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__': main()
