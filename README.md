# RustOS

A custom operating system written in Rust, designed for single-board computers, with Raspberry Pi Zero 2 W as the first hardware target.

The broader product goal is an **OS assembler**: select compatible RustOS components for a target and produce its bootable image. Initial scope is RustOS-only. Development starts with emulator verification, then Zero 2 W hardware and later Pi 5 support. See the [agreed product direction](./docs/product-direction.md) for the revised milestones; the detailed roadmap below remains an initial outline awaiting reconciliation.

**Status: M1 emulator milestone complete.** The Windows assembler supports `validate`/`plan`/`build`/`verify`, immutable ELF bundles, external reports and automatic dashboard ingestion. Profile 0.1.1 passes real startup/panic checks and the scoped cancellation/reporting/cleanup failure acceptance. See [M1 delivery and evidence](./docs/m1-acceptance.md). M2 Zero 2 W images and later OS features remain planned.

## Engineering Plan and Live Progress

See the [research reference index](./docs/research-index.md) for the saved Redox OS, Ventoy and Phil Opp blog_os analyses and their relevance to RustOS.

Build and verify the M1 bundle from the root configuration:

```powershell
cargo build --manifest-path tools/assembler/Cargo.toml --locked
tools/assembler/target/debug/rustos.exe build --repo . --config rustos.toml --format json
tools/assembler/target/debug/rustos.exe verify --repo . --manifest out/m1/manifest.json --format json
```

Build once into a fresh destination. Existing bundles are never overwritten; verify the delivered bundle directly or choose a new output path for another build. See [M1 prerequisites and reproduction](./docs/m1-acceptance.md).

Run the [kernel emulator checks](./docs/p4-verification.md) from this repository root:

```powershell
python tools/test_kernel.py --report target/p4/new-evidence.json
```

This builds and tests the minimal kernel directly; it does not produce an assembler release bundle or Raspberry Pi image.

The [assembler host tool](./tools/assembler/README.md) now implements `validate` and `plan`. Run from this repository root:

```powershell
cargo run --manifest-path tools/assembler/Cargo.toml --locked -- plan --repo . --config docs/examples/m1.toml
```

This inspects module metadata without building or booting an OS. See the [P3 verification evidence](./docs/p3-verification.md).

To assemble the M1 bundle on Windows, use a fresh configured output destination:

```powershell
cargo run --manifest-path tools/assembler/Cargo.toml --locked -- build --repo . --config docs/examples/m1.toml --format json
```

Output resolves relative to the configuration file and existing destinations are rejected. See [snapshot build behavior and evidence](./docs/p5-build-verification.md); a passing build does not imply production emulator verification.

Use the [documentation index](./docs/README.md), [delivery plan](./docs/plan.md), [architecture and workflow diagrams](./docs/architecture.md), and [feature specifications](./docs/features/README.md) to follow the proposed design. The [live progress dashboard](./docs/dashboard/README.md) tracks requirements, analysis, design, review, documentation, implementation, and verification using an explicit repository progress register. It refreshes recorded changes every five seconds while running locally.

## Purpose and Vision

RustOS aims to provide a small, understandable command-line operating system whose kernel, hardware interfaces, drivers, and user programs can evolve independently. The project provides a path to learning and implementing operating-system fundamentals while building a useful SBC environment.

The long-term aspiration is a CLI environment with capabilities comparable in scope to Raspberry Pi OS Lite. This is a development direction, not a claim of Linux compatibility, equivalent hardware support, or production readiness.

## Goals and Success Criteria

### Who This Project Is For

RustOS is intended for developers learning bare-metal Rust, operating-system design, and single-board computer bring-up. It is also a foundation for experimenting with small command-line applications and hardware control once the required drivers and userland exist.

The primary workflow is to build an image on a development computer, boot it on the target board, connect through a serial terminal, and interact with the system through its shell. This workflow is a goal; it is not available in the current scaffold.

### Expected User Experience

As development progresses, a user should be able to:

