"""Synthetic debugger inputs exercise UART success/failure; not firmware proof."""
import hashlib
import json
import socket
import struct
import subprocess
import time
from test_entry_handoff import ROOT, symbols
from test_entry_first_write import Remote
from test_pi_kernel_entry import build_adapter
from test_entry_memory_reference import fixture
from check_entry_stack import audit


def run(kernel, adapter, dtb, linked, mode, folder, panic=False):
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    name='deliberate_panic' if panic and mode=='ready' else mode
    log=folder/(name+'.serial')
    command=['C:/Program Files/qemu/qemu-system-aarch64.exe','-machine','raspi3b','-S',
             '-display','none','-serial','file:'+str(log),'-monitor','none','-gdb',f'tcp:127.0.0.1:{port}',
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
        def ok(request):
            if remote.request(request)!='OK':raise RuntimeError('Debugger command rejected: '+request)
        def memory(address,size):return bytes.fromhex(remote.request(f'm{address:x},{size:x}'))
        def write(address,data):ok(f'M{address:x},{len(data):x}:'+data.hex())
        def continue_to(address):
            remote.send('c');stop=remote.receive();regs=remote.registers()
            if regs['pc']!=address:raise RuntimeError(f'Unexpected debugger stop: {stop} {regs}')
            return regs
        ok('Hg1');ok('Hc1')
        response=next(value for name,value in linked.items() if 'ClockOperation8response' in name)
        ok(f'Z1,{response:x},4')
        original=None
        for operation in range(3):
            regs=continue_to(response)
            snapshot=regs['x1']
            if regs['x0']!=operation or not 0x3f0000<=snapshot<=0x400000-64:
                raise RuntimeError('Response ABI differs from inspected binary')
            words=list(struct.unpack('<16I',memory(snapshot,64)))
            expected=[0x38001,0x38002,0x30047][operation]
            if words[2]!=expected or words[5]!=2:raise RuntimeError('Unexpected response snapshot')
            ok(f'z1,{response:x},4')
            if operation==2:
                original=words.copy()
                # Deliberately patch only the completed response's local snapshot.
                # The real firmware-owned allocation and production code stay unchanged.
                words[4]=0x80000008;words[6]=48_000_000
                write(snapshot,struct.pack('<16I',*words))
            else:
                remote.send('s');remote.receive();ok(f'Z1,{response:x},4')
        prefix=b'RUSTOS_EXPECTED_PANIC' if panic else b'RUSTOS_BOOT_OK'
        diagnostics=b'RUSTOS_PI_CONSOLE_READY\n'+(b'RUSTOS_PI_DELIBERATE_PANIC\n' if panic else b'')
        fault=mode!='ready'
        park=linked['pi_console_failed' if fault else 'pi_marker_committed']
        ok(f'Z1,{park:x},4')
        expected=diagnostics+prefix+b'\n'
        stage=None
        if fault:
            if 'marker_' in mode:
                is_tx=not mode.endswith('drain_timeout')
                ordinal=(3 if panic else 2)+(1 if mode.endswith('lf_timeout') else 0)
                stage=12 if mode.endswith('lf_timeout') else 10 if is_tx else 11
                expected=diagnostics+(b'' if stage==10 else prefix)
            else:
                is_tx=mode.endswith('tx_timeout')
                ordinal=2 if panic else 1
                stage=(8 if is_tx else 9) if panic else (6 if is_tx else 7)
                expected=(b'RUSTOS_PI_CONSOLE_READY\n' if panic else b'') if is_tx else diagnostics
            needle='Write$GT$9write_str' if is_tx else 'Console$GT$5flush'
            gate=next(value for symbol,value in linked.items() if needle in symbol)
            ok(f'Z1,{gate:x},4');regs=continue_to(gate)
            for _ in range(ordinal-1):
                return_pc=regs['x30']
                if not 0x200000<=return_pc<0x3f0000:raise RuntimeError('Invalid driver return address')
                ok(f'z1,{gate:x},4');ok(f'Z1,{return_pc:x},4');continue_to(return_pc)
                ok(f'z1,{return_pc:x},4');ok(f'Z1,{gate:x},4');regs=continue_to(gate)
            uart=regs['x0']
            if not 0x3f0000<=uart<=0x400000-8 or struct.unpack('<Q',memory(uart,8))[0]!=0x3f201000:
                raise RuntimeError('PL011 ABI differs from inspected binary')
            write(0x1200018,struct.pack('<I',32 if is_tx else 8))
            write(uart,struct.pack('<Q',0x1200000));ok(f'z1,{gate:x},4')
        regs=continue_to(park)
        serial=log.read_bytes()
        checks={'exact_terminal':regs['pc']==park,
                'marker':regs['x10']==(0xc10c if fault else 0xc023),
                'serial':serial==expected,'stack_in_budget':0x3f0000<=regs['sp']<=0x400000,
                'complete_token_only_on_commit':(prefix+b'\n' in serial)==(not fault),
                'no_opposite_variant_token':(b'RUSTOS_BOOT_OK' if panic else b'RUSTOS_EXPECTED_PANIC') not in serial}
        if fault:checks['failure_stage']=regs['x14']==stage
        return {'mode':name,'passed':all(checks.values()),'checks':checks,'serial_hex':serial.hex(),
                'variant':'panic-test' if panic else 'normal', 'committed':not fault,
                'original_measured_snapshot':original,'synthetic_measured_hz':48_000_000,
                'fault':'none' if mode=='ready' else 'PL011 base redirected to synthetic RAM register page',
                'terminal_registers':regs}
    finally:
        if connection is not None:connection.close()
        if process.poll() is None:process.kill()
        process.communicate(timeout=10)


def main():
    folder=ROOT/'target'/f'pi-console-controlled-{time.time_ns()}';folder.mkdir(parents=True)
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/kernel/Cargo.toml'),
                    '--release','--target','aarch64-unknown-none-softfloat'],check=True)
    source=ROOT/'bsp/rpi-zero2w/kernel/target/aarch64-unknown-none-softfloat/release/rustos-pi-kernel'
    kernel=folder/'kernel.elf';kernel.write_bytes(source.read_bytes());linked=symbols(kernel.read_bytes())
    adapter=build_adapter(folder);dtb=folder/'valid.dtb';dtb.write_bytes(fixture([(0,0x8000000)],dynamic=True))
    cases=[run(kernel,adapter,dtb,linked,mode,folder) for mode in ['ready','tx_timeout','drain_timeout','marker_tx_timeout','marker_drain_timeout','marker_lf_timeout']]
    subprocess.run(['cargo','build','--manifest-path',str(ROOT/'bsp/rpi-zero2w/kernel/Cargo.toml'),
                    '--release','--target','aarch64-unknown-none-softfloat','--features','panic-test'],check=True)
    panic_kernel=folder/'panic.elf';panic_kernel.write_bytes(source.read_bytes())
    cases.append(run(panic_kernel,adapter,dtb,symbols(panic_kernel.read_bytes()),'ready',folder,panic=True))
    for mode in ['panic_tx_timeout','panic_drain_timeout','panic_marker_tx_timeout','panic_marker_drain_timeout','panic_marker_lf_timeout']:
        cases.append(run(panic_kernel,adapter,dtb,symbols(panic_kernel.read_bytes()),mode,folder,panic=True))
    stack_reports={}
    for label,elf in [('normal',kernel),('panic',panic_kernel)]:
        result=audit(elf,include_console=True)
        if not result['passed']:raise RuntimeError('Linked console stack budget exceeded')
        path=folder/(label+'.stack.json');path.write_text(json.dumps(result,indent=2)+'\n')
        stack_reports[label]={'path':str(path),'root_bounds':result['root_bounds'],'maximum':result['stack_bound']}
    report={'passed':all(c['passed'] for c in cases),'cases':cases,
            'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'kernel_features':[],
            'panic_kernel_sha256':hashlib.sha256(panic_kernel.read_bytes()).hexdigest(),'panic_kernel_features':['panic-test'],
            'linked_stack_audits':stack_reports,
            'scope':'Debugger-synthetic response snapshot and optional RAM-backed UART fault; not firmware support, real baud or hardware acceptance'}
    path=folder/'report.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'checks':{c['mode']:c['checks'] for c in cases},'report':str(path)}))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
