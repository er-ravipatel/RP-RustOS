# P7 combined preflight audit checkpoint

2026-11-01. Two self-review passes over the combined test prototype: semantic comparison against the Rust validator, then register/control-flow and first-write assumptions. This is not independent review, formal verification or production entry acceptance. [Assembly](../tools/entry-harness/handoff.S).

## Reproduced and corrected semantic gap

With one valid memory bank present, a second root node named `ram@0` declaring exact `device_type="memory"` was ignored by assembly while the Rust validator returned `Node`. A new shared fixture reproduced that false policy acceptance before the change. The RAM pass now checks the device_type property of otherwise unrecognized root children and rejects this case. An unrelated root device type remains accepted. The successful suite has 26 cases; the earlier failing case is retained as diagnostic evidence, not acceptance.

The narrow assembly subset can additionally reject a disabled misnamed memory node that Rust would skip. That conservative difference does not permit unsafe memory. Multiple banks/active reservation children and unsupported static variants also remain explicit conservative limits. Dynamic shape validation is not pool placement, and a shape-valid no-space request still fails in Rust. None of these test-stage success markers can be reused as complete boot success.

## Phase register ownership reviewed

| Registers | Earlier phase | Later reuse and constraint |
| --- | --- | --- |
| x0 | Original handoff pointer | Remains unchanged; copied to result register only at test success |
| x19/x20 | DTB base/checked complete end | Retained through all semantic phases |
| x21 | Structure start | Retained for later tree rescans |
| x22 | Structure end | Becomes reservation-parent flags only after complete structure/root validation no longer needs the end |
| x23 | Strings base | Retained for checked property-name lookup |
| x24 | Strings end | Becomes semantic node class after the full structure pass |
| x25–x28 | Record/token counts, depth, root state, cursors | Reinitialized as semantic depth/cursor/value metadata before reuse |
| x29 | Current node property-region start | Replaced by checked root address-cell count after duplicate validation |
| x30 | Current property token address during rescan | Replaced by checked root size-cell count; no BL or ABI call is permitted here |
| x8 | Child-seen mask, then root required flags | Reinitialized as active RAM result before semantic traversal |
| x14–x17 | Rescan budget and property scratch | Reinitialized as current node flags/status/reg-or-size extent |
| x11/x13 | Observed CurrentEL/SCTLR | Retained for harness assertions, not a production boot-information ABI |
| x18, SP | Unused by the inspected prototype | No implicit scratch stack/platform-register assumption |

Fault entry overwrites diagnostic registers and never returns. Every helper is inline/branch based; compiler-generated Rust prologues are outside the preflight ELF's inspected assembly extent. Name comparisons and semantic skips rely on the earlier complete structure pass; they are not stand-alone raw-pointer parsers. That dependency must remain explicit when separating production files.

## Remaining first-write gates

- Review exact Cortex-A53 production control-register values/barriers and the full MPIDR affinity policy. Current masks and low-byte affinity are test-adapter behavior.
- Build first-write observation with an exact approved stack interval, linker assertions and debugger/write tracing. Keep negative fixtures from reaching any store, rather than inferring this from a marker or source scan.
- Specify the pre-BSS Rust validator ABI, panic behavior and generated helper/stack requirements. It must not touch globals, UART or an allocator before those are initialized.
- Keep the DTB readable and stable across rescans under the firmware handoff assumptions. No proof of DMA quiescence, external-master behavior or DTB authenticity follows from QEMU tests.
- Reconcile the narrow bank/child limits and unsupported variants with observed physical firmware data; the artificial 128 MiB update is not that evidence.

No first stack write, BSS clear, production CPU transition or physical Pi boot was added. The asset lock and accepted M1 implementation are unchanged. Next: prepare the exact write-observation harness and production register review, with failures still parking before writes.

After the correction all five suites pass: [26 RAM](evidence/p7-entry-audit-ram.json), [four full-tree models](evidence/p7-entry-audit-pinned.json), [18 static](evidence/p7-entry-audit-static.json), [19 CMA](evidence/p7-entry-audit-cma.json) and [58 entry/structure](evidence/p7-entry-audit-entry.json). The [original failing node fixture](evidence/p7-entry-audit-node-discovery.json) is retained separately as diagnostic evidence.
