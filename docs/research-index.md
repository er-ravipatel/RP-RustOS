# Research references

Use this index before revisiting external OS/build/boot designs. These are recorded research findings, not implemented features or changes to the approved RustOS architecture.

| Reference | Saved analysis | Useful for | Important boundary |
| --- | --- | --- | --- |
| Redox OS build system | [Assembler analysis](redox-research.md) | Architecture/board/product profiles, recipes, staging, image publication | Supplied local checkout contains the builder; kernel and core drivers are separate projects. |
| Redox kernel and bootloader | [Pinned boot-source review](redox-boot-research.md) | Boot arguments, memory ownership, AArch64 entry, early diagnostics | Reviewed UEFI loader assumptions do not solve RustOS's direct Pi first-stack safety. |
| Ventoy | [Source and feature assessment](ventoy-research.md) | Configuration handlers, image catalogs, verification, future multiboot/persistence | ARM64 UEFI differs from direct Pi firmware; GPLv3+ and component licences require review before code reuse. |
| Phil Opp blog_os | [Tutorial and pinned-code review](blog-os-research.md) | Kernel tests, memory ownership, allocators, later event queues/executor | x86_64 boot/interrupt/paging details require ARM replacements; supplied main branch is site source, executable chapters use separate branches. |

## Retained evidence

- Redox local build-system source supplied by the user: `E:/Work/redox-master/redox-master`. Its commit identity was unavailable; the report identifies this limitation.
- [Redox selected-source manifest](../out/research/redox-reference/sources.json): pinned kernel/bootloader commits, source URLs and SHA-256 hashes.
- [Ventoy selected-source manifest](../out/research/ventoy-reference/sources.json): pinned source commit, URLs and SHA-256 hashes.
- [blog_os selected-source manifest](../out/research/blog-os-reference/sources.json): pinned post-12 commit, URLs and SHA-256 hashes; local site source supplied at `E:/Work/blog_os-main/blog_os-main`.

The manifests and downloaded source files are local research cache material. If a cache is unavailable, use the immutable upstream links and commit identities retained in the reports. No upstream source was incorporated into RustOS by these reviews.

## Carry forward

Apply the assembler/profile/staging and verification ideas within existing requirements. Keep later multiboot, persistence, driver services and microkernel choices as future design inputs. Neither reference establishes Zero 2 W or Pi 5 hardware compatibility. D20 was approved separately; its implementation and startup verification remain tracked under P7. Research completion does not establish implementation completion.

Add future reviews here with their scope, source revision, evidence limits and RustOS relevance. The dashboard planning register links these reports as research evidence.
