# Proposed RustOS architecture

This page describes the target operating system. The [assembler architecture](assembler-architecture.md) describes the host application that selects, builds, packages, and verifies those components; its component responsibility boundaries are agreed.

## Context and boundaries

The development host builds and packages artifacts. Board firmware loads the kernel under a contract still to be selected. RustOS owns its kernel and userland; it does not assume Linux services. The first hardware target is Raspberry Pi Zero 2 W, with AArch64 as the intended execution mode.

```mermaid
flowchart TB
  Developer --> Host[Development host: build and inspect]
  Host --> Image[Image builder and packager]
  Image --> Media[Boot media and required firmware]
  Media --> Board[Raspberry Pi Zero 2 W]
  Operator --> Terminal[Serial terminal]
  Terminal <--> Board
```

## Subsystems

Arrows below indicate proposed service use, not existing crate dependencies. Filesystem access to block storage applies to a future persistent backend; an early in-memory filesystem need not use it.

```mermaid
flowchart TB
  Init[Init] --> ABI[Syscall ABI]
  Shell[Shell and utilities] --> ABI
  Runtime[C and MicroPython runtime support] --> ABI
  ABI --> MM[Memory management]
  ABI --> Sched[Task scheduler]
  ABI --> FS[Filesystem]
  ABI --> IPC[IPC]
  Kernel[Kernel integration] --> MM
  Kernel --> Sched
  Kernel --> FS
  Kernel --> IPC
  Sched --> Timer[Timer driver]
  FS --> Block[Block driver]
  ABI --> Console[Console driver]
  GPIO[GPIO driver] --> HAL[Hardware contracts]
  Timer --> HAL
  Block --> HAL
  Console --> HAL
  HAL --> BSP[Board support and device configuration]
```

## Proposed boot flow

```mermaid
flowchart TD
  Firmware[Board firmware] --> Entry[Entry contract and initial stack]
  Entry --> Early[Minimal board and serial setup]
  Early --> Exceptions[Exception diagnostics]
  Exceptions --> Memory[Memory discovery and allocation]
  Memory --> Devices[Interrupt and timer setup]
  Devices --> Tasks[Scheduler and initial tasks]
  Tasks --> User[User address space and init]
  User --> Shell[Interactive shell]
  Early -. failure .-> Panic[Report available diagnostics and stop safely]
  Memory -. failure .-> Panic
  Devices -. failure .-> Panic
```

Only the early portion is needed for first boot. Later initialization ordering must be refined after the boot, memory, and interrupt designs are selected.

## Program execution workflow

```mermaid
sequenceDiagram
  actor User
  participant Shell
  participant Kernel
  participant Loader
  participant Task
  User->>Shell: Enter program command
  Shell->>Kernel: Request program launch through proposed ABI
  Kernel->>Loader: Validate executable and resources
  alt Invalid image or insufficient resources
    Loader-->>Kernel: Structured error
    Kernel-->>Shell: Launch failure
    Shell-->>User: Diagnostic and prompt
  else Valid executable
    Loader->>Task: Create address space and execution state
    Kernel->>Task: Schedule execution
    Task-->>Kernel: Exit or fault
    Kernel-->>Shell: Completion result
    Shell-->>User: Result and next prompt
  end
```

## Safety and ownership

Board support owns board addresses and initialization assumptions. Drivers own device access; shared access needs an explicit synchronization policy. Memory management owns page and mapping lifetimes. Syscall dispatch validates user-provided values and pointers. Task teardown must release owned resources. Unsafe operations require documented invariants and fault-oriented verification.

These are design constraints, not guarantees provided by current code. Exception level, executable format, syscall ABI, address layout, locking, filesystem format, and image layout remain open. See the [feature catalog](features/README.md) for the corresponding specification proposals.
