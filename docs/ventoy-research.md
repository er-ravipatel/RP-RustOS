# Ventoy reuse assessment

2026-11-01. Requested source review, pinned to commit `74cff34240dca6991b79c6656770670da7b0c39e`. Reviewed selected source files and official documentation, not a complete audit. [Source identities](../out/research/ventoy-reference/sources.json) record immutable URLs and hashes. No Ventoy executable or installer was run, no code incorporated and no media modified. CMA implementation was interrupted before verification and is not reported complete here. D20 was approved by the user's preceding confirmation; it is no longer awaiting approval.

## What Ventoy contributes

Ventoy is a bootable-image launcher, not an OS kernel or a driver framework. Its composition includes GRUB and other existing projects. Its value for RustOS is primarily in the assembler, release-image and future boot-media layers.

| Feature or logic | Evidence inspected | Use in RustOS | Timing |
| --- | --- | --- | --- |
| Configuration plugin dispatch and validation | `ventoy_plugin.c`: separate check/entry handlers, path checks, image list and persistence configuration | Use typed extension points for board backends, image formats and product presets; validate before execution. Plugins here are configuration handlers, not arbitrary dynamically loaded modules. Keep RustOS strict schemas. | Assembler evolution |
| Image catalog, filtering and menu metadata | Image-list and menu structures in `ventoy_plugin.c` | Catalog normal, panic and later recovery images by board, architecture, hash and boot protocol. Expose compatible artifacts in the dashboard. Boot-menu implementation is separate work. | Catalog useful soon; on-device menu later |
| Checksum sidecars and verification from boot media | Official checksum documentation | Extend our existing manifest hashing with optional release sidecars and separately recorded post-write readback. Distinguish artifact validation, media readback and actual boot success. A checksum alone does not authenticate an image. | Release/media procedure |
| Boot assets separate from image payloads | Official two-partition layout; `ventoy_disk.c` recognizes MBR/GPT, signatures and partition geometry | Useful for a future maintenance/multiboot medium. Our approved M2 image stays one FAT32 partition; copying Ventoy's exFAT/payload layout would change its boot contract. | After M2 |
| Existing-layout validation | `ventoy_disk.c` checks signatures, sector positions/counts and Ventoy partition identity | Reinforces independent image inspection and exact expected layout checks. These routines recognize Ventoy geometry, not arbitrary RustOS images. | P8 design reference |
| Image-specific Linux boot preparation | `ventoy_linux.c`: initrd discovery/list handling and OS-specific processing | Shows why boot protocols need separate backends. Its Linux initrd and distribution adaptations do not apply to our bare-metal Rust kernel. | Future multi-OS tooling only |
| Persistence and installation templates | `ventoy_plugin.c`: per-image persistence backends and auto-install templates | Inspiration for separating immutable base images from writable state and for declarative installation. Requires storage/filesystem/process support not present in M2. | Later OS milestones |

## Most useful proposed workflow

Architecture + board + features → validated assembler plan → target image + manifest + hash → independent inspection → explicit media preparation/readback → boot capture tied to the exact image hash.

Ventoy adds useful catalog/menu and media-verification examples around this flow. It does not produce the Rust kernel or establish board driver support. Copying a raw RustOS Pi image as a file onto a Ventoy USB does not establish bootability: the firmware entry, payload protocol and hardware drivers must all match.

The official ARM64 page describes experimental **UEFI** support. That is a different environment from D16's direct Zero 2 W firmware handoff. No Zero 2 W or Pi 5 compatibility was established in this review. PC ISO/multiboot support is a possible later assembler backend, with its own acceptance tests.

## Source reuse and licences

The repository's COPYING contains GPLv3. Ventoy's official licence page states its author's code is GPLv3+ and modified upstream components retain their respective licences. Therefore component/file-level licence and distribution review is required before incorporating source. Translating copied implementation into Rust is not automatically a new permissively licensed work. Prefer implementing the documented behavior against RustOS's own interfaces unless a deliberate compatible code-reuse decision is made. This assessment is not a complete dependency/licence audit.

## Recommendation and review limits

First pass inspected the selected plugin, JSON, Linux boot-preparation and disk-recognition files plus README/COPYING. Second pass compared their execution environments, geometry and licence assumptions with RustOS D16–D19 and the assembler goal. Both passes are self-review; no Ventoy build, security audit or compatibility test was performed.

Adopt the design ideas for typed plugins, artifact catalogs and verification evidence. Preserve M2 scope and existing hashes. Defer multiboot menus, persistence, installer templates and a separate boot partition to future requirements. No new OS feature is marked implemented by this research. Resume the approved D20 implementation and verify any changes left by the interrupted command before proceeding.

## Primary references

- [Pinned plugin implementation](https://github.com/ventoy/Ventoy/blob/74cff34240dca6991b79c6656770670da7b0c39e/GRUB2/MOD_SRC/grub-2.04/grub-core/ventoy/ventoy_plugin.c).
- [Pinned disk recognition](https://github.com/ventoy/Ventoy/blob/74cff34240dca6991b79c6656770670da7b0c39e/LinuxGUI/Ventoy2Disk/Core/ventoy_disk.c).
- [Checksum behavior](https://www.ventoy.net/en/doc_checksum.html).
- [Disk layout](https://www.ventoy.net/en/doc_disk_layout.html).
- [ARM64 UEFI support](https://www.ventoy.net/en/doc_aarch64.html).
- [Composition](https://www.ventoy.net/en/doc_composition.html) and [licensing](https://www.ventoy.net/en/doc_license.html).
