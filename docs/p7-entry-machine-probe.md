# P7 entry-harness machine inventory

2026-11-01. Queried two local QEMU machines while paused at reset, using bounded QMP exchanges. No kernel, test stub, Pi firmware or image was supplied/executed. No media was accessed. [Raw evidence](evidence/p7-entry-machine-probe.json) includes exact commands, emulator greeting/version, memory trees and reset registers. [Probe tool](../tools/probe_entry_machines.py) creates a fresh report and stops only its own emulator processes.

| Machine | Observed memory | Harness implication |
| --- | --- | --- |
| virt, virtualization enabled, Cortex-A53, 128 MiB | RAM 0x40000000–0x47ffffff inclusive | Does not cover Pi kernel 0x200000 or a DTB inside the validator's below-512-MiB window. Do not silently relocate production validation constants to make tests pass. |
| raspi3b, default memory | Base RAM 0–0x3fffffff inclusive, with higher-priority peripherals at 0x3f000000–0x3fffffff | Low addresses needed for Pi-like fixtures exist. Restrict synthetic RAM declarations to the approved board ceiling and avoid device overlays. This is an emulator model, not the user's Zero 2 W or Pi 5. |

The initial attempt batched QMP commands and timed out; its owned emulator was killed and no success report was written. Ordered greeting/capabilities/request/reply exchanges succeeded. The tool now has explicit reply timeouts, a 64-message event bound, hidden-window process creation on Windows and cleanup on failure. The successful recorded inventory predates only the additional event-count guard; machine arguments and queries are unchanged.

Next: prototype an explicit harness-only reset stub and controlled EL2 handoff on the low-memory model, verify CPU state/fixture loads and park secondaries. This requires actual execution evidence before selecting it as the definitive startup harness. Its memory inventory alone does not establish handoff, instruction behavior, protection against writes or an accepted stackless parser. Keep the [entry design gates](p7-stackless-entry-design.md) open, including exact CPU masks and register liveness. M1 is unchanged.
