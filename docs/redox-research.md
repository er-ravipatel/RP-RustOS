# Redox reference research

2026-11-01. Read-only review of the user-supplied source at `E:/Work/redox-master/redox-master`. The outer directory contains this nested root. No Redox scripts were executed, dependencies downloaded, source copied or RustOS boot policy changed. No `.git` history was present in the inspected root; its upstream commit identity is unverified.

## What the supplied repository contains

The README identifies it as the Redox **build system**. It includes Cookbook Rust code, package recipes, image configurations and Make-based orchestration. Kernel, base drivers, bootloader and filesystem are separate repositories. In particular, `recipes/core/kernel/recipe.toml` points to the kernel repository, and the bootloader recipe points to a different repository. The actual kernel entry and memory-management implementation cannot be reviewed from these recipes alone.

Redox is a Rust-based microkernel operating system. This does not imply every shipped program, firmware component or build dependency is Rust. Its recipe tree includes ports of third-party software. Source reuse needs a component-specific licence review; the supplied build-system LICENSE is MIT and requires preservation of its notice.

## Findings mapped to RustOS

| Observed mechanism | Local evidence | Application to RustOS |
| --- | --- | --- |
| Separate architecture, board and product configuration | `mk/config.mk`: ARCH, BOARD, CONFIG_NAME and filesystem config selection | Supports our architecture → board → modules → image selection direction. Keep explicit compatibility checks. |
| Layered filesystem/package profiles | `config/minimal.toml` includes base; board minimal profile includes shared minimal | Useful later for reusable product presets; define deterministic merge/conflict rules before adding inheritance. |
| Source recipes and staging | `recipes/core/kernel/recipe.toml`, bootloader recipe; `src/config.rs` recipe locks/offline settings | Keep acquisition, compilation, staging and packaging separate. Extend our locked inputs rather than importing shell execution wholesale. |
| Staged image publication | `mk/disk.mk` writes `.partial` then renames | Reinforces our staged immutable outputs. Rename alone does not prove independent validation or byte reproducibility. |
| Multiple boot/image families | `mk/disk.mk`, `recipes/core/bootloader/recipe.toml` | Confirms image format is target-specific. A Pi SD image and a PC ISO need different backends. |
| Explicit Pi emulator path | `mk/qemu.mk` raspi3bp branch uses raspi3b machine, 1 GiB, four cores and U-Boot | A reference for target-specific emulator runners, not evidence for either of the user's Pi models. |

The inspected Pi profile is `config/aarch64/raspi3bp/minimal.toml` with a 256 MiB filesystem and 128 MiB EFI partition. Its QEMU runner fetches a U-Boot binary from a mutable `main` URL; no hash check appears in that rule. RustOS should preserve its stricter pinned asset lock and independent image reader. No complete upstream security/reproducibility audit is implied.

## Architecture and boot implications

Build-time modular selection is compatible with multiple kernel architectures. Redox's microkernel design is useful research for later process isolation, driver services, resource APIs and fault containment; it does not by itself justify changing the current RustOS kernel or M2 acceptance criteria. A microkernel migration would require its own requirements, IPC/service model, driver boundaries and performance/verification plan.

The AArch64 bootloader recipe builds UEFI executables. The Pi emulator branch provides U-Boot. RustOS D16 currently specifies direct Pi firmware → flat Rust kernel at 0x200000 with DTB and a reviewed EL2-to-EL1 path. These are different boot contracts. Redox's builder therefore does not answer whether our pinned firmware updates memory correctly, how to handle its CMA node, or how to establish a stack safely. D20 stays proposed and unimplemented.

## Two review passes and recommendation

Pass one read the README, architecture/board selection, minimal and board profiles, kernel and bootloader recipes, Cookbook configuration/lock types, image rules and Pi QEMU rules. Pass two cross-checked their relationships and compared the observed UEFI/U-Boot route, image geometry and source-fetch rules with RustOS D16–D19. Both are self-review; neither is a Redox build, kernel audit, emulator run or physical test.

Use Redox immediately as an assembler design reference. Keep M1/M2 scope and the existing asset lock. Before reusing low-level code, review pinned versions of the separate kernel and bootloader repositories, concentrating on AArch64 entry, DTB parsing and memory reservations. This can be a focused follow-up without building or replacing RustOS. Do not present Pi 3 emulator configuration as Zero 2 W/Pi 5 hardware compatibility.

## Primary sources and access limits

The supplied GitLab project and website docs landing page returned HTTP 403 through the research browser. The local README points to the Redox Book; its official GitHub mirror provided accessible documentation:

- [Build-system reference](https://github.com/redox-os/book/blob/master/src/build-system-reference.md): architecture/board configuration, package recipes, staging and images.
- [Hardware support](https://github.com/redox-os/book/blob/master/src/hardware-support.md): AArch64 support has limitations; generic architecture support is not a board guarantee.
- [Kernel mirror](https://github.com/redox-os/kernel): follow-up source, not yet inspected in this review.
- [User-provided upstream build repository](https://gitlab.redox-os.org/redox-os/redox/).

Local files are the basis for the specific code observations above. Online documentation is rolling and is not asserted to match the unversioned local snapshot exactly.
