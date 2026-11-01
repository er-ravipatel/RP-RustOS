# M1 environment verification — 2026-10-31

## Selected and checked environment

Native Windows; QEMU 11.1.0 (`v11.1.0-12130-ge470268ff4`), machine `virt-11.1`, CPU `cortex-a53`, software accelerator `tcg`, one core, 128 MiB RAM. Installed via WinGet package `SoftwareFreedomConservancy.QEMU`, version 11.1.0. The installer hash was verified by WinGet. The binary provider is linked from the [official QEMU download page](https://www.qemu.org/download/).

Rust/Cargo 1.88.0 are installed. A temporary `#![no_std]` library cross-compiled using `rustc --edition=2021 --crate-type=lib --emit=obj --target=aarch64-unknown-none-softfloat -C panic=abort`; the resulting object had the ELF signature and AArch64 machine ID 183. This establishes object generation, not a linked RustOS kernel or a tested host-side CLI build.

## Reproducible emulator probe

From the repository root:

```powershell
python tools/probe_emulator.py
```

Override the QEMU executable with `--qemu` if installed elsewhere. The checked Windows installation is `C:\Program Files\qemu\qemu-system-aarch64.exe`.

The probe generates a synthetic AArch64 ELF in a temporary directory, loads one executable segment at entry `0x40080000`, and writes to PL011 UART at `0x09000000`. It invokes QEMU with:

```text
-machine virt-11.1,secure=off,virtualization=off,gic-version=2
-cpu cortex-a53 -accel tcg -smp 1 -m 128M
-display none -monitor none -serial stdio -nic none
-kernel <temporary-probe.elf>
```

Expected output marker: `RUSTOS_ENV_PROBE_OK` followed by a newline. The fixture deliberately loops afterward. The probe observes a five-second deadline, terminates its own QEMU process, escalates to killing that same process if required, and waits for settlement. An early exit or missing marker fails the check. No disk is attached and no physical media is written.

## Recorded result

- `passed`: true.
- Serial output: `RUSTOS_ENV_PROBE_OK\n`.
- Standard error: empty.
- Expected loop reached deadline: true.
- Owned process settled: true.
- Generated fixture SHA-256: `b2f71c2b5dd0f346c3f6360fadf3c1a3efd5c37829df687dcb7565f6f12ffc93`.
- Installed machine inventory includes `virt-11.1`; CPU inventory includes `cortex-a53`.

## Scope and remaining contracts

This is environment evidence only. The fixture is hand-encoded machine code, not RustOS; it does not verify RustOS startup, exceptions, deliberate panic, stack/BSS setup, or Raspberry Pi hardware. No assembler run is recorded from this probe.

The initial loading approach is direct ELF loading. Schema/startup design must still specify kernel stack, reserved memory, entry registers and exception level assumptions, initialization invariants, Rust toolchain pinning, actual startup/panic markers, and production test deadlines. Image formats and boot assets for Zero 2 W remain M2 work. A source/tool version pin must be recorded in the implementation before claiming a reproducible delivered build.
