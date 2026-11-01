"""Observe a test-only first stack write with QEMU CPU0 GDB watchpoints."""
import hashlib
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from test_entry_handoff import ROOT, symbols, READ_ONLY_MNEMONICS
from probe_entry_machines import probe
from test_entry_memory_reference import fixture


class Remote:
    def __init__(self, connection):
        self.connection = connection
        connection.settimeout(2)

    def byte(self):
        value = self.connection.recv(1)
        if not value:
            raise RuntimeError('Debugger connection closed')
        return value

    def send(self, text):
        data = text.encode()
        self.connection.sendall(b'$'+data+b'#'+f'{sum(data)%256:02x}'.encode())
        if self.byte() != b'+':
            raise RuntimeError('Expected debugger acknowledgement')

    def receive(self):
        if self.byte() != b'$':
            raise RuntimeError('Expected debugger packet')
        data = bytearray()
        while True:
            value = self.byte()
            if value == b'#':
                break
            data.extend(value)
            if len(data)>2*1024*1024:
                raise RuntimeError('Debugger response exceeds bound')
        checksum = int(self.byte()+self.byte(),16)
        if sum(data)%256 != checksum:
            raise RuntimeError('Debugger checksum mismatch')
        self.connection.sendall(b'+')
        return data.decode()

    def request(self, text):
        self.send(text)
        return self.receive()

    def registers(self):
        raw = bytes.fromhex(self.request('g'))
        return {**{f'x{i}':int.from_bytes(raw[i*8:(i+1)*8],'little') for i in range(31)},
                'sp':int.from_bytes(raw[248:256],'little'),'pc':int.from_bytes(raw[256:264],'little')}


def observe(elf, dtb, linked, expected):
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0)); port=reservation.getsockname()[1]
    command=['C:/Program Files/qemu/qemu-system-aarch64.exe','-machine','raspi3b','-S',
             '-display','none','-serial','none','-monitor','none','-gdb',f'tcp:127.0.0.1:{port}',
             '-device',f'loader,file={elf},cpu-num=0',
             '-device',f'loader,file={dtb},addr=0x1000000,force-raw=on']
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    connection=None
    try:
        deadline=time.monotonic()+5
        while connection is None:
            try: connection=socket.create_connection(('127.0.0.1',port),timeout=0.2)
            except OSError:
                if time.monotonic()>deadline or process.poll() is not None: raise
                time.sleep(0.05)
        remote=Remote(connection)
        if remote.request('Hg1')!='OK' or remote.request('Hc1')!='OK':
            raise RuntimeError('Could not select CPU0 debugger thread')
        before=remote.registers()
        sentinel=bytes([0xa5])*32
        if remote.request('M3fffe0,20:'+sentinel.hex())!='OK':
            raise RuntimeError('Could not initialize test guard bytes')
        watch='2,0,20000000'  # CPU0 writes anywhere in the board-addressable window.
        if remote.request('Z'+watch)!='OK':
            raise RuntimeError('Emulator rejected write watchpoint; no fallback permitted')
        remote.send('c')
        try: stop=remote.receive()
        except socket.timeout:
            connection.sendall(b'\x03'); stop=remote.receive()
        stopped=remote.registers()
        memory_at_stop=bytes.fromhex(remote.request('m3fffe0,20'))
        checks={'watchpoint_installed':True,'initial_sp_zero':before['sp']==0}
        if expected=='write':
            # QEMU reports the watched range's base, not the access address.
            checks['first_stop_is_write']=bool(re.search(r'watch:0+;',stop))
            checks['write_pc']=stopped['pc'] in [linked['first_test_write'],linked['first_test_write']+4]
            checks['memory_unchanged_before_store']=memory_at_stop==sentinel
            if remote.request('z'+watch)!='OK': raise RuntimeError('Could not remove watchpoint')
            if stopped['pc']==linked['first_test_write']:
                remote.send('s'); step_stop=remote.receive()
            else: step_stop='already completed store'
            after=remote.registers()
            memory_after=bytes.fromhex(remote.request('m3fffe0,20'))
            wanted=sentinel[:16]+bytes.fromhex('8877665544332211')+sentinel[24:]
            checks.update(store_and_guards=memory_after==wanted,sp_after_store=after['sp']==0x3ffff0,
                          pc_after_store=after['pc']==linked['first_test_write']+4)
        else:
            checks.update(no_watchpoint='watch:' not in stop,
                          failure_marker=stopped['x10']==0xffff,
                          failure_pc=stopped['pc'] in [linked['failure_park'],linked['failure_park']+4],
                          sp_untouched=stopped['sp']==0,guard_unchanged=memory_at_stop==sentinel)
            after, memory_after, step_stop=stopped,memory_at_stop,None
        return {'command':command,'checks':checks,'passed':all(checks.values()),'stop':stop,
                'step_stop':step_stop,'initial_registers':before,'stop_registers':stopped,
                'after_registers':after,'memory_at_stop':memory_at_stop.hex(),'memory_after':memory_after.hex()}
    finally:
        if connection is not None: connection.close()
        if process.poll() is None: process.kill()
        process.communicate(timeout=10)


