# M1 kernel startup contract — proposal

Status: twice-checked startup contract approved by the user as an implementation baseline on 2026-10-31; not implemented RustOS behavior. Applies only to the selected QEMU profile, not Raspberry Pi hardware.

## Entry evidence and scope

QEMU 11.1.0, machine `virt-11.1,secure=off,virtualization=off,gic-version=2`, Cortex-A53, TCG, one core, 128 MiB, direct ELF loading. A corrected synthetic probe printed `ENTRY_EL_RAW=4`, observing EL1 (`CurrentEL` encodes the level shifted left two bits). The owned emulator process settled after termination. ELF entry remains `0x40080000`; the environment probe has exercised PL011 at `0x09000000`.

Two initial temporary register probes produced no output. Aligning the 64-bit UART literal to eight bytes made the narrowed CurrentEL probe work. Alignment was the changed variable; this does not prove the complete cause of every earlier failure. The attempted combined MMU-state probe did not produce usable evidence: MMU state is not recorded as independently measured. Startup must check its assumptions rather than relying on that failed probe.

## Proposed startup sequence

1. Assembly entry masks interrupts, reads CurrentEL, and accepts EL1 only for this initial profile. It must establish a diagnostic path or halt without a success marker on unsupported entry. EL2/EL3 normalization is deferred to a target that requires it.
2. Select SP_EL1 and establish a private 16-byte-aligned downward-growing stack before calling Rust. Never assume incoming SP or general-purpose registers are usable. Preserve any explicitly consumed boot data before overwriting it; M1 does not assume x0 contains a Linux-style DTB pointer for direct ELF loading.
3. Check translation state required for identity-address startup. Unexpected enabled translation causes explicit failure/halt; do not disable an unknown active mapping blindly. Define and inspect the exact initial SCTLR/cache assumptions during implementation before using ordinary Rust memory operations.
4. Establish non-overlapping linker-defined text, read-only data, writable data, BSS and stack ranges within the selected RAM region. Reserve `[0x40080000, 0x40200000)` for this initial kernel image/data/stack budget; fail the link if exceeded. Keep lower RAM and other addresses untouched. Proposed stack reservation is 64 KiB within that budget. This is a development limit, not a measured minimum or memory allocator.
5. Zero BSS without clearing the live stack or initialized data. ELF data segments supply initialized values; linker/ELF inspection must verify segment file/memory sizes and entry placement. No heap, dynamic loader, multicore, timer interrupt or scheduler is required in M1.
6. Install a 2048-byte-aligned EL1 vector table and handlers that report available ESR/ELR/FAR context, then halt on unexpected exceptions. Keep interrupts masked; asynchronous driver handling is later work. Early faults before vectors/console may only manifest as a missing marker.
7. Initialize polling PL011 through the selected BSP/driver with finite waits. Initialize driver ownership before normal Rust diagnostics. UART transfer/flush policy must ensure a final protocol line is observable before halting. The synthetic fixture's direct register writes are not a production driver implementation.
8. Check BSS/data sentinel values and stack alignment, and print initialization diagnostics. Only after these checks may the normal variant emit the exact final line `RUSTOS_BOOT_OK` and idle. The panic variant calls Rust's panic path after common initialization; only its expected panic handler emits diagnostics and the exact final line `RUSTOS_EXPECTED_PANIC` before halting. Unexpected panics/exceptions emit distinct failure markers. Ensure no allocation or unsafe recursive logger use in fault paths.

## Safety and build constraints

Use the selected bare-metal soft-float target, abort-on-panic and no unwinding. Soft-float ABI alone does not prove generated code never uses FP/SIMD; inspect code generation and explicitly establish or avoid required CPU state. Document assembly/Rust boundaries, linker invariants and volatile MMIO access. Stack overflow guards and memory isolation are later features; do not claim they are provided by a fixed stack reservation.

Both variants use the same source snapshot, target and linker layout, with an explicit internal variant flag. The normal kernel must never emit the expected-panic marker. The test handler must establish that the deliberate trigger was armed and reached, rather than treating any accidental panic in the test image as expected.

## Two-pass review

Pass 1: checked direct-ELF behavior in [QEMU 11.1.0 loader source](https://github.com/qemu/qemu/blob/v11.1.0/hw/arm/boot.c), the selected machine settings, and [AAPCS64 stack constraints](https://github.com/ARM-software/abi-aa/blob/2025Q4/aapcs64/aapcs64.rst). Do not import Linux raw-image entry assumptions into the direct ELF contract.

Pass 2: measured EL1 in an isolated corrected synthetic probe and reviewed ordering hazards: no Rust before stack, no BSS clearing over live stack, no success before vectors/console/sentinel checks, no generic panic mistaken for the deliberate scenario. No actual RustOS startup checks have executed. The memory/stack budgets and linker/vector/driver implementation need compile-time and emulator evidence in P4.

## Proposed acceptance evidence

Inspect the ELF entry and all loadable ranges; check linker overlap/budget assertions; verify normal BSS/data sentinels; capture both variant diagnostics and markers under the approved bounded recipe; induce an unexpected exception and confirm it fails rather than passing. Record compiler version/options, artifact hashes, QEMU version/arguments and cleanup result. Preserve failure traces and disassembly needed to explain startup issues.
