ENTRY(_start)
SECTIONS {
  . = 0x200000;
  .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.got*) }
  .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) __bss_end = .; }
  __test_stack_bottom = 0x3f0000;
  __test_stack_top = 0x400000;
  ASSERT(. <= __test_stack_bottom, "Rust harness overlaps test stack")
  ASSERT(_start == 0x200000, "Unexpected entry")
  /DISCARD/ : { *(.comment*) *(.eh_frame*) }
}