def main():
    folder=ROOT/'target'/f'entry-first-write-{time.time_ns()}'; folder.mkdir(parents=True)
    source=ROOT/'tools/entry-harness/handoff.S'
    rust=folder/'write_probe.rs'
    constants='\n'.join(f'.equ {name}, 1' for name in ['TEST_HEADER','TEST_TREE','TEST_ROOT','TEST_RAM','TEST_STATIC','TEST_CMA','TEST_WRITE'])
    rust.write_text('#![no_std]\ncore::arch::global_asm!('+json.dumps(constants)+');\ncore::arch::global_asm!(include_str!(r"'+str(source)+'"));\n')
    sysroot=Path(subprocess.check_output(['rustc','--print','sysroot'],text=True).strip())
    linker=sysroot/'lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
    obj,elf=folder/'probe.o',folder/'probe.elf'
    commands=[['rustc',str(rust),'--crate-type','lib','--target','aarch64-unknown-none-softfloat','--emit=obj','-o',str(obj)],
              [str(linker),'-flavor','gnu','-T',str(ROOT/'tools/entry-harness/link.ld'),str(obj),'-o',str(elf)]]
    for command in commands: subprocess.run(command,capture_output=True,check=True,timeout=60)
    linked=symbols(elf.read_bytes())
    count=(linked['harness_code_end']-linked['_start'])//4
    inspection=probe('C:/Program Files/qemu/qemu-system-aarch64.exe','raspi3b',
                     ['-device',f'loader,file={elf},cpu-num=0'],disassemble=(linked['_start'],count))
    decoded=re.findall(r'^0x([0-9a-fA-F]+):\s+[0-9a-fA-F]{8}\s+(\S+)([^\r\n]*)',inspection['disassembly'],re.MULTILINE)
    stores=[(address,operands.strip()) for address,mnemonic,operands in decoded if mnemonic=='str']
    stack_moves=[(address,operands.strip()) for address,mnemonic,operands in decoded if mnemonic=='mov' and re.search(r'\bsp\b',operands)]
    instruction_checks={
        'complete_decode':len(decoded)==count,
        'single_labelled_store':len(stores)==1 and int(stores[0][0],16)==linked['first_test_write'] and bool(re.fullmatch(r'x9,\s*\[sp,\s*#-0x10\]!',stores[0][1])),
        'single_labelled_sp_setup':len(stack_moves)==1 and int(stack_moves[0][0],16)==linked['stack_pointer_setup'] and bool(re.fullmatch(r'sp,\s*x9',stack_moves[0][1])),
        'remaining_code_read_only':all((mnemonic=='str' and int(address,16)==linked['first_test_write']) or
                                      (mnemonic=='mov' and int(address,16)==linked['stack_pointer_setup']) or
                                      (mnemonic in READ_ONLY_MNEMONICS and not re.search(r'\b(?:sp|wsp)\b',operands))
                                      for address,mnemonic,operands in decoded)}
    ram=[(0,0x8000000)]
    cases=[('valid',fixture(ram),'write'),
           ('zero_ram',fixture([(0,0)]),'reject'),
           ('reserved_stack_byte',fixture(ram,reserved=(0x3ffff0,1)),'reject'),
           ('invalid_cma',fixture(ram,dynamic=True,dynamic_props={'no-map':b''}),'reject')]
    results=[]
    for name,data,expected in cases:
        path=folder/f'{name}.dtb'; path.write_bytes(data)
        result=observe(elf,path,linked,expected)
        result.update(name=name,expected=expected,fixture_sha256=hashlib.sha256(data).hexdigest())
        results.append(result)
    report={'passed':all(c['passed'] for c in results) and all(instruction_checks.values()),'cases':results,'symbols':linked,'build_commands':commands,
            'instruction_checks':instruction_checks,'instruction_inspection':inspection,
            'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'scope':'CPU0 test-only watchpoint over 0..512 MiB; no production stack, Rust call or physical boot'}
    path=folder/'report.json'; path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'failed_cases':{c['name']:c['checks'] for c in results if not c['passed']},'report':str(path)}))
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__': main()
