"""Run the actual isolated Pi entry ELF behind a separate QEMU reset adapter."""
import hashlib
import json
import re
import socket
import struct
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, symbols
from test_entry_memory_reference import fixture
from probe_entry_machines import probe
from check_entry_stack import audit
from test_entry_first_write import Remote


def observe_bss(kernel, adapter, dtb, linked, accepted, pool):
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0)); port=reservation.getsockname()[1]
    command=['C:/Program Files/qemu/qemu-system-aarch64.exe','-machine','raspi3b','-S',
             '-display','none','-serial','none','-monitor','none','-gdb',f'tcp:127.0.0.1:{port}',
             '-device',f'loader,file={kernel}','-device',f'loader,file={adapter},cpu-num=0',
             '-device',f'loader,file={dtb},addr=0x1000000,force-raw=on']
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    connection=None
    try:
        deadline=time.monotonic()+5
        while connection is None:
            try:connection=socket.create_connection(('127.0.0.1',port),timeout=0.2)
            except OSError:
                if time.monotonic()>deadline or process.poll() is not None:raise
                time.sleep(0.05)
        remote=Remote(connection)
        for request in ['Hg1','Hc1']:
            if remote.request(request)!='OK':raise RuntimeError('Cannot select CPU0')
        begin,end=linked['__bss_start'],linked['__bss_end'];size=end-begin
        sentinel=b'\xa5'*size
        if remote.request(f'M{begin:x},{size:x}:'+sentinel.hex())!='OK':raise RuntimeError('Cannot seed BSS')
        park=linked['bss_clear_begin' if accepted else 'failure_park']
        watches=['Z2,0,3f0000','Z2,400000,1fc00000']
        for request in watches+[f'Z1,{park:x},4']:
            if remote.request(request)!='OK':raise RuntimeError('Required observation rejected')
        remote.send('c');stop=remote.receive();regs=remote.registers()
        before=bytes.fromhex(remote.request(f'm{begin:x},{size:x}'))
        checks={'no_pre_validation_outside_stack_write':'watch:' not in stop,
                'expected_stop':regs['pc']==park,'bss_untouched_before_gate':before==sentinel}
        if accepted:
            for request in [*['z'+w[1:] for w in watches],f'z1,{park:x},4',f'Z1,{linked["pi_entry_ready"]:x},4']:
                if remote.request(request)!='OK':raise RuntimeError('Cannot advance BSS observation')
            remote.send('c');remote.receive();regs=remote.registers()
            after=bytes.fromhex(remote.request(f'm{begin:x},{size:x}'))
            wanted=bytearray(size);offset=linked['pi_boot_record']-begin
            wanted[offset:offset+32]=struct.pack('<QQQQ',0x1000000,dtb.stat().st_size,*pool)
            checks.update(ready_after_bss=regs['pc']==linked['pi_entry_ready'],
                          zeroed_bss_and_boot_record=after==wanted)
        return {'passed':all(checks.values()),'checks':checks,'stop':stop,
                'scope':'CPU0 0..512 MiB outside-stack watch until BSS gate or rejection; BSS sentinel then expected clear/boot record'}
    finally:
        if connection is not None:connection.close()
        if process.poll() is None:process.kill()
        process.communicate(timeout=10)


def build_adapter(folder):
    rust,obj,adapter = [folder/('adapter'+suffix) for suffix in ['.rs','.o','.elf']]
    rust.write_text('#![no_std]\ncore::arch::global_asm!(include_str!(r"'+str(ROOT/'tools/entry-harness/pi-reset-adapter.S')+'"));\n')
    script = folder/'adapter.ld'
    script.write_text('ENTRY(reset_adapter)\nSECTIONS { . = 0x100000; .text : { *(.text*) } }\n')
    sysroot=Path(subprocess.check_output(['rustc','--print','sysroot'],text=True).strip())
    linker=sysroot/'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    subprocess.run(['rustc',str(rust),'--crate-type','lib','--target','aarch64-unknown-none-softfloat','--emit=obj','-o',str(obj)],check=True)
    subprocess.run([str(linker),'-flavor','gnu','-T',str(script),str(obj),'-o',str(adapter)],check=True)
    return adapter


def main():
    folder = ROOT/'target'/f'pi-kernel-entry-{time.time_ns()}'
    folder.mkdir(parents=True)
    subprocess.run(['python',str(ROOT/'tools/sync_pi_entry_sources.py'),'--check'],check=True)
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/kernel/Cargo.toml'),
                    '--target','aarch64-unknown-none-softfloat','--release','--features','entry-only'],check=True)
    kernel = ROOT/'bsp/rpi-zero2w/kernel/target/aarch64-unknown-none-softfloat/release/rustos-pi-kernel'
    linked = symbols(kernel.read_bytes())
    clock_address = linked['PI_CLOCK_BUFFERS']
    if clock_address % 64 or not linked['__bss_start'] <= clock_address or clock_address+192 > linked['__bss_end']:
        raise ValueError('Permanent clock buffers must be aligned and fully retained in BSS')
    stack = audit(kernel)
    (folder/'stack.json').write_text(json.dumps(stack,indent=2)+'\n')
    adapter=build_adapter(folder)
    cases=[]
    for name,data,accepted,pool in [
        ('no_pool',fixture([(0,0x8000000)]),True,(0,0)),
        ('cma_pool',fixture([(0,0x8000000)],dynamic=True),True,(0x4000000,0x4000000)),
        ('cma_no_space',fixture([(0,0x2000000)],dynamic=True),False,None),
        ('zero_ram',fixture([(0,0)]),False,None),
        ('reserved_stack',fixture([(0,0x8000000)],reserved=(0x3ffff0,1)),False,None),
    ]:
        dtb=folder/(name+'.dtb');dtb.write_bytes(data)
        extra=['-device',f'loader,file={kernel}']
        for cpu in range(4):
            extra+=['-device',f'loader,file={adapter},cpu-num={cpu}']
        extra+=['-device',f'loader,file={dtb},addr=0x1000000,force-raw=on']
        observed=probe('C:/Program Files/qemu/qemu-system-aarch64.exe','raspi3b',extra,run=True,cpus=range(4))
        checks={}
        for cpu in range(4):
            registers=observed['cpu_registers'][str(cpu)]
            def reg(key):
                m=re.search(r'\b'+key+r'=([0-9a-fA-F]+)',registers)
                return int(m.group(1),16) if m else None
            park=linked['secondary_park' if cpu else 'pi_entry_ready' if accepted else 'failure_park']
            checks[f'cpu{cpu}'] = f'CPU#{cpu}' in registers and reg('PC') in (park,park+4)
            checks[f'cpu{cpu}_stack'] = reg('SP') == (0 if cpu or name in ('zero_ram','reserved_stack') else 0x400000 if accepted else 0x3fffd0)
            if cpu==0:
                checks['marker']=reg('X10') == (0x50415353 if accepted else 0xffff)
                if accepted:
                    checks['handoff']=(reg('X00'),reg('X01'),reg('X02'),reg('X03'))==(0x1000000,len(data),*pool)
        bss=observe_bss(kernel,adapter,dtb,linked,accepted,pool)
        checks['bss_order']=bss['passed']
        cases.append({'name':name,'passed':all(checks.values()),'checks':checks,'qemu':observed,'bss_observation':bss})
    report={'passed':stack['passed'] and all(c['passed'] for c in cases),'cases':cases,
            'clock_buffers': {'address':clock_address,'bytes':192,'alignment':64,'retained_in_bss':True},
            'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),
            'stack_bound':stack['stack_bound'], 'scope':'Actual Pi entry scaffold with separate EL3 test adapter; no PL011, packaged image or physical boot'}
    report['kernel_features'] = ['entry-only']
    path=folder/'report.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'report':str(path),'stack_bound':report['stack_bound'],
                      'checks':{c['name']:c['checks'] for c in cases}}))
    if not report['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
