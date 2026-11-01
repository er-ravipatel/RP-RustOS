# M2 boot-asset provenance and licence inventory

Current update: the [DTB reproduction](m2-dtb-reproduction.md) has now passed twice with exact bytes. Earlier prerequisite/reproduction gaps below describe the preceding checkpoint; final source/notice binding in the production asset lock remains open.

2026-11-01. Research findings, not a completed distribution package. No image is published or hardware verified. The [pinned research evidence](evidence/m2-asset-license-research.json) identifies exact URLs, lengths and SHA-256 values from two matching reads of each source reference.

## Inventory

Firmware candidate: `raspberrypi/firmware` commit `f2491b71ed49880cc8285e41e03f81b163c6cd59`.

| Asset | Repository's stated coverage | Required packaging follow-up |
| --- | --- | --- |
| bootcode.bin | boot/LICENCE.broadcom | Preserve unchanged bytes and the applicable notice |
| start.elf and fixup.dat | boot/LICENCE.broadcom | Keep matching pair, unchanged bytes and notice |
| bcm2710-rpi-zero-2-w.dtb | README assigns DTBs to Linux/GPL; boot/COPYING.linux supplied | Retain notice and prepare corresponding-source distribution material |
| Generated config and our flat kernel | Project-owned inputs, with their own dependency/source inventory | Identify sources and hashes; do not assign the firmware notice to our entire image |

The repository's own README distinguishes firmware from DTBs. Therefore the earlier five-file boot inventory is incomplete as a distribution inventory: at least COPYING.linux and the DTB source arrangement must be added before freezing a production lock. Additional overlays, if selected later, need their own entries and coverage.

The firmware notice permits unchanged binary redistribution for Raspberry Pi use under its stated conditions. Package its full notice rather than substituting a summary. This record does not determine the licensing of our separate kernel or assert that every component shares one licence.

## Source provenance and limits

At the selected firmware commit, extra/git_hash contains Linux commit `9b488bc7a1e9b61713082f3e6c4361988d62f77b`. The Zero 2 W board source and Linux COPYING exist at that exact revision and were read twice. The board source includes other DTS/header files; copying only the top-level DTS is insufficient to reproduce its build input.

The source pointer is evidence of intended provenance, not an independently reproduced DTB hash. A production asset process must preserve a suitable corresponding-source package and build information, including transitive includes, and inspect any per-file notices. Prefer preparing the source alongside the binary distribution rather than relying solely on an upstream link. The exact source payload/build recipe is still pending.

## Review passes

1. Checked the pinned repository README and boot directory notices against the initial asset list. Found the missing Linux notice and separate DTB coverage.
2. Followed extra/git_hash to immutable Linux source and COPYING, checked the board's include dependencies, and repeated all five reference reads with matching hashes. This checks provenance references; it does not establish binary reproduction or complete source-distribution obligations.

## Remaining gate

Before production asset-lock approval: add all notices, prepare the source payload and build instructions, inspect per-file coverage, and record whether the DTB can be rebuilt to the same bytes. Any unresolved reproduction discrepancy must remain visible. No synthetic licence relationship may be reused as real asset coverage.

## Primary references

- [Pinned firmware README](https://github.com/raspberrypi/firmware/blob/f2491b71ed49880cc8285e41e03f81b163c6cd59/README.md)
- [Pinned firmware notice](https://github.com/raspberrypi/firmware/blob/f2491b71ed49880cc8285e41e03f81b163c6cd59/boot/LICENCE.broadcom)
- [Pinned Linux notice supplied with binaries](https://github.com/raspberrypi/firmware/blob/f2491b71ed49880cc8285e41e03f81b163c6cd59/boot/COPYING.linux)
- [Pinned source-version hint](https://github.com/raspberrypi/firmware/blob/f2491b71ed49880cc8285e41e03f81b163c6cd59/extra/git_hash)
- [Pinned board DTS](https://github.com/raspberrypi/linux/blob/9b488bc7a1e9b61713082f3e6c4361988d62f77b/arch/arm/boot/dts/broadcom/bcm2710-rpi-zero-2-w.dts)
- [Pinned Linux COPYING](https://github.com/raspberrypi/linux/blob/9b488bc7a1e9b61713082f3e6c4361988d62f77b/COPYING)