1. Follow a reproducible build procedure and prepare boot media.
2. Boot the board and see startup diagnostics on the serial console.
3. Reach a shell, discover supported commands, and run basic utilities.
4. Launch a user program and receive its output and completion status.
5. Read and write files on supported storage.
6. Run documented C and MicroPython examples when those runtimes are supported.

These are acceptance scenarios for future releases, not commands or features implemented today.

### Project Outcomes

| Goal | Evidence of success |
| --- | --- |
| Boot on Raspberry Pi Zero 2 W | A reproducible image boots and prints a startup message over a documented serial connection. |
| Establish a reliable kernel | Exceptions, allocation, interrupts, and scheduling have documented behavior and verification. |
| Run user programs | Init starts, programs use a defined syscall interface, and the shell launches and waits for them. |
| Provide a useful CLI | Users can enter commands, inspect files, and run basic utilities. |
| Support persistent storage | Files can be read and written and survive reboot. |
| Remain portable | Kernel services use hardware interfaces; board addresses and initialization stay in board-specific code. |
| Support language runtimes | C and MicroPython examples run after their ABI, memory, and filesystem requirements are met. |
| Make development reproducible | A fresh checkout can be built, tested, and booted using documented tools and commands. |

The first delivery target is a bootable kernel with serial output. Networking, additional boards, and language runtimes come later. A graphical desktop and broad Linux application compatibility are outside the initial scope.

### Scope Boundaries

| Area | Initial scope | Later or undecided |
| --- | --- | --- |
| Hardware | Raspberry Pi Zero 2 W and the peripherals needed for bring-up | Additional boards and wider peripheral coverage |
| Interaction | Serial diagnostics followed by a command-line shell | Graphical interfaces are outside the initial scope |
| Execution | A minimal kernel, followed by a defined user/kernel boundary | Multicore execution and advanced scheduling policies |
| Storage | An in-memory or static image for early programs | Persistent storage after a block driver and filesystem are selected |
| Compatibility | RustOS-specific interfaces documented as they are implemented | POSIX coverage, Linux binary compatibility, and existing application portability are not promised |
| Connectivity | No network requirement for the first boot | Networking feasibility and supported protocols |
| Readiness | Development and learning on a documented target | Production use requires reliability and security work beyond the initial milestones |

## Current State

The root [Cargo workspace](./Cargo.toml) now contains four implemented bare-metal crates: kernel, HAL, QEMU board support and console driver. A separate host assembler implements validate/plan/build. Other component directories remain planned. The [documentation and dashboard](./docs/README.md) distinguish the tested emulator startup slice from broader subsystem outlines.

The kernel cross-compiles and boots in the selected emulator, with normal/panic/fault evidence. M1 assembly and verification pass end to end. CI automation, hardware support and SD-card image packaging remain later work; M2 physical-board work has not started.

## Target Platform

| Item | Intended target |
| --- | --- |
| First board | Raspberry Pi Zero 2 W |
| Architecture | ARMv8-A, AArch64 |
| Initial interface | Serial console; UART selection, wiring, and settings remain to be documented |
| Deployment | Bootable board image; firmware requirements and image layout remain to be specified |
| Portability | Additional SBCs through hardware abstraction and separate board support packages |

Boot protocol, exception-level transitions, memory layout, interrupts, and supported peripherals require implementation decisions.

## Intended Architecture

```text
Userland: init, shell, utilities, future applications
                         |
          Runtime support and syscall interface
                         |
Kernel: memory, scheduling, filesystem, IPC, syscall dispatch
                         |
        Hardware abstraction and reusable drivers
                         |
       Board support: initialization and device wiring
                         |
             Raspberry Pi Zero 2 W hardware
```

This is a conceptual design, not an implemented dependency graph. Image-building and packaging tools run on the development host, outside the target OS.

### Project Structure

