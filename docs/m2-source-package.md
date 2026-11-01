# M2 local source/asset package checkpoint

Current update: the [DTB reproduction](m2-dtb-reproduction.md) has now passed twice with exact bytes. Earlier prerequisite/reproduction gaps below describe the preceding checkpoint; final source/notice binding in the production asset lock remains open.

2026-11-01. The [research package](../out/research/m2-source-9b488bc7a1e9/README.md) now retains the full pinned Linux source archive, source and include-closure manifests, notices and six real boot assets/notices. It contains no RustOS image.

Evidence: [archive identity](evidence/m2-source-archive.json), [source closure](evidence/m2-dtb-source-closure.json), [retained boot assets](evidence/m2-local-boot-assets.json).

Two checks completed: archive hash read twice and required source/build/notice members inspected; then the board source was compared with the separately fetched pinned source and its 21 transitive include files resolved within the archive. Real boot bytes were refetched, compared with prior hashes and rehashed after retention. No whole-tree extraction or host installation was performed.

The archive is 257,653,039 bytes with 98,133 members. It includes the complete upstream source rather than just the top-level DTS. The source-package instructions follow official AArch64 Pi build guidance, with the actual pinned preprocessing/dtc scripts also inspected. Those instructions remain unexecuted.

Local prerequisites: clang/gcc, make and dtc were not found on PATH; Docker CLI exists, but its Linux engine is not running. This prevents the proposed local reproduction path from running now. It does not establish a missing Rust toolchain or invalidate M1.

Next: prepare a suitable isolated DTB build environment, reproduce/compare the DTB and capture tool/config/command identities. Then bind source archive, build instructions and all notices into the final asset lock. A matching source hint and complete archive do not alone prove that the supplied binary DTB was built from them.

Reference: [official Raspberry Pi Linux build guidance](https://www.raspberrypi.com/documentation/computers/linux_kernel.html). This is supporting work for a reused DTB, not a change to the agreed RustOS-only kernel goal.
