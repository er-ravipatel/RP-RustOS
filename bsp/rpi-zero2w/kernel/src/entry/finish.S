// EL1 landing has completed; full Rust validation precedes every BSS write.
.global rust_call_begin
rust_call_begin:
    mov x19, x0
    ldr w20, [x19, #4]
    rev w20, w20
    sub sp, sp, #48
    stp xzr, xzr, [sp, #16]
    mov x0, x19
    mov x1, x20
    add x2, sp, #16
    bl rustos_validate_boot_memory
    cbnz w0, failed
    ldp x21, x22, [sp, #16]
    add sp, sp, #48
.global rust_call_end
rust_call_end:
    ldr x9, =__bss_start
    ldr x14, =__bss_end
.global bss_clear_begin
bss_clear_begin:
    cmp x9, x14
    b.hs bss_clear_done
    str xzr, [x9], #8
    b bss_clear_begin
bss_clear_done:
    mov x0, x19
    mov x1, x20
    mov x2, x21
    mov x3, x22
    ldr x9, =pi_boot_record
    stp x0, x1, [x9]
    stp x2, x3, [x9, #16]
    movz x10, #0x5353
    movk x10, #0x5041, lsl #16
.global pi_entry_ready
pi_entry_ready:
.ifdef PI_ENTRY_ONLY
    wfe
    b pi_entry_ready
.else
    b pi_initialize_console
.endif
failed:
    mov x10, #0xffff
.global failure_park
failure_park:
    wfe
    b failure_park
.global secondary_park
secondary_park:
    wfe
    b secondary_park
early_fault:
    mrs x14, esr_el2
    mrs x15, elr_el2
    mrs x16, far_el2
    mov x10, #0xf00d
fault_park:
    wfe
    b fault_park
.global pi_panic_park
pi_panic_park:
    wfe
    b pi_panic_park
.ltorg
.section .text.early_vectors,"ax"
.balign 2048
early_vectors:
.rept 16
    b early_fault
    .fill 31, 4, 0xd503201f
.endr
.section .rodata.entry_names,"a"
root_compatible_name: .asciz "compatible"
root_address_name: .asciz "#address-cells"
root_size_name: .asciz "#size-cells"
zero2w_compatible: .asciz "raspberrypi,model-zero-2-w"
memory_device_type: .asciz "memory"
memory_reg_name: .asciz "reg"
memory_type_name: .asciz "device_type"
memory_status_name: .asciz "status"
memory_disabled: .asciz "disabled"
memory_okay: .asciz "okay"
memory_ok: .asciz "ok"
reserved_parent_name: .asciz "reserved-memory"
reserved_ranges_name: .asciz "ranges"
cma_node_name: .asciz "linux,cma"
cma_reusable_name: .asciz "reusable"
cma_default_name: .asciz "linux,cma-default"
cma_size_name: .asciz "size"
cma_phandle_name: .asciz "phandle"
cma_compatible: .asciz "shared-dma-pool"
.section .bss.boot_record,"aw",@nobits
.balign 16
.global pi_boot_record
pi_boot_record:
    .skip 64