| Location | Intended responsibility |
| --- | --- |
| [core/kernel/](./core/kernel/) | Kernel entry, initialization, and subsystem integration |
| [core/mm/](./core/mm/) | Physical and virtual memory management and allocation |
| [core/sched/](./core/sched/) | Task lifecycle, scheduling, and context switching |
| [core/fs/](./core/fs/) | Filesystem interfaces and file access |
| [core/ipc/](./core/ipc/) | Interprocess communication |
| [core/syscall/](./core/syscall/) | User/kernel ABI and syscall dispatch |
| [hal/](./hal/) | Hardware-independent traits and contracts |
| [bsp/pi-zero-2w/](./bsp/pi-zero-2w/) | Board initialization, memory map, and device configuration |
| [drivers/block/](./drivers/block/) | Block-device access |
| [drivers/console/](./drivers/console/) | Console input and output |
| [drivers/gpio/](./drivers/gpio/) | GPIO access |
| [drivers/timer/](./drivers/timer/) | Hardware timing support |
| [userland/init/](./userland/init/) | First user process and user environment startup |
| [userland/shell/](./userland/shell/) | Command parsing and program execution |
| [userland/utils/](./userland/utils/) | Basic command-line utilities |
| [runtimes/crt/](./runtimes/crt/) | C program startup support |
| [runtimes/libc/](./runtimes/libc/) | A deliberately scoped C library interface |
| [runtimes/micropython/](./runtimes/micropython/) | Future MicroPython integration |
| [tools/image-builder/](./tools/image-builder/) | Host-side boot-image assembly |
| [tools/packager/](./tools/packager/) | Host-side packaging of programs and runtime assets |
| [docs/](./docs/) | Setup, design decisions, hardware notes, and verification procedures |

### Design Principles

- Keep board addresses and device configuration out of portable kernel services.
- Define small hardware interfaces with explicit ownership and error behavior.
- Use `no_std` for bare-metal components where required; separate host tools from target code.
- Isolate unsafe operations and document invariants for registers, memory access, and context switching.
- Establish process isolation, pointer validation, and resource ownership as userland is introduced.
- Build vertical slices with observable bootable behavior before expanding subsystem coverage.

These are proposed implementation principles. Crate dependencies, ABI, synchronization model, executable format, and filesystem format are not yet defined.

## Languages, Tooling, and Dependencies

Rust is the intended primary language, with Cargo managing the workspace. C and MicroPython are future runtime integration targets. No application framework is currently implemented.

The root manifest uses Cargo resolver `2`, abort-on-panic development and release profiles, and release optimization through LTO and one code-generation unit.

| Dependency | Version requirement | Intended role |
| --- | --- | --- |
| `bitflags` | `2.4` | Bitmask types |
| `spin` | `0.9` | Synchronization primitives |
| `volatile` | `0.5` | Volatile memory access |
| `once_cell` | `1.19`, default features disabled | One-time initialization |
| `aarch64-cpu` | `10.0` | AArch64 CPU operations |
| `tock-registers` | `0.9` | Typed register access |
| `fdt` | `0.4` | Flattened Device Tree parsing |
| `log` | `0.4`, default features disabled | Logging facade |

These shared declarations are planned dependency requirements, not evidence of usage. The minimal target crates currently use only local path dependencies. Root and host workspaces have their own lockfiles. Future integrations must verify target compatibility and features; the logging facade still needs an implementation if adopted.

## Development Roadmap

This original subsystem roadmap expresses dependencies, not delivery dates. Emulator build/boot diagnostics are now demonstrated in P4; physical-board boot and later services remain planned. The current P1?P5 delivery queue in the dashboard governs M1 completion.

| Milestone | Deliverable | Completion criteria |
| --- | --- | --- |
| 1. Build foundation | Initial crates, toolchain and target selection, linker layout, build instructions | The initial kernel cross-compiles from a fresh checkout using documented commands. |
| 2. First boot | Board entry, stack setup, serial output, panic path | An image boots on the board, prints an identifiable banner, and reports a deliberate panic. |
| 3. Kernel essentials | Exceptions, memory initialization, timer interrupts | Exceptions produce diagnostics; allocation and periodic interrupts pass defined checks. |
| 4. Task execution | Context switching and initial scheduling policy | Multiple tasks make progress with verified stack and state handling. |
| 5. Userland boundary | User address spaces, executable loading, syscalls, init | Init runs in user mode; invalid user accesses are handled without corrupting the kernel. |
| 6. Interactive environment | Console input, shell, initial utilities | Users can enter commands and launch programs with observable completion behavior. |
| 7. Persistent files | Block driver and selected filesystem | Files can be created, read, and recovered after reboot. |
| 8. Runtime expansion | Defined C support and MicroPython integration | Documented example programs execute using supported runtime interfaces. |
| 9. Portability and services | Second-board bring-up and evaluated networking support | Another board reuses kernel services through defined hardware interfaces. |

