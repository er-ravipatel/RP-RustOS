# P7 Pi-specific kernel entry scaffold

2026-11-01. The [isolated kernel target](../bsp/rpi-zero2w/kernel/Cargo.toml) now wires D16/D20/D21 into a Pi-specific entry ELF. It is an entry scaffold, not a complete M2 kernel or boot image. The original root workspace still has four members; M1 entry/artifacts and the approved firmware lock are unchanged.

## Entry behavior

Firmware enters at 0x200000 with DTB in x0. Entry masks interrupts, requires EL2, checks Cortex-A53 identity/full affinity and inherited translation/cache/endianness state before DTB reads, and parks secondary cores. The complete bounded register-only preflight precedes stack setup. It conservatively supports the reviewed single-bank/static-reservation shape and narrow CMA request; the full Rust validator remains authoritative.

The reviewed EL1 controls/vectors/stack are installed before ERET. The explicit C ABI calls the real BSP validator using the private stack and a 16-byte result buffer. Full validation failure parks without BSS initialization. Success preserves DTB/length and CMA base/size, clears the bounded linker BSS and stores the validated handoff in a 64-byte BSS boot record. It then parks at the labelled entry-ready point. No PL011 or other peripheral is touched yet. The unformatted Rust panic handler parks silently.

[Generated promotion check](../tools/sync_pi_entry_sources.py) keeps the checked-in [preflight](../bsp/rpi-zero2w/kernel/src/entry/preflight.S), CPU guards and EL1 controls identical to the reviewed fully enabled harness paths, except development stack-symbol spelling. Test injections and the EL3 reset adapter are excluded. Run the check before building entry changes; do not edit promoted files independently.

## First review: source and layout

Reviewed startup ordering and the promoted assembly against D16/D20/D21. The linker places code/data/BSS below 0x3f0000, with the entire 64 KiB private stack at 0x3f0000..0x400000 inside the proven kernel budget. BSS extent is aligned to 16 bytes for the eight-byte clear loop. Full Rust validation is the only call before BSS initialization, and its scalar failure branches directly to the park. DTB and selected pool survive the clear in callee-saved registers. The boot record is written only after validation and clearing.

## Second review: actual artifact and emulator

[Five actual-ELF cases pass](evidence/p7-pi-kernel-entry.json): valid RAM without CMA, valid 64 MiB CMA allocation, insufficient CMA space, zero RAM, and one reserved stack byte. The separate [QEMU EL3 adapter](../tools/entry-harness/pi-reset-adapter.S) is loaded at 0x100000; it is not linked into the Pi ELF. All four emulated cores execute it. Core 0 reaches the expected ready/rejection park; cores 1-3 park at EL2 with SP=0.

A separate CPU0 debugger execution seeds BSS with nonzero bytes. Required write watchpoints cover 0..512 MiB outside the private stack until either the BSS gate or rejection. Accepted cases reach the BSS gate with the sentinel unchanged, then continue to the ready point with zeroed BSS and the exact expected boot record. Rejected cases leave BSS unchanged. This is finite execution evidence, not a proof of every malformed input or physical firmware behavior.

The [actual linked stack audit](evidence/p7-pi-kernel-stack.json) passes at 21,440 bytes, including the 48-byte caller and reachable panic helpers, within the 65,536-byte budget. Release AArch64 build, target Clippy with warnings denied, four adversarial stack-checker test methods and source-promotion check pass. Both review passes are self-review.

## Build and remaining work

Build with `cargo build --manifest-path bsp/rpi-zero2w/kernel/Cargo.toml --target aarch64-unknown-none-softfloat --release`; verify with `python tools/test_pi_kernel_entry.py`.

Next implement reviewed Pi mailbox/GPIO/PL011 initialization and bounded startup/panic diagnostics, then integrate the target-specific assembler build and image packaging. The entry-ready marker is debugger-visible only. No UART boot acceptance, firmware-updated physical DTB, flat-image packaging, SD writing or physical board startup is claimed by these results. P7 and M2 remain in progress.
