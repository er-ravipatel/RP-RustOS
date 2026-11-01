# M2 real asset-lock review

2026-11-01. Decision D19 approved by the user. The [real asset lock](../assets/locks/rpi-zero2w-boot-assets.lock.json) is a concrete candidate for the M2 implementation baseline, distinct from the synthetic examples. It is not yet consumed by the Rust assembler.

## Locked contents

- Firmware repository commit `f2491b71ed49880cc8285e41e03f81b163c6cd59`: bootcode.bin, matched start.elf/fixup.dat, Zero 2 W DTB, LICENCE.broadcom and COPYING.linux.
- Linux source commit `9b488bc7a1e9b61713082f3e6c4361988d62f77b`: complete source archive, immutable URL, exact size and SHA-256.
- Build materials: pinned-base Dockerfile, source build script, bounded runner and package instructions, with exact file identities.
- Reproduction evidence: both fresh-container runs, original/rebuilt DTB identities and retained compiler/config/command/log evidence.

Every asset has a hash, length and immutable origin. Firmware and DTB use separate explicit notice bindings. The DTB references the source package. Source archive, instructions and evidence are independently hashed. Changes require an explicit lock update and revalidation; a mutable download is not an acceptable substitute.

## Two review passes

First: structural and cross-record validation, plus local byte checks for all six assets, the complete archive, build materials and proof records. Second: re-read/rehashed retained bytes and reviewed wrong notice/source references, changed commit URLs, path collisions, same-length corruption and wrong lengths. The checker confirms each retained rebuilt DTB hash/length equals the locked DTB and rechecks all retained build artifacts against the bound evidence.

[Validation evidence](evidence/m2-asset-lock-validation.json) records the candidate lock hash and checker identities. All 62 M2 test methods pass, alongside 12 M1 design and 25 dashboard tests. Counts describe contract/local-check coverage, not 62 OS executions.

## Distribution and implementation requirements

Ship the source archive, notices and build instructions as retained bundle-side material associated with the locked DTB. The 257 MB source archive is outside the 64 MiB boot images; it must not be silently squeezed into FAT or omitted from the distribution plan. Actual image/bundle file mappings, manifest identities and bounded asset acquisition/snapshot budgets must be implemented and checked in P7/P8. Existing M1 input limits must not be weakened globally to fit this archive.

The cache checker is a read-only review utility. It rejects unsafe paths and reparse/symlink inputs, checks sizes/hashes, and notices ordinary changes during a read. It is not the runtime's stable-handle loader or a substitute for Windows ownership/identity protections. Hashes do not prove author authenticity. The Docker base is pinned; package versions are captured in the resulting image/logs rather than snapshot-pinned for a future clean image rebuild.

The notices and complete source are preserved, and this selected DTB is reproduced exactly. This is a technical packaging/provenance review, not a legal opinion about every possible distribution. Any additional boot asset or overlay needs the same review before it is added.

## Approval scope

Approve D19 to use this exact pinned asset/source set as the M2 baseline, including source/notice sidecar material and explicit offline checks. Approval does not establish image packaging, Rust Pi startup or hardware success. Those remain implementation and acceptance work. Hardware setup is still unrecorded.
