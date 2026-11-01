// Generated from reviewed harness sources; run tools/sync_pi_entry_sources.py --check.
    adr x9, early_vectors
    msr vbar_el2, x9
    isb
    mov x19, x0
    tst x19, #7
    b.ne failed
    cmp x19, #0x1000
    b.lo failed
    mov x9, #0x20000000
    cmp x19, x9
    b.hs failed
    add x20, x19, #40
    mov x9, #0x20000000
    cmp x20, x9
    b.hi failed
    // Prove header does not overlap the entire kernel reservation before loads.
    mov x9, #0x400000
    cmp x19, x9
    b.hs header_read
    mov x9, #0x200000
    cmp x20, x9
    b.hi failed
header_read:
    ldr w9, [x19]
    rev w9, w9
    movz w14, #0xfeed
    movk w14, #0xd00d, lsl #16
    cmp w9, w14
    b.ne failed
    ldr w14, [x19, #4]
    rev w14, w14
    cmp x14, #40
    b.lo failed
    mov x9, #0x200000
    cmp x14, x9
    b.hi failed
    add x20, x19, x14
    mov x9, #0x20000000
    cmp x20, x9
    b.hi failed
    mov x9, #0x400000
    cmp x19, x9
    b.hs header_version
    mov x9, #0x200000
    cmp x20, x9
    b.hi failed
header_version:
    ldr w9, [x19, #20]
    rev w9, w9
    cmp w9, #17
    b.lo failed
    ldr w15, [x19, #24]
    rev w15, w15
    cmp w15, #16
    b.lo failed
    cmp w15, #17
    b.hi failed
    cmp w15, w9
    b.hi failed
    ldr w21, [x19, #8]
    rev w21, w21
    tst x21, #3
    b.ne failed
    ldr w23, [x19, #12]
    rev w23, w23
    ldr w15, [x19, #16]
    rev w15, w15
    cmp x15, #40
    b.lo failed
    tst x15, #7
    b.ne failed
    cmp x15, x21
    b.hi failed
    add x9, x15, #16
    cmp x9, x21
    b.hi failed
    ldr w16, [x19, #36]
    rev w16, w16
    cmp x16, #4
    b.lo failed
    tst x16, #3
    b.ne failed
    add x22, x21, x16
    cmp x22, x23
    b.hi failed
    ldr w16, [x19, #32]
    rev w16, w16
    add x24, x23, x16
    cmp x24, x14
    b.hi failed
    // Header reservations: bounded scans using registers only.
    add x26, x19, x15
    mov x28, x26
    add x21, x19, x21
    mov x25, #0
reservation_next:
    add x9, x28, #16
    cmp x9, x21
    b.hi failed
    ldr x1, [x28]
    rev x1, x1
    ldr x2, [x28, #8]
    rev x2, x2
    orr x9, x1, x2
    cbz x9, reservations_done
    cmp x25, #128
    b.hs failed
    adds x3, x1, x2
    b.cs failed
    cbz x2, reservation_advance
    mov x9, #0x20000000
    cmp x3, x9
    b.hi failed
    mov x9, #0x400000
    cmp x1, x9
    b.hs reservation_previous
    mov x9, #0x200000
    cmp x3, x9
    b.hi failed
reservation_previous:
    mov x7, x26
reservation_compare:
    cmp x7, x28
    b.hs reservation_advance
    ldr x4, [x7]
    rev x4, x4
    ldr x5, [x7, #8]
    rev x5, x5
    cbz x5, reservation_compare_next
    add x6, x4, x5
    cmp x1, x6
    b.hs reservation_compare_next
    cmp x4, x3
    b.lo failed
reservation_compare_next:
    add x7, x7, #16
    b reservation_compare
reservation_advance:
    add x25, x25, #1
    add x28, x28, #16
    b reservation_next
reservations_done:
    add x22, x19, x22
    add x23, x19, x23
    add x24, x19, x24
    mov x28, x21
    mov x25, #0
    mov x26, #0
    mov x27, #0
    mov x8, #0
    mov x17, #0
    mov x14, #0x100000
tree_next:
    cmp x25, #16384
    b.hs failed
    add x25, x25, #1
    add x9, x28, #4
    cmp x9, x22
    b.hi failed
    ldr w1, [x28], #4
    rev w1, w1
    cmp w1, #1
    b.eq tree_begin
    cmp w1, #2
    b.eq tree_end_node
    cmp w1, #3
    b.eq tree_property
    cmp w1, #4
    b.eq tree_next
    cmp w1, #9
    b.ne failed
    cmp x27, #2
    b.ne failed
    cbnz x26, failed
    cmp x28, x22
    b.ne failed
    b tree_done
tree_begin:
    cmp x27, #2
    b.eq failed
    cmp x26, #16
    b.hs failed
    mov x3, #0
tree_node_name:
    cmp x28, x22
    b.hs failed
    ldrb w6, [x28], #1
    cbz w6, tree_node_named
    add x3, x3, #1
    cmp x3, #128
    b.hi failed
    b tree_node_name
tree_node_named:
    cbnz x26, tree_child
    cbnz x27, failed
    cbnz x3, failed
    mov x27, #1
    b tree_node_padding
tree_child:
    cbz x3, failed
    mov x9, #1
    lsl x9, x9, x26
    orr x8, x8, x9
tree_node_padding:
    tst x28, #3
    b.eq tree_node_ready
    cmp x28, x22
    b.hs failed
    ldrb w6, [x28], #1
    cbnz w6, failed
    b tree_node_padding
tree_node_ready:
    add x26, x26, #1
    mov x17, #0
    mov x29, x28
    b tree_next
tree_end_node:
    cbz x26, failed
    mov x9, #1
    lsl x9, x9, x26
    bic x8, x8, x9
    sub x26, x26, #1
    cbnz x26, tree_next
    mov x27, #2
    b tree_next
tree_property:
    sub x30, x28, #4
    cbz x26, failed
    mov x9, #1
    lsl x9, x9, x26
    tst x8, x9
    b.ne failed
    cmp x17, #256
    b.hs failed
    add x17, x17, #1
    add x9, x28, #8
    cmp x9, x22
    b.hi failed
    ldr w1, [x28], #4
    rev w1, w1
    ldr w2, [x28], #4
    rev w2, w2
    add x2, x23, x2
    mov x12, x2
    mov x3, #0
tree_property_name:
    cmp x2, x24
    b.hs failed
    ldrb w6, [x2], #1
    cbz w6, tree_property_named
    add x3, x3, #1
    cmp x3, #128
    b.hi failed
    b tree_property_name
tree_property_named:
    cbz x3, failed
    // Prior properties are already locally validated; children are forbidden here.
    mov x15, x29
tree_duplicate_next:
    cmp x15, x30
    b.hs tree_property_value
    subs x14, x14, #1
    b.eq failed
    ldr w9, [x15], #4
    rev w9, w9
    cmp w9, #4
    b.eq tree_duplicate_next
    cmp w9, #3
    b.ne failed
    ldr w16, [x15], #4
    rev w16, w16
    ldr w5, [x15], #4
    rev w5, w5
    add x5, x23, x5
    mov x4, x12
tree_duplicate_name:
    subs x14, x14, #1
    b.eq failed
    ldrb w6, [x4], #1
    ldrb w7, [x5], #1
    cmp w6, w7
    b.ne tree_duplicate_skip
    cbz w6, failed
    b tree_duplicate_name
tree_duplicate_skip:
    add x15, x15, x16
    add x15, x15, #3
    and x15, x15, #0xfffffffffffffffc
    b tree_duplicate_next
tree_property_value:
    add x28, x28, x1
    cmp x28, x22
    b.hi failed
tree_property_padding:
    tst x28, #3
    b.eq tree_next
    cmp x28, x22
    b.hs failed
    ldrb w6, [x28], #1
    cbnz w6, failed
    b tree_property_padding
tree_done:
    // Full envelope/duplicate pass already succeeded. Rescan root properties.
    mov x26, x21
root_find:
    ldr w9, [x26], #4
    rev w9, w9
    cmp w9, #4
    b.eq root_find
    cmp w9, #1
    b.ne failed
    add x26, x26, #4
    mov x8, #0
root_next:
    ldr w9, [x26], #4
    rev w9, w9
    cmp w9, #4
    b.eq root_next
    cmp w9, #3
    b.ne root_done
    ldr w27, [x26], #4
    rev w27, w27
    ldr w12, [x26], #4
    rev w12, w12
    add x12, x23, x12
    mov x28, x26
    add x26, x26, x27
    add x26, x26, #3
    and x26, x26, #0xfffffffffffffffc
    mov x7, #1
    adr x4, root_compatible_name
root_compare_start:
    mov x5, x12
root_compare_name:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne root_other_name
    cbnz w1, root_compare_name
    cmp x7, #1
    b.eq root_compatible_value
    cmp x27, #4
    b.ne failed
    ldr w1, [x28]
    rev w1, w1
    cmp w1, #1
    b.lo failed
    cmp w1, #2
    b.hi failed
    orr x8, x8, x7
    cmp x7, #2
    b.ne root_size_value
    mov x29, x1
    b root_next
root_size_value:
    mov x30, x1
    b root_next
root_other_name:
    cmp x7, #1
    b.ne root_try_size
    mov x7, #2
    adr x4, root_address_name
    b root_compare_start
root_try_size:
    cmp x7, #2
    b.ne root_next
    mov x7, #4
    adr x4, root_size_name
    b root_compare_start
root_compatible_value:
    cbz x27, failed
    mov x1, x28
    add x2, x28, x27
    mov x6, #0
root_compatible_entry:
    adr x3, zero2w_compatible
    mov x4, #1
    mov x5, #0
root_compatible_byte:
    cmp x1, x2
    b.hs failed
    ldrb w7, [x1], #1
    cbz w7, root_compatible_end
    cmp w7, #0x20
    b.lo failed
    cmp w7, #0x7e
    b.hi failed
    add x5, x5, #1
    cbz x4, root_compatible_byte
    ldrb w9, [x3], #1
    cmp w7, w9
    b.eq root_compatible_byte
    mov x4, #0
    b root_compatible_byte
root_compatible_end:
    cbz x5, failed
    cbz x4, root_compatible_continue
    ldrb w9, [x3]
    cbnz w9, root_compatible_continue
    mov x6, #1
root_compatible_continue:
    cmp x1, x2
    b.lo root_compatible_entry
    cbz x6, failed
    orr x8, x8, #1
    b root_next
root_done:
    cmp x8, #7
    b.ne failed
    mov x26, x21
    mov x25, #0
    mov x24, #0
    mov x8, #0
    mov x22, #0
ram_next:
    ldr w9, [x26], #4
    rev w9, w9
    cmp w9, #1
    b.eq ram_begin
    cmp w9, #2
    b.eq ram_end_node
    cmp w9, #3
    b.eq ram_property
    cmp w9, #4
    b.eq ram_next
    cmp w9, #9
    b.ne failed
    cmp x8, #1
    b.ne failed
    b ram_done
ram_begin:
    cmp x25, #3
    b.ne ram_begin_parent_check
    cmp x24, #4
    b.eq failed
ram_begin_parent_check:
    cmp x25, #2
    b.ne ram_node_name
    cmp x24, #2
    b.eq ram_node_name
    cbnz x24, failed
ram_node_name:
    mov x5, x26
    mov x3, #0
ram_node_skip:
    ldrb w6, [x26], #1
    cbz w6, ram_node_skipped
    add x3, x3, #1
    b ram_node_skip
ram_node_skipped:
    add x26, x26, #3
    and x26, x26, #0xfffffffffffffffc
    cmp x25, #2
    b.ne ram_not_reserved_child
    cmp x24, #2
    b.ne ram_not_reserved_child
    and x9, x22, #7
    cmp x9, #7
    b.ne failed
    mov x24, #4
    mov x14, #0
    mov x15, #0
    mov x16, #0
    mov x17, #0
    cmp x3, #9
    b.ne ram_begin_ready
    adr x4, cma_node_name
    mov x7, #10
cma_node_compare:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne ram_begin_ready
    subs x7, x7, #1
    b.ne cma_node_compare
    mov x14, #1
    b ram_begin_ready
ram_not_reserved_child:
    cmp x25, #1
    b.ne ram_begin_ready
    mov x24, #0
    // Until the tree-reservation pass is implemented, never accept such a tree.
    mov x12, x5
    cmp x3, #15
    b.ne ram_memory_name
    adr x4, reserved_parent_name
    mov x7, #16
ram_reserved_guard:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne ram_memory_name
    subs x7, x7, #1
    b.ne ram_reserved_guard
    cbnz x22, failed
    mov x22, #8
    mov x24, #2
    b ram_begin_ready
    b failed
ram_memory_name:
    mov x5, x12
    cmp x3, #6
    b.lo ram_begin_ready
    adr x4, memory_device_type
    mov x7, #6
ram_node_compare:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne ram_begin_ready
    subs x7, x7, #1
    b.ne ram_node_compare
    ldrb w1, [x5]
    cbz w1, ram_candidate
    cmp w1, #0x40
    b.ne ram_begin_ready
ram_candidate:
    mov x24, #1
    mov x14, #0
    mov x15, #0
    mov x16, #0
    mov x17, #0
ram_begin_ready:
    add x25, x25, #1
    b ram_next
ram_property:
    ldr w27, [x26], #4
    rev w27, w27
    ldr w12, [x26], #4
    rev w12, w12
    add x12, x23, x12
    mov x28, x26
    add x26, x26, x27
    add x26, x26, #3
    and x26, x26, #0xfffffffffffffffc
    cmp x25, #3
    b.ne ram_property_root_depth
    cmp x24, #4
    b.eq ram_property_selected
ram_property_root_depth:
    cmp x25, #2
    b.ne ram_next
    cbnz x24, ram_property_selected
    // A root node declaring memory cannot hide behind an unrecognized name.
    adr x4, memory_type_name
    mov x5, x12
ram_unrecognized_type_name:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne ram_next
    cbnz w1, ram_unrecognized_type_name
    cmp x27, #7
    b.ne ram_next
    mov x7, #2
    adr x4, memory_device_type
    b ram_value_compare_start
ram_property_selected:
    cmp x24, #2
    b.ne ram_property_regular
    mov x7, #8
    adr x4, root_address_name
    b ram_property_compare_start
ram_property_regular:
    mov x7, #1
    adr x4, memory_reg_name
ram_property_compare_start:
    mov x5, x12
ram_property_compare:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne ram_property_other
    cbnz w1, ram_property_compare
    cmp x24, #2
    b.eq reserved_parent_value
    cmp x7, #1
    b.ne ram_property_value
    cmp x24, #4
    b.ne cma_reg_ready
    tst x14, #16
    b.ne failed
cma_reg_ready:
    mov x16, x28
    mov x17, x27
    b ram_next
ram_property_other:
    cmp x7, #1
    b.ne ram_try_status
    mov x7, #2
    adr x4, memory_type_name
    b ram_property_compare_start
ram_try_status:
    cmp x7, #8
    b.ne reserved_try_ranges
    mov x7, #16
    adr x4, root_size_name
    b ram_property_compare_start
reserved_try_ranges:
    cmp x7, #16
    b.ne reserved_try_parent_status
    mov x7, #32
    adr x4, reserved_ranges_name
    b ram_property_compare_start
reserved_try_parent_status:
    cmp x7, #32
    b.eq ram_status_name
    cmp x7, #2
    b.eq ram_status_name
    cmp x24, #4
    b.eq cma_try_property
    b ram_next
ram_status_name:
    mov x7, #4
    adr x4, memory_status_name
    b ram_property_compare_start
ram_property_value:
    cmp x7, #64
    b.hs cma_property_value
    cmp x24, #4
    b.ne ram_property_memory_value
    cmp x7, #4
    b.ne failed
ram_property_memory_value:
    cmp x7, #2
    b.ne ram_status_value
    mov x14, #2
    cmp x27, #7
    b.ne ram_next
    adr x4, memory_device_type
    b ram_value_compare_start
ram_status_value:
    mov x15, #2
    cmp x27, #9
    b.ne ram_status_okay
    adr x4, memory_disabled
    b ram_value_compare_start
ram_status_okay:
    cmp x27, #5
    b.ne ram_status_ok
    adr x4, memory_okay
    b ram_value_compare_start
ram_status_ok:
    cmp x27, #3
    b.ne ram_next
    adr x4, memory_ok
ram_value_compare_start:
    mov x5, x28
    mov x3, x27
ram_value_compare:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne ram_next
    subs x3, x3, #1
    b.ne ram_value_compare
    cbz x24, failed
    cmp x7, #2
    b.ne ram_status_matched
    mov x14, #1
    b ram_next
ram_status_matched:
    mov x15, #0
    cmp x27, #9
    b.ne ram_next
    mov x15, #1
    b ram_next
ram_end_node:
    cmp x25, #3
    b.ne reserved_parent_end
    cmp x24, #4
    b.eq reserved_child_end
reserved_parent_end:
    cmp x25, #2
    b.ne ram_normal_end
    cmp x24, #2
    b.ne ram_normal_end
    and x9, x22, #7
    cmp x9, #7
    b.ne failed
    mov x24, #0
    b ram_end_ready
ram_normal_end:
    cmp x25, #2
    b.ne ram_end_ready
    cbz x24, ram_end_ready
    cmp x15, #1
    b.eq ram_end_ready
    cbnz x15, failed
    cmp x14, #1
    b.ne failed
    cbnz x8, failed
ram_decode_range:
    cbz x16, failed
    add x9, x29, x30
    lsl x9, x9, #2
    cmp x17, x9
    b.ne failed
    cmp x29, #1
    b.ne ram_address_two
    ldr w1, [x16], #4
    rev w1, w1
    b ram_size
ram_address_two:
    ldr w1, [x16], #4
    rev w1, w1
    ldr w9, [x16], #4
    rev w9, w9
    lsl x1, x1, #32
    orr x1, x1, x9
ram_size:
    cmp x30, #1
    b.ne ram_size_two
    ldr w2, [x16]
    rev w2, w2
    b ram_range
ram_size_two:
    ldr w2, [x16]
    rev w2, w2
    ldr w9, [x16, #4]
    rev w9, w9
    lsl x2, x2, #32
    orr x2, x2, x9
ram_range:
    cbz x2, failed
    adds x3, x1, x2
    b.cs failed
    mov x9, #0x20000000
    cmp x3, x9
    b.hi failed
    cmp x24, #4
    b.eq reserved_static_range
    mov x9, #0x200000
    cmp x1, x9
    b.hi failed
    mov x9, #0x400000
    cmp x3, x9
    b.lo failed
    cmp x1, x19
    b.hi failed
    cmp x3, x20
    b.lo failed
    mov x8, #1
ram_end_ready:
    sub x25, x25, #1
    b ram_next
ram_done:
    b reserved_pass_done
reserved_parent_value:
    cmp x7, #4
    b.eq failed
    cmp x7, #32
    b.ne reserved_parent_cell
    cbnz x27, failed
    orr x22, x22, #4
    b ram_next
reserved_parent_cell:
    cmp x27, #4
    b.ne failed
    ldr w1, [x28]
    rev w1, w1
    cmp x7, #8
    b.ne reserved_parent_size
    cmp x1, x29
    b.ne failed
    orr x22, x22, #1
    b ram_next
reserved_parent_size:
    cmp x1, x30
    b.ne failed
    orr x22, x22, #2
    b ram_next
reserved_child_end:
    cmp x15, #1
    b.eq reserved_child_complete
    cbnz x15, failed
    tst x22, #16
    b.ne failed
    orr x22, x22, #16
    tst x14, #16
    b.ne cma_request_end
    b ram_decode_range
reserved_static_range:
    mov x9, #0x400000
    cmp x1, x9
    b.hs reserved_header_scan
    mov x9, #0x200000
    cmp x3, x9
    b.hi failed
reserved_header_scan:
    ldr w4, [x19, #16]
    rev w4, w4
    add x4, x19, x4
    mov x12, #0
reserved_header_next:
    ldr x5, [x4], #8
    rev x5, x5
    ldr x6, [x4], #8
    rev x6, x6
    orr x9, x5, x6
    cbz x9, reserved_child_complete
    cbz x6, reserved_header_next
    add x12, x12, #1
    cmp x12, #128
    b.hs failed
    add x7, x5, x6
    cmp x1, x7
    b.hs reserved_header_next
    cmp x5, x3
    b.lo failed
    b reserved_header_next
reserved_child_complete:
    mov x24, #2
    b ram_end_ready
cma_try_property:
    cmp x7, #4
    b.ne cma_try_reusable
    mov x7, #64
    adr x4, root_compatible_name
    b ram_property_compare_start
cma_try_reusable:
    cmp x7, #64
    b.ne cma_try_default
    mov x7, #128
    adr x4, cma_reusable_name
    b ram_property_compare_start
cma_try_default:
    cmp x7, #128
    b.ne cma_try_size
    mov x7, #256
    adr x4, cma_default_name
    b ram_property_compare_start
cma_try_size:
    cmp x7, #256
    b.ne cma_try_phandle
    mov x7, #512
    adr x4, cma_size_name
    b ram_property_compare_start
cma_try_phandle:
    cmp x7, #512
    b.ne failed
    mov x7, #1024
    adr x4, cma_phandle_name
    b ram_property_compare_start
cma_property_value:
    cmp x24, #4
    b.ne failed
    cmp x7, #64
    b.eq cma_compatible_value
    cmp x7, #128
    b.eq cma_reusable_value
    cmp x7, #256
    b.eq cma_default_value
    cmp x7, #512
    b.eq cma_size_value
    cmp x27, #4
    b.ne failed
    ldr w1, [x28]
    rev w1, w1
    cbz w1, failed
    mov w9, #0xffffffff
    cmp w1, w9
    b.eq failed
    b ram_next
cma_compatible_value:
    cmp x27, #16
    b.ne failed
    adr x4, cma_compatible
    mov x5, x28
    mov x3, #16
cma_compatible_compare:
    ldrb w1, [x4], #1
    ldrb w2, [x5], #1
    cmp w1, w2
    b.ne failed
    subs x3, x3, #1
    b.ne cma_compatible_compare
    orr x14, x14, #2
    b ram_next
cma_reusable_value:
    cbnz x27, failed
    orr x14, x14, #4
    b ram_next
cma_default_value:
    cbnz x27, failed
    orr x14, x14, #8
    b ram_next
cma_size_value:
    cbnz x16, failed
    orr x14, x14, #16
    mov x16, x28
    mov x17, x27
    b ram_next
cma_request_end:
    cmp x14, #31
    b.ne failed
    lsl x9, x30, #2
    cmp x17, x9
    b.ne failed
    ldr w1, [x16]
    rev w1, w1
    cmp x30, #1
    b.eq cma_size_checked
    ldr w2, [x16, #4]
    rev w2, w2
    lsl x1, x1, #32
    orr x1, x1, x2
cma_size_checked:
    cbz x1, failed
    mov x9, #0x20000000
    cmp x1, x9
    b.hi failed
    // Shape only: no physical allocation exists before the later Rust pass.
    b reserved_child_complete
reserved_pass_done:
