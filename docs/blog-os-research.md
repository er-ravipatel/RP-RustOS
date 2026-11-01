# Phil Opp blog_os research

2026-11-01. Read-only review of [Writing an OS in Rust](https://os.phil-opp.com/), the [upstream repository](https://github.com/phil-opp/blog_os), and the supplied local root `E:/Work/blog_os-main/blog_os-main`. No tutorial build, installer or disk-writing command was run. No upstream code was incorporated into RustOS.

## Source scope

The local main-branch snapshot contains the blog/site source and embedded code examples. Its README explains that runnable kernels are on separate `post-XX` branches; the second edition's latest listed branch is `post-12`. Its local revision is unverified because no Git metadata was established. The first edition is explicitly described as outdated and unmaintained.

To inspect executable source rather than infer from prose, selected files from `post-12` were retrieved at immutable commit `cc04789ff4afb1878ec9190373924282c6b95c81`. The [source manifest](../out/research/blog-os-reference/sources.json) retains URLs and SHA-256 hashes. It is a focused selection, not a complete dependency closure or a demonstrated reproducible build. The selected revision's Cargo metadata and dependency APIs must not be assumed to work with RustOS's current toolchain unchanged.

## Relevant patterns

| Pattern | Inspected evidence | RustOS application and boundary |
| --- | --- | --- |
| Small testable kernel increments | Chapter branches and tutorial progression | Organize feature work around executable outcomes, negative tests and evidence. Supports our milestone/dashboard approach; a tutorial chapter is not an acceptance result. |
| no_std test harness | `src/lib.rs`, Cargo metadata | Separate test entry, named serial results and explicit failure path. Keep our AArch64 host/QMP runner; x86 ISA debug-exit port 0xf4 and exit code 33 are not portable to Pi. |
| Deliberate panic and stack-fault binaries | `tests/should_panic.rs`, `tests/stack_overflow.rs` | Expected-failure scenarios must have dedicated success rules. Unexpected continuation must fail. x86 double-fault/IST mechanisms cannot be copied into AArch64 vectors. |
| Explicit memory ownership | `src/memory.rs` BootInfoFrameAllocator | Allocate only truly unused frames from a validated map. RustOS must subtract firmware, kernel, DTB, static reservations and CMA before a future allocator. Raw `/memory/reg` is not an allocator-ready free list. |
| Unsafe contracts at mapping boundaries | `src/memory.rs` OffsetPageTable initialization | Document uniqueness/aliasing and physical mapping assumptions at unsafe APIs. x86 CR3 and four-level paging types require AArch64 replacements. |
| Heap before collection-based services | `src/allocator.rs` | Clear initialization dependency: valid RAM → frame ownership → mappings → heap → allocation-using services. Heap and paging remain later milestones; M2 preflight stays allocation-free. |
| Interrupt-to-task event queue | `src/task/keyboard.rs` | Queue small events and defer work; register a waker then recheck the queue to avoid a lost wakeup. Hardware scancodes/PS2 are not Pi USB keyboard support. Review queue overflow and logging policy for our kernel. |
| Ready-task executor | `src/task/executor.rs` | Future cooperative tasks and cached wakers can support shell/device work. Queue overflow currently panics in the example; production RustOS needs explicit capacity/backpressure rules. Its x86 enable-and-halt idle operation needs an architecture-specific replacement. |

The frame allocator repeatedly constructs its usable-frame iterator and uses `nth(next)`; it is simple instructional code, not a scalability recommendation. Its safety contract assumes the boot map already excludes occupied frames. Similarly, the executor is cooperative: it provides neither process isolation nor preemptive scheduling. The keyboard example's diagnostic printing should not be treated as a proof that every interrupt path is nonblocking.

## Fit for the Pi startup work

The tutorials target x86_64 with a bootloader-supplied BootInfo and prepared execution environment. VGA text memory, 16550 serial, 8259 PIC, GDT/IDT/IST, x86 I/O ports and page-table registers do not solve Zero 2 W GPIO/PL011, ARM exception levels or DTB handoff. No Zero 2 W/Pi 5 compatibility was established. The bootloader's preparation also does not solve our first safe stack problem; retain D16/D20 and the [stackless entry checkpoint](p7-stackless-entry-design.md).

Immediate use: improve review/test design and make preconditions explicit. Later use: allocator designs, frame ownership, event queues and cooperative executors, adapted behind our hardware interfaces. Do not add heap, interrupts or scheduling to M2 just to follow tutorial order.

## Licensing and review

The inspected `post-12` README offers MIT or Apache-2.0 at the recipient's option, and warns that this statement applies to that branch; other branches may differ. Selected licence files were retained. Check the exact component/version before reuse and preserve the required notices. Do not assume the code's licence automatically covers all website prose, artwork or dependencies.

First review pass followed the local README and tutorial material, then inspected pinned test, memory, allocator and executor source. Second pass checked architecture/boot assumptions, queue/allocator limitations, licence scope and dependencies against current RustOS milestones. Both are self-review; no upstream runtime validation, security audit or source-porting claim is made.

## Primary references

- [Testing](https://os.phil-opp.com/testing/).
- [Paging implementation](https://os.phil-opp.com/paging-implementation/).
- [Allocator designs](https://os.phil-opp.com/allocator-designs/).
- [Async/await](https://os.phil-opp.com/async-await/).
- [Pinned runnable source](https://github.com/phil-opp/blog_os/tree/cc04789ff4afb1878ec9190373924282c6b95c81).

Together: Redox informs the larger OS/assembler architecture, Ventoy informs boot-media tooling, and blog_os supplies incremental kernel-learning and testing patterns. They are complementary references, not interchangeable boot implementations.
