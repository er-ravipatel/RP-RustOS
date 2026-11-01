ENTRY(_start)
PHDRS { text PT_LOAD FLAGS(5); rodata PT_LOAD FLAGS(4); data PT_LOAD FLAGS(6); }
SECTIONS {
  . = 0x40080000;
  __kernel_start = .;
  .text : ALIGN(16) { KEEP(*(.text.entry)) *(.text .text.*) } :text
  .rodata : ALIGN(4096) { *(.rodata .rodata.*) } :rodata
  .data : ALIGN(4096) { *(.data .data.*) *(.got .got.*) } :data
  .bss (NOLOAD) : ALIGN(16) { __bss_start = .; *(.bss .bss.*) *(COMMON) . = ALIGN(16); __bss_end = .; } :data
  .stack (NOLOAD) : ALIGN(16) { __stack_bottom = .; . += 0x10000; __stack_top = .; } :data
  __kernel_end = .;
  /DISCARD/ : { *(.eh_frame*) *(.comment*) }
  ASSERT(__kernel_end <= 0x40200000, "M1 kernel exceeds reserved budget")
  ASSERT((__stack_top & 15) == 0, "Stack must be 16-byte aligned")
  ASSERT(__bss_end <= __stack_bottom, "BSS overlaps stack")
}
