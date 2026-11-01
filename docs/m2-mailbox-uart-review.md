# M2 mailbox and UART initialization review

2026-11-01. **D22 approved by the user.** D15 approved PL011 TX diagnostics, but its [console contract](m2-console-contract.md) leaves exact mailbox transport as a prerequisite review. This proposal specifies that transport and initialization. It does not change firmware assets or authorize physical media operations.

## Proposed ownership and transport

After full DTB validation and BSS initialization, only the primary EL1 core may initialize UART. Keep MMU/caches off and interrupts masked. Use the Zero 2 W constants: mailbox base 0x3f00b880, GPIO 0x3f200000, PL011 0x3f201000 and the 1 MHz system timer CLO at 0x3f003004. Verify the final linked layout stays inside the proven kernel budget.

Use three dedicated, 64-byte aligned, 64-byte BSS mailbox buffers, one each for clock enable, rate setting and measured-rate query. They remain allocated for the complete boot; never use a stack buffer or return its memory to an allocator. Each buffer is submitted at most once. On any malformed response or timeout, mark initialization failed and park without retries or buffer reuse. A late firmware write then remains confined to its dedicated allocation. Rust must not retain ordinary references while firmware owns the memory; use explicit raw-pointer volatile accesses and exclusive single-core ownership.

Check the whole buffer physical extent inside the validated kernel/BSS reservation and below the BCM2837 DMA-window limit. Convert to the documented coherent GPU bus alias as `physical | 0xc0000000`, after checked address/alignment/range validation. The pinned BCM2837 DTS maps that bus window to ARM physical RAM; this is a board-specific translation, not a generic ARM rule.

Property channel is 8; submit `bus_address | 8`. Read mailbox0 data at base+0x00 and status at +0x18 (EMPTY bit 30). Check mailbox1 status at +0x38 (FULL bit 31) before writing at +0x20. Require exact response-word correlation, including channel and address. Consume unrelated words within the global transaction budget without treating them as completion. Before submission, drain stale receive words within that budget. No interrupts or concurrent mailbox clients are introduced.

Use ordered 32-bit volatile MMIO. Finish request-buffer stores with DSB SY before the mailbox write; after matching completion, DSB SY before volatile response loads. Place barriers around changes between peripheral blocks. Each transaction has a one-second timer deadline using wrapping u32 elapsed arithmetic and an independent 1,000,000-iteration cap; progress never resets the deadline/cap. A stuck timer or permanently busy FIFO therefore still fails. These are policy limits, not promised service latency.

## Clock messages and validation

Each request contains one tag, little-endian words, exact total byte size, request status zero and an end tag. UART clock ID is 2. Use:

| Operation | Tag | Value capacity/request bytes | Expected response bytes |
| --- | --- | --- | --- |
| Enable UART clock | 0x00038001 | 8 / 8: ID 2, state 1 | 8: ID 2, state exactly 1 |
| Request 48 MHz | 0x00038002 | 12 / 12: ID 2, 48000000, skip-turbo 1 | 8: ID 2, positive supported rate |
| Read measured UART rate | 0x00030047 | 8 / 4: ID 2, zero padding | 8: ID 2, positive measured rate |

The set-rate request is 36 bytes total; the other two messages are 32 bytes. Buffers are 64 bytes each, but total-size fields describe only the message. Validate the unchanged total size, global success 0x80000000, exact tag identity and capacity, response flag and exact eight-byte response length, clock identity, accepted value and end tag before reading semantics. Reject unsupported/missing tags, extra layout, truncation, overlong response lengths or firmware error. Strict rejection is intentional M2 policy even though the protocol allows forward extensions. Unused response-capacity bytes are not interpreted.

The ordinary Get Clock Rate tag reports the next requested enable rate; it is not substituted for the measured tag. Compute divisors from the measured positive rate, require representability and at most 1% baud error at 115200. Do not assume measured rate equals the 48 MHz request. No fallback to hard-coded divisors is allowed when measured-rate support is missing. Actual pinned-firmware support remains a physical/emulator compatibility test, not established by documentation.

