# Redox AArch64 boot reference review

2026-11-01. Focused read-only source review; no upstream build or hardware test. Official GitHub mirrors were resolved through the GitHub API and selected files downloaded at immutable commits:

- Kernel: `b68957d4a3e1590c4f5b8d5608d94b3e45bd3b45`.
- Bootloader: `cc922ec0bb3f9dd31cce589bb513ab2f15ac9746`.

These independently selected revisions are research snapshots, not a proven mutually compatible Redox release. [Source manifest](../out/research/redox-reference/sources.json) records URLs and SHA-256 hashes. Only selected files were retrieved, not complete dependency closures. Both inspected root licences are MIT; no source was incorporated into RustOS.

## Evidence and implications

| Inspected source | Observation | RustOS implication |
| --- | --- | --- |
| Bootloader `src/os/uefi/dtb.rs` | Looks up DEVICE_TREE_GUID in UEFI configuration tables, parses a raw pointer and copies the DTB into allocated page-aligned memory using heap storage | Useful separation of discovery and ownership; allocation and pointer readability are already assumed. This cannot establish our first safe stack or heap. |
| Bootloader `src/os/uefi/memory_map.rs` | Gets UEFI memory descriptors and map key, checks descriptor size/version, classifies memory, exits boot services and installs runtime virtual mappings | Memory ownership comes from UEFI, rather than only Pi firmware's DTB. Do not substitute its classifications for our RAM/reservation validation. |
| Bootloader `src/os/uefi/arch/aarch64.rs` | Handles EL2-to-EL1 or existing EL1, configures timer/trap/system registers, switches page tables, sets stack and invokes the kernel with KernelArgs | A register checklist and review reference, not an approved mask set for Cortex-A53 direct firmware entry. Its live MMU transition differs from D16's rejection of unexpected enabled entry state. |
| Bootloader `src/arch/aarch64.rs` | Builds mappings and allocates page-table storage through the OS allocator; distinguishes memory attributes | Useful for future MMU milestones; outside M2's no-MMU scope. |
| Kernel `src/arch/aarch64/start.rs` | Naked entry checks BSS/data, establishes a static 128 KiB stack and vectors, then reads KernelArgs and initializes memory/device services | Kernel expects a prepared loader environment. The RustOS stack remains 64 KiB and cannot be assumed writable from this example. |
| Kernel `src/arch/aarch64/device/cpu/boot.rs` | Separate secondary CPU protocol with argument state, translation/control registers and readiness/failure states | Good future multicore reference. Keep secondary cores parked in M2. |

The inspected kernel starts early serial discovery from hardware descriptor data before normal logging. This supports distinguishing early diagnostics from full device initialization. It does not establish our board GPIO mux or UART clock preparation. The architecture serial file inspected delegates to other shared modules; the complete PL011 implementation was not audited here.

## Two review passes

Pass one traced UEFI DTB discovery, allocation and memory-map ownership into the AArch64 loader transition and kernel entry. Pass two compared those assumptions against RustOS D16, the existing bounded validator and D20. The decisive mismatch is the pre-existing UEFI execution/allocator environment: copying these paths cannot prove our memory safe before the first stack write. These are self-review passes, not independent audits.

The inspected DTB-copy path and UEFI map classifier provide no direct solution for the dynamic CMA request in our handoff tree. No claim is made that CMA is absent from every Redox component; the review covered selected sources only. D20 remains proposed and runtime rejection remains unchanged.

## Recommendation

Retain Redox as a reference for the assembler recipe/staging model, explicit boot argument ownership, memory classes, early diagnostics and later services/multicore work. Continue RustOS's approved direct Pi boot path and bounded validation. A migration to U-Boot/UEFI or a Redox-derived microkernel would be a separate architectural decision with new assets, image content and acceptance tests; this research does not authorize it.

The next direct-boot design work remains the narrowly scoped CMA reservation policy and a register-only preflight specification, followed by emulator/disassembly checks before kernel wiring. D20 needs the user's pending confirmation; no firmware/image changes or SD writes occurred.

## Immutable primary sources

- [Redox kernel entry](https://github.com/redox-os/kernel/blob/b68957d4a3e1590c4f5b8d5608d94b3e45bd3b45/src/arch/aarch64/start.rs).
- [Redox UEFI CPU handoff](https://github.com/redox-os/bootloader/blob/cc922ec0bb3f9dd31cce589bb513ab2f15ac9746/src/os/uefi/arch/aarch64.rs).
- [Redox UEFI memory map](https://github.com/redox-os/bootloader/blob/cc922ec0bb3f9dd31cce589bb513ab2f15ac9746/src/os/uefi/memory_map.rs).
- [Redox DTB discovery/copy](https://github.com/redox-os/bootloader/blob/cc922ec0bb3f9dd31cce589bb513ab2f15ac9746/src/os/uefi/dtb.rs).
