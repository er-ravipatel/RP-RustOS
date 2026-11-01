ENTRY(_start)
SECTIONS {
  . = 0x200000;
  .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.got*) }
  . = ALIGN(16);
  .bss (NOLOAD) : { __bss_start = .; KEEP(*(.bss.pi_clock)) *(.bss*) *(COMMON) . = ALIGN(16); __bss_end = .; }
  __stack_bottom = 0x3f0000;
  __stack_top = 0x400000;
  ASSERT(_start == 0x200000, "Unexpected Pi entry")
  ASSERT(__bss_end <= __stack_bottom, "Pi image overlaps private stack")
  ASSERT(__stack_top - __stack_bottom == 0x10000, "Unexpected stack budget")
  /DISCARD/ : { *(.comment*) *(.eh_frame*) }
}
