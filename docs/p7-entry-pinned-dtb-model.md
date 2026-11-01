# P7 full pinned-DTB handoff model

2026-11-01. Tested the complete pinned Zero 2 W DTB against the combined header/map/structure/root/RAM/static/CMA-shape prototype and the host Rust checker. [Runner](../tools/test_entry_pinned_dtb.py), [retained evidence](evidence/p7-entry-pinned-dtb-model.json).

The runner requires the exact pinned SHA-256 `5b31bc70011e454f482ba323b1eca22bf54fa2fa4682576ee73816a2eccfa277`, identifies the single eight-byte zero placeholder at `/memory@0/reg`, and generates separate target-directory fixtures. It checks that no bytes outside that property's value changed and that the original cached asset remains byte-for-byte unchanged after execution. No test fixture replaces the locked DTB or enters a production image.

| Complete-tree fixture | Emulator preflight | Full host Rust validator |
| --- | --- | --- |
| Unchanged pinned DTB | Reject | Reject zero-sized RAM |
| Simulated 128 MiB RAM update | Accept this test stage | Accept; reserve 64 MiB CMA at 0x4000000 |
| Simulated RAM ending inside kernel budget | Reject | Reject kernel containment |
| Simulated 32 MiB RAM update | Accept RAM and request shape | Reject because a 64 MiB CMA pool cannot fit |

All four cases passed their explicit expectations, including exact emulator markers/park addresses, CPU state, instruction inspection and vector checks. The final row intentionally demonstrates deferred pool selection rather than agreement on complete boot readiness. No stage marker is production boot success. The Rust checker must reject impossible allocation before later boot services.

Unlike the small synthetic fixtures, these cases retain the full board tree, symbols, aliases and existing reservation metadata. The 128 MiB value is an artificial conservative test input, not a measurement or prediction of Pi firmware's RAM report. Firmware itself was not run. Physical handoff, DTB authenticity, first stack writes, production CPU masks/full affinity, runtime write tracing, kernel/console wiring and hardware acceptance remain unverified.

The approved asset lock and its bound inputs were rechecked successfully: six boot assets, one source package and both DTB reproduction records. The initial validation command lacked the optional jsonschema module; using the existing isolated validation dependencies completed the check without downloading or changing assets. The lock identity remains `537d7d3b991369db5ec4bb3475ddf37b41dd2217b56b53e44d69c163b356e850`.

Next: audit the combined prototype's safety contract and phase register ownership, identify malformed semantic cases that still bypass the intended policy, and design explicit first-write observation before integrating it with a safe stack. A successful simulated tree does not close those gates. M1 is unchanged; M2/P7 remain in progress.
