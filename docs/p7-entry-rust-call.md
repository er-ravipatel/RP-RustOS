# P7 actual EL1-to-Rust validator call

2026-11-01. D21 implementation experiment; production entry remains pending.

The [runner](../tools/test_entry_rust_call.py) builds the isolated BSP release library for AArch64 soft-float and links its actual exported validator into a no_std static-library harness. The [assembly call](../tools/entry-harness/rust-call.S) follows the existing complete stackless preflight and reviewed EL1 transition. It passes the bounded DTB in x0/x1 and an explicit, 16-byte aligned stack result pointer in x2. No BSS initialization is performed.

[Retained evidence](evidence/p7-entry-rust-call.json): all three cases passed:

| Case | Result |
| --- | --- |
| 128 MiB RAM, no dynamic request | Status 0; CMA base/size both zero. |
| 128 MiB RAM, 64 MiB request | Status 0; pool base 0x4000000, size 0x4000000. |
| 32 MiB RAM, 64 MiB request | Assembly shape preflight accepts; full Rust returns status 1 and leaves both output sentinels unchanged. |

Every case checks the exact success park at EL1, restored SP, the scalar return, both adjacent output guards, preserved x19/x20 DTB identity/length and x21-x29 sentinels. The rejection case reaches the success marker only after verifying the expected rejection and unchanged output; the marker therefore means the test passed, not that the invalid map was accepted.

A second execution of each ELF uses required CPU0 write watchpoints covering 0..0x3f0000 and 0x400000..0x20000000. A hardware breakpoint at the success park ends observation. All cases reach it without a write watchpoint firing. Thus the observed CPU0 writes within the 512 MiB board-addressable window are confined to the private stack, including the output buffer; code, DTB and any BSS in that window were not written during these executions. No watchpoint fallback is allowed.

The stack is initialized with a sentinel before observation. The lowest changed byte gives an observed write extent of 21,280 bytes below stack top for all three fixtures; the bottom 256-byte guard remains intact. This is finite execution evidence, not a static maximum stack-depth proof or evidence about untouched transient stack-pointer values. It does not observe DMA, other cores or MMIO outside the watched window.

The three earlier EL1 transition/fault/RAM-rejection cases also pass after this change. M1 entry, immutable M1 artifacts, boot asset lock and physical media are unchanged.

## Remaining gates

Complete register readback and unexpected CPU/control-state/affinity coverage, compile-time/reachable-call stack bounds, panic-path verification and production guard ordering before wiring the Pi kernel. This experiment performs extra CPU guards after the existing DTB preflight; production must place them before DTB reads. Physical Zero 2 W firmware/UART normal and panic acceptance remains separate.

See the [subsequent CPU guard and panic review](p7-entry-cpu-review.md) for updated guard ordering, broader register readbacks and the explicit remaining static-stack gap.
