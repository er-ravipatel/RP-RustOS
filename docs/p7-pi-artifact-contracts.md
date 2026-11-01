# P7 exact compiler-output layout and stack contracts

2026-11-01. [check_pi_artifacts.py](../tools/check_pi_artifacts.py) validates the exact ELF paths and SHA-256 recorded by the internal Pi compiler. It requires the normal/no-extra-feature and panic-test/panic-test feature identities, then checks ELF64 little-endian AArch64 executable headers, entry 0x200000, bounded header tables, load extents within [0x200000,0x3f0000), matching virtual/physical addresses, non-overlapping load segments, alignment and W^X. Linked stack boundaries must be [0x3f0000,0x400000); aligned BSS and the complete 192-byte, 64-byte-aligned permanent clock buffers must fit below the stack.

It invokes the existing conservative stack analyzer against each same-hash output, including the post-BSS console path. [Results](evidence/p7-pi-artifact-contracts.json) show both variants pass with a 21,440-byte maximum bound inside 65,536 bytes. The exact caller frame, direct console dispatch, stackless terminal loops and final marker commit tail pass the analyzer's existing checks. Full disassembly and tool command details are retained in the evidence.

[Twenty negative cases](evidence/p7-pi-artifact-negative.json) reject altered machine, entry, table extents, writable executable loads, physical-address mismatch, oversized load and truncated headers across both variants. Five existing stack-analyzer regression tests also pass. No production Rust code changed in this slice.

First self-review checked exact compiler-report hashes, memory extents and permanent buffer placement. Second self-review checked negative mutations and conservative stack results for both feature variants.

This is an engineering validator, not a general untrusted-ELF security parser. Feature identity is read from the retained compiler report; this does not independently prove instruction-level variant semantics. Layout and stack analysis do not establish complete entry behavior, asynchronous-handler safety, firmware compatibility or physical boot. Exact-output entry behavior remains the next validation task, followed by flat kernel generation and complete image packaging. The public Pi backend remains gated.

```powershell
python tools/check_pi_artifacts.py --compiler-report target/pi-compiler-1793537607765823600/report.json --report target/pi-compiler-1793537607765823600/new-contracts.json
python tools/test_pi_artifact_contracts.py --compiler-report target/pi-compiler-1793537607765823600/report.json
```