An in-memory filesystem or static program image can support early userland work before persistent storage is available.

## Getting Started

Use the installed AArch64 soft-float target and QEMU environment described in the [P4 verification record](./docs/p4-verification.md).

```powershell
cargo build --locked -p rustos-kernel --release --target aarch64-unknown-none-softfloat
python tools/test_kernel.py --report target/p4/new-evidence.json
```

The development harness builds and checks normal, expected-panic and negative-test variants. Choose a new evidence filename for each run. This does not package an SD-card image or use a production assembler verification backend.

### Next Deliverable: Assembler Integration

P5 connects the existing configuration resolver and kernel to build/package/verify commands, immutable manifests, safe output publication, owned process-tree cleanup and dashboard report ingestion. Physical Zero 2 W images follow after M1's end-to-end emulator delivery. See the [current priorities](./docs/priorities.md).

## Verification Strategy

Planned checks include:

- Host tests for portable allocators, parsers, queues, and filesystem logic where feasible.
- Bare-metal cross-compilation and separate native checks for host tools.
- Formatting and lint checks once buildable packages exist.
- Boot smoke tests with serial output and explicit success or failure markers.
- Hardware checks for peripheral behavior, timing, and image compatibility.
- Negative tests for invalid user pointers, faults, and resource exhaustion as isolation is introduced.

The [P4 kernel harness](./tools/test_kernel.py) records actual emulator evidence; the host inspector, schema and dashboard suites validate their respective scopes. M1 interruption/reporting failure acceptance is complete; hardware checks remain M2. Each milestone records its exact procedure and tested environment.

## Open Design Decisions

- Boot firmware contract, entry conditions, linker addresses, and memory discovery.
- Single-core bring-up and the scope of later multicore support.
- Interrupt handling, synchronization, and interrupt-safe locking.
- Page allocation, virtual address layout, and user/kernel isolation.
- Scheduling policy, process model, syscall ABI, and executable format.
- Initial and persistent filesystems and packaging format.
- C library compatibility and MicroPython integration scope.
- Emulator choice, supported development hosts, CI, and release process.

Record decisions and their rationale in [docs/](./docs/) as implementation progresses.

## Contributing

Focus initial changes on the next incomplete milestone. Describe behavior, affected interfaces, hardware assumptions, and verification evidence. Document unsafe-code invariants and keep board-specific details within the hardware boundary.

A directory or interface alone does not make a feature complete. Completion requires observable behavior and a repeatable verification procedure.

### Documentation Maintenance

When a feature lands, update its status, build or usage instructions, and verification evidence together. Keep planned behavior explicitly marked until it has been demonstrated. Record hardware setup and design rationale in [docs/](./docs/) rather than leaving them only in development conversations.

## Terminology

| Term | Meaning in RustOS |
| --- | --- |
| Kernel | Privileged code responsible for managing CPU execution, memory, and access to system resources |
| HAL | Hardware abstraction layer: interfaces that separate portable services from hardware operations |
| BSP | Board support package: initialization and configuration specific to a supported board |
| Userland | Programs outside the kernel, including init, the shell, and utilities |
| Syscall ABI | The contract user programs follow to request kernel services |
| `no_std` | Rust code that does not depend on the standard library; runtime facilities must be supplied as needed |
| Host tools | Programs that run on the development computer to build or package target artifacts |

## License

No license file is currently present. A project license must be selected and added to establish explicit reuse and contribution terms.