## GPIO and PL011 order

First boundedly drain inherited UART transmission; disable UART, DMA and UART interrupts; confirm idle again. Only then change routing or clock. Detach the known Bluetooth UART route by setting GPIO30-33 to inputs; keep GPIO15 input because M2 has no receiver. Do not initialize Bluetooth or apply Linux alias assumptions. GPIO14 alone is routed to ALT0 TXD0 using a read-modify-write that preserves unrelated function fields.

Disable pulls on the selected diagnostic pin with the BCM2835 GPPUD/GPPUDCLK sequence, using timer-based 150 microsecond setup and hold delays, each with an independent iteration bound. This deliberately exceeds the manual's 150-cycle minimum; it is policy, not an assertion that CPU cycles equal peripheral cycles. Clear the pull clock afterward. Reject unsupported timer behavior. Complete the clock exchanges while PL011 remains disabled, then program divisors, clear/mask interrupts, disable DMA, select 8N1/FIFO and enable UART+TX only (no RX/RTS/CTS). Reuse the polling console only after board preparation succeeds. Preserve unrelated GPIO settings except the explicitly owned diagnostic/Bluetooth UART pins.

Every TX poll and final drain is bounded. A preparation failure prevents marker transmission; a later formatting/transmit or drain failure prevents successful acceptance even if some bytes have already reached the wire. Before console-ready, failures park silently; panic before readiness never attempts mailbox/GPIO setup. After readiness, panic uses only the already initialized bounded transmitter, with no recursive initialization.

## Review pass 1: primary sources

The [official mailbox protocol](https://github.com/raspberrypi/firmware/wiki/Mailbox-property-interface) defines aligned in-place messages, clock ID/tags and the distinction between requested and measured rate. Its snapshot is hashed in the [retained manifest](../out/research/pi-uart-review/sources.json); it is a rolling document, not a proof of the pinned binary's behavior.

The [BCM2835 peripheral manual](https://datasheets.raspberrypi.com/bcm2835/bcm2835-peripherals.pdf) provides register offsets, GPIO routing/pull protocol, PL011 busy semantics and peripheral ordering guidance. The old BCM2835 CPU peripheral base is not reused. Pinned BCM2837 DTS supplies 0x3f000000 translation and the 0xc0000000 DMA alias; the Zero 2 W DTS identifies UART0 GPIO30-33 as the Bluetooth route. Selected files were extracted from the already locked Linux source archive at commit 9b488bc7a1e9b61713082f3e6c4361988d62f77b, not copied into RustOS implementation.

## Review pass 2: implementation and failure cases

The pinned Linux mailbox controller independently confirms mailbox0 receive and mailbox1 transmit status offsets and FULL/EMPTY bits. The firmware service uses aligned DMA storage and memory barriers. Its allocation/timeout behavior is not adopted as RustOS ownership policy: dedicated lifetime-long buffers avoid returning storage while firmware could still write.

Compared with the current polling driver: its initial wait occurs before disabling UART, matching the required initial drain, but board preparation must also mask DMA/interrupts and prove idle before reconfiguration. No shared M1 driver change is assumed by this proposal. Recomputed the 48 MHz example: divisor units round(48000000*4/115200)=1667, IBRD=26, FBRD=3, approximately 0.02% error. A valid divisor alone does not prove the measured clock or wire output.

Required implementation evidence: pure parser/address/divisor tests; mock-MMIO traces for exact order, wrong-channel/address, FIFO-full, malformed/unsupported replies, timeout, late completion without reuse, and no success after drain failure; linked stack/write-order rechecks after integration; physical clock/baud/startup/panic capture on the identified board. QEMU may not implement every property tag: report that failure explicitly rather than silently changing clock policy.

Both passes are self-review. D22 approval would permit implementation and emulator/mock verification of this precise baseline; M2 remains incomplete until packaging and physical acceptance.
