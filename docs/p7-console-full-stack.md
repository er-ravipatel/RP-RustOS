# P7 full console stack and panic failure review

2026-11-01. This closes the linked post-BSS stack audit for the two exact reviewed normal/panic-test ELFs. M2 physical acceptance is still pending.

## Linked stack results

| Exact artifact | Pre-BSS validator including caller | Post-BSS console including deliberate diagnostic paths | Maximum boot phase |
| --- | --- | --- | --- |
| [Normal report](evidence/p7-console-full-stack-normal.json) | 21,440 bytes | 464 bytes | 21,440 bytes |
| [Panic-test report](evidence/p7-console-full-stack-panic.json) | 21,440 bytes | 464 bytes | 21,440 bytes |

The phases share the 65,536-byte private stack sequentially. The [analyzer](../tools/check_entry_stack.py) verifies the validator caller restores its 48-byte frame, then checks the assembly window up to the console dispatch contains no extra stack adjustment/call and that dispatch branches directly to the console root. The phase bounds are therefore compared rather than added.

Each ready/failure/panic terminal accepted by the audit is verified in the actual ELF as exact stackless WFE/branch bytes. All other unknown exits, indirect calls, recursion, inconsistent depth, unbalanced returns and stack-changing cycles still reject. The analyzer follows all direct reachable helper/error edges from the console root, including deliberate-panic paths in the panic-test artifact. It does not skip those paths based on the observed QEMU clock rejection.

First review checked the complete reachable call graph and distinct phase entry stack depths. Second review checked terminal byte validation, direct assembly dispatch and retained fail-closed rules. Five [analyzer test methods](../tools/test_entry_stack_checker.py) pass, including explicit multiple-terminal acceptance and unknown-terminal rejection. Both reviews are self-review, not independent formal verification. Bounds are specific to the hashed artifacts and this instruction model, not future builds, pointer safety, asynchronous exception stacks or physical firmware.

## Six controlled runtime cases

[All six cases pass](evidence/p7-console-full-stack-controlled.json): normal ready, normal TX timeout, normal drain timeout, deliberate-panic output, panic TX timeout and panic drain timeout. The last two let the first startup driver call return before injecting the fault into the second call from the deliberate-panic routine. Startup therefore completes before the panic-specific fault.

Panic TX failure emits only the startup line, then reaches failure stage 8. Panic drain failure emits startup and deliberate-panic lines, then reaches failure stage 9. Neither reaches the deliberate-panic success terminal or retries console/mailbox setup. Complete bytes alone cannot establish successful drain. Every case checks exact terminal PC, marker, output bytes and SP inside budget.

As before, these tests explicitly synthesize a valid completed measured-rate snapshot and, for fault cases, redirect the UART object to RAM-backed stuck status registers. They do not establish firmware support or real UART fault behavior. The deliberate-panic routine uses an explicitly initialized console; ordinary Rust panics remain silent so pre-BSS code never reads readiness globals.

## Regressions and next work

The [unmodified default run](evidence/p7-console-full-stack-unmodified.json) still stops at stage 4 because QEMU's measured-rate response is incomplete, with no serial bytes. [Five explicit entry-only cases](evidence/p7-console-full-stack-entry.json) still pass multicore/BSS checks.

Next finalize variant-specific acceptance markers and fail-reporting semantics, then integrate the Pi build/output into the assembler and image inspection pipeline. Physical firmware clock support and Zero 2 W startup/panic capture remain pending. No image was flashed and no M1 or approved firmware-lock bytes changed.
