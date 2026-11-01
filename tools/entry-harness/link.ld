ENTRY(_start)
SECTIONS {
  . = 0x200000;
  .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) }
  __test_stack_bottom = 0x3f0000;
  __test_stack_top = 0x400000;
  ASSERT(. <= __test_stack_bottom, "Harness image overlaps test stack")
  ASSERT(_start == 0x200000, "Unexpected harness entry")
  /DISCARD/ : { *(.comment*) *(.eh_frame*) }
}
