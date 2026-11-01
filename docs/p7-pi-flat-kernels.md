# P7 flat Pi kernel generation

2026-11-01. The internal [Pi compiler](../tools/assembler/src/pi_build.rs) now converts each reviewed normal/panic ELF into a separate kernel8.img engineering artifact. Both flat and ELF SHA-256, flat byte length and explicit 0x200000 load address are recorded in the [compiler evidence](evidence/p7-pi-flat-compiler.json).

The bounded converter requires ELF64 little-endian AArch64 executable identity, entry 0x200000 and a bounded program-header table. It rejects overflow, truncated fields, mismatched virtual/physical addresses, invalid file/memory extents, overlapping load segments, invalid alignment, writable executable loads and load memory outside [0x200000,0x3f0000). The first executable segment must begin at the configured entry and include an instruction. Initialized bytes are copied at physical-load offsets; gaps are zero-filled. Memory-only tails and the private stack are not appended to the flat file. Output uses the existing create-new writer.

[Independent Python reconstruction](evidence/p7-pi-flat-contracts.json) reproduces the complete expected bytes from ELF headers and compares contents, digest, length and load address for both variants. Layout and conservative stack checks pass again on the new ELFs, both at 21,440/65,536 bytes. [Exact-output entry verification](evidence/p7-pi-flat-entry.json) passes all ten memory/BSS scenarios and four-core observations. Current QEMU still safely rejects measured-clock service at stage 4; no UART success is claimed. Entry execution in this record loads ELFs, not flat files or SD images.

41 regular Rust tests pass, including synthetic initialized ranges/gaps/BSS-tail behavior and malformed/truncated/overflowing ELF rejection. The explicit two-variant offline build, five M1 CLI tests and nine M1 build acceptance tests pass. Scoped all-target Clippy passes with the previously recorded result_large_err exception.

First self-review checked checked arithmetic, memory limits, segment overlap and runtime-only storage. Second self-review checked independent byte reconstruction, exact-output entry/stack identity and unchanged M1 acceptance.

These are kernel engineering files, not complete bootable SD-card images. Next: locked firmware and source notices, normal/panic image packaging, independent image inspection and complete schema-2 publication. No physical media was written and no hardware acceptance is claimed.
