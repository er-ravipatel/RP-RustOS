# P7 exact compiler-output entry verification

2026-11-01. [test_pi_compiler_entry.py](../tools/test_pi_compiler_entry.py) consumes the internal compiler report and verifies the recorded SHA-256 before and after execution. It does not rebuild or patch either kernel. A separate EL3 reset adapter and synthetic DTBs provide the emulator handoff.

[Both variants pass](evidence/p7-pi-compiler-entry.json) five CPU0 entry/BSS observations each: valid RAM without CMA, valid RAM with CMA, insufficient CMA space, zero RAM, and reserved stack overlap. Outside-stack write watchpoints and BSS sentinels check rejection before BSS mutation; accepted cases stop before console dispatch and check the zeroed BSS and expected boot record. Observation scope is inherited from the existing bounded entry harness.

Separate four-core observations confirm secondary cores park without establishing a stack. CPU0 reaches EL1 and safely rejects the unsupported measured-clock response at console stage 4. Serial capture is empty for both variants. This is expected failure-path evidence on the current QEMU model, not a successful UART, firmware or physical boot result.

First self-review checked binding to exact compiler output hashes and absence of kernel rebuilds or response injection. Second self-review checked all ten memory cases, secondary-core observations and explicit failure classification. The existing layout/stack record remains applicable to these same hashes.

```powershell
python tools/test_pi_compiler_entry.py --compiler-report target/pi-compiler-1793537607765823600/report.json
```

Next: flat kernel generation, complete image packaging and independent inspection. The public Pi bundle gate and physical UART acceptance remain pending.
