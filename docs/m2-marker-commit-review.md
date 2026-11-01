# M2 final marker commit review

2026-11-01. **D23 approved by the user.** Implementation and verification are tracked separately. This is a narrow refinement of D15's final-drain evidence, not permission to claim a successful firmware clock or physical boot.

## Problem and recommendation

The existing schema-2 output contract requires RUSTOS_BOOT_OK for normal and RUSTOS_EXPECTED_PANIC for panic-test. The current engineering lines are not acceptance tokens. A panic artifact must never emit the normal pass token: the marker classifier treats the opposite token as contradictory.

The current controlled drain-failure test demonstrates that a complete engineering line can already be on the wire when the final BUSY poll subsequently fails. Simply renaming that line to a pass token would create a false-pass opportunity for a one-way serial observer. An extra completion token followed by another mandatory drain would repeat the same observability problem.

Recommend a deliberately defined commit boundary:

1. Complete mandatory boot checks, valid measured clock, UART initialization and all ordinary diagnostic writes/drains. For panic-test, enter the explicit fatal routine with the initialized console before committing its token.
2. Write the selected token **without its newline**. Perform a bounded drain. Any TX/drain failure parks with an unterminated prefix, which cannot satisfy exact-line verification.
3. Enqueue exactly one LF using bounded TX-space polling. If enqueue fails, no complete token exists. On success, perform the required MMIO ordering and immediately enter the already reviewed stackless terminal park. Perform no later fallible work or status poll that could retroactively invalidate the token.
4. The host accepts only the complete LF-terminated exact token within the capture deadline. Receipt of that last byte is the evidence that the final commit byte reached the wire; it is not represented as an observed firmware BUSY-clear read after the LF.

This intentionally replaces a software final-drain check after the final LF with host-observed final-byte delivery. It preserves bounded software polling and requires all earlier drains to succeed. It is a change in how the last-byte drain is evidenced and therefore needs explicit D23 approval. If the user requires a separate device-side BUSY-clear observation after the LF, the existing single TX wire cannot independently prove it; additional acknowledgement/observability design would be required instead. No such hardware requirement is introduced here.

## Variant and failure semantics

Normal emits only RUSTOS_BOOT_OK as its final token. Panic-test emits only RUSTOS_EXPECTED_PANIC, after entering the deliberate fatal diagnostic path. Both may emit clearly nonaccepting diagnostic lines first. Never emit the other variant's token. Unexpected Rust panics and CPU faults remain failure/silence; the pre-BSS panic path must not consult global readiness state. The intentional panic test is the explicit kernel fatal routine, not evidence that the Rust panic handler prints diagnostics.

No complete token may precede the last fallible operation. Partial lines, contradictory tokens, malformed output, disconnected capture and deadline expiry remain failures. Real firmware clock rejection must remain a failure before token construction; no QEMU requested-rate fallback is added. Normal/panic artifact identities remain distinct and bound to their feature sets.

Required controlled cases: both variant tokens; diagnostic drain failure; token-prefix TX/drain failure with no LF; final-LF enqueue failure; wrong variant/contradictory token rejection; exact full/partial lines; commit-to-park disassembly with no later fallible operation; and linked stack rechecks. Synthetic measured-rate tests remain explicitly separate from unmodified QEMU and physical capture.

## First review: contracts and classifier

Read D15/D18 and the actual [output validator](../tools/m2_output_contracts.py), [marker classifier](../tools/assembler/src/verify.rs) and current Pi kernel. The validator already binds variants to the two token texts. The classifier requires complete exact lines and rejects the opposite/fault token. No new token text or M1 change is needed. D15 requires final drain failure to prevent pass; the proposed split token addresses every software drain failure before the final commit byte, while explicitly changing last-byte evidence to host reception.

## Second review: observed failure and implementation boundary

The [controlled serial evidence](evidence/p7-console-full-stack-controlled.json) includes a complete ready line followed by normal failure stage 7, and complete startup/panic lines followed by panic drain failure stage 9. Thus complete output does not establish a later BUSY-poll result. Reviewed the proposed split-token paths against bounded Pl011 writes: a write error occurs before the corresponding byte is enqueued; token-prefix drain failure prevents LF enqueue. After LF, an unconditional terminal branch leaves no later software check that could contradict the commit. Physical serial capture still cannot attest arbitrary future OS behavior or the actual flashed SD bytes; existing operator-binding limitations remain.

Both review passes are self-review. The proposal is ready for confirmation, then implementation/testing. M1 and approved asset-lock bytes remain unchanged.

## Assembler integration checkpoint

Corrected the existing pending-backend diagnostic: standalone Pi entry/console now exists, while assembler snapshot build, Pi image packaging and image/hardware verification integration remain pending. The backend gate remains active; 33 current Rust assembler tests pass.

Before removing that gate, introduce a typed Pi target path rather than passing a Pi profile through the QEMU-only prepared state; snapshot the actual Pi kernel/BSP/common driver sources and target-specific build inputs; bind normal/panic features and exclude entry-only artifacts; produce both ELF/flat/image roles with exact relationships; check the immutable firmware lock; independently inspect both images; and publish only a complete schema-2 bundle. A standalone kernel ELF is not a successful assembler bundle.

The selected catalog's logical kernel module currently points at the M1 kernel source while the Pi entry is a separate kernel target. Its source/provenance mapping must be explicitly reconciled during integration: do not claim M1 code built the Pi binary or enable a partial Pi backend to bypass this gap. Physical capture remains a separate explicit operation.
