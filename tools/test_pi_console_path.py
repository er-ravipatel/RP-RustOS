"""Exercise the default post-BSS console path, reporting unsupported clocks."""
import hashlib
import json
import re
import subprocess
import time
from test_entry_handoff import ROOT, symbols
from test_pi_kernel_entry import build_adapter
from test_entry_memory_reference import fixture
from probe_entry_machines import probe


def main():
    folder=ROOT/'target'/f'pi-console-path-{time.time_ns()}';folder.mkdir(parents=True)
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/kernel/Cargo.toml'),
                    '--target','aarch64-unknown-none-softfloat','--release'],check=True)
    built=ROOT/'bsp/rpi-zero2w/kernel/target/aarch64-unknown-none-softfloat/release/rustos-pi-kernel'
    kernel=folder/'kernel.elf';kernel.write_bytes(built.read_bytes())
    linked=symbols(kernel.read_bytes());adapter=build_adapter(folder)
    dtb=folder/'valid.dtb';dtb.write_bytes(fixture([(0,0x8000000)],dynamic=True))
    log=folder/'serial.log'
    extra=['-device',f'loader,file={kernel}']
    for cpu in range(4):extra+=['-device',f'loader,file={adapter},cpu-num={cpu}']
    extra+=['-device',f'loader,file={dtb},addr=0x1000000,force-raw=on']
    observed=probe('C:/Program Files/qemu/qemu-system-aarch64.exe','raspi3b',extra,
                   run=True,cpus=range(4),serial='file:'+str(log),
                   memory_words=(linked['PI_CLOCK_BUFFERS'],48))
    registers=observed['cpu_registers']['0']
    def reg(key):
        m=re.search(r'\b'+key+r'=([0-9a-fA-F]+)',registers)
        return int(m.group(1),16) if m else None
    captured=log.read_bytes()
    words=[int(w,16) for w in re.findall(r'0x[0-9a-fA-F]{8}(?![0-9a-fA-F])',observed['physical_words'])]
    if len(words)!=48:raise RuntimeError('Incomplete clock buffer observation')
    ready=reg('PC') in (linked['pi_marker_committed'],linked['pi_marker_committed']+4)
    rejected=reg('PC') in (linked['pi_console_failed'],linked['pi_console_failed']+4)
    checks={'el1':'EL1h' in registers,'bounded_terminal':ready or rejected,
            'outcome_marker':reg('X10')==(0xc023 if ready else 0xc10c),
            'serial_matches_outcome':captured==b'RUSTOS_PI_CONSOLE_READY\nRUSTOS_BOOT_OK\n' if ready else captured==b'',
            'supported_or_explicit_clock_failure':ready or (rejected and reg('X14')==4)}
    for cpu in [1,2,3]:
        text=observed['cpu_registers'][str(cpu)]
        m=re.search(r'\bPC=([0-9a-fA-F]+)',text)
        checks[f'cpu{cpu}_parked']=f'CPU#{cpu}' in text and m is not None and int(m[1],16) in (linked['secondary_park'],linked['secondary_park']+4)
    report={'passed':all(checks.values()),'checks':checks,'kernel_features':[],
            'outcome':'console_ready' if ready else 'clock_rejected' if rejected else 'unexpected',
            'failure_stage':None if ready else reg('X14'),'serial_hex':captured.hex(),
            'clock_buffers':{'enable':words[:16],'set_rate':words[16:32],'measured_rate':words[32:]},
            'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'qemu':observed,
            'scope':'Actual default kernel post-BSS path; rejected clock means failure-path evidence, never successful UART/hardware acceptance'}
    path=folder/'report.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','outcome','failure_stage','checks']}|{'report':str(path)}))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
