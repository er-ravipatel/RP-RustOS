# M2 boot-memory and CPU-entry proposal

2026-11-01. Direction approved by the user as D16. Not implemented or hardware verified. This is separate from the agreed [console contract](m2-console-contract.md).

## Selected direction

Use a separate Zero 2 W entry path and linker script. Configure AArch64 mode explicitly, select an uncompressed flat kernel file explicitly, and set `kernel_address=0x200000`. Link its first executable byte and ELF entry to the same address. Do not depend on firmware defaults or change the accepted QEMU address.

Reserve the half-open range [0x200000, 0x400000) for all kernel load segments, BSS, vectors, mailbox storage and a 64 KiB stack. This 2 MiB budget is a project limit, not a statement about total board RAM. Linker assertions reject any overflow, misaligned stack/vector area or overlap. The flat file contains initialized load bytes and zero-filled gaps; BSS and stack remain runtime memory. Conversion rejects overlapping segments, out-of-range addresses and an entry that does not match the first instruction. Keep ELF and flat-file hashes in the manifest.

Preserve low memory, including firmware stub/spin-table storage. Do not release secondary cores in M2. Any secondary reaching our entry parks before touching shared data or stack. No scheduler, MMU, cache enablement or multicore execution is introduced by this milestone.

## CPU handoff

1. Mask asynchronous exceptions and preserve the incoming x0 device-tree pointer in a register before reading CurrentEL. Do not write globals before the primary-core check and memory-safety checks.
2. Support the expected non-secure AArch64 EL2 entry for this first Pi contract. Reject other levels without emitting success. Direct EL1 entry can be a separately reviewed future contract; it must not be silently guessed.
3. Check inherited EL2 MMU/data/instruction cache state. Unexpected enabled state is rejected; disabling a live MMU or cache without a reviewed transition is not an acceptable shortcut.
4. Establish EL1 AArch64 execution, explicitly initialize relevant EL2 control/trap/timer state, EL1 system-control state and the private EL1 stack, then return through ERET into EL1h with exceptions masked. Register writes must respect Cortex-A53 RES0/RES1 requirements. Exact instruction/register masks require architecture-reference review and disassembly verification in P7, before execution.
5. At EL1, initialize BSS, FP/SIMD permission and exception vectors, retaining the current startup self-checks. Retain the DTB pointer outside the cleared region until it is safely transferred into initialized boot information.
6. Prepare the board console through the agreed failure-aware board interface, then emit startup diagnostics only after all required checks pass.

Unexpected entry can be silent before UART initialization. A bounded host capture must classify silence as failure, never as a completed diagnostic. Physical-board power removal is an operator action, not owned-process cleanup.

## Device-tree and reserved-memory safety

Do not assume a firmware-selected DTB address. Require an aligned pointer within a conservative board-addressable RAM window; reject arithmetic overflow and any overlap with our complete reserved interval before clearing BSS or establishing writable stack use. Header reads must themselves be bounded and outside our write region. Cap accepted DTB size at 2 MiB as our parser limit.

Validate FDT magic, total length, block offsets and reservation ranges before using its contents. Establish that the full kernel reservation lies in ARM-accessible RAM and outside firmware/device-tree reservations before board services write buffers. Reject unsupported or inconsistent layouts. Never derive usable RAM from the board's advertised total alone. These requirements imply a small stackless preflight and a bounded parser; their implementation deserves explicit negative tests.

Do not add a Linux Image header merely because Linux documentation describes one. This project boots a bare-metal flat image with explicit configuration. Confirm that the pinned firmware obeys the configured placement on hardware; a host-side file check alone cannot prove firmware handoff.

## Two review passes and evidence limits

First pass: official Pi boot configuration defines explicit load placement; published Arm stub source selects EL2, supplies the DTB pointer and parks secondary cores. The Linux AArch64 boot document provides an independent description of the conventional register handoff and cache/exception preconditions, but is not a RustOS specification or proof of the firmware binary.

Second pass: inspected the actual M1 entry, linker, build script and startup self-checks. Found the EL1-only check, overwritten x0, fixed QEMU link address and unconditional stack/BSS setup that require board separation. Checked the proposed budget arithmetically: 0x400000 - 0x200000 = 2 MiB; the 64 KiB stack is inside this budget. Reviewed cold-boot failure cases below. Both passes are Codex self-review, not independent human or physical validation.

Required checks during implementation: unsupported EL, secondary entry, wrong entry address, oversized/overlapping load segments, stack/BSS overlap, invalid DTB pointer/header/length, reserved-memory collision, unexpected cache/MMU state, and console preparation failure. No such failure may emit startup success. M1 must retain its existing regression coverage.

## Sources

- [Explicit firmware load-address option](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/legacy_config_txt/boot.adoc)
- [Kernel selection and AArch64 configuration](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/config_txt/boot.adoc)
- [Published Pi Arm stub](https://github.com/raspberrypi/tools/blob/master/armstubs/armstub8.S)
- [Linux AArch64 boot handoff for comparison](https://docs.kernel.org/arch/arm64/booting.html)
- [Board-family address map and spin-table locations](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/broadcom/bcm2837.dtsi)

Decision D16: user approved explicit 2 MiB load placement, a separate Pi EL2-to-EL1 startup path, one active core and bounded DTB/reserved-memory validation on 2026-11-01. Image geometry and profile/report schemas remain separate decisions. Approval does not waive the register-level implementation review or hardware acceptance.
