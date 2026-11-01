# P7 DTB board compatibility

2026-11-01. The isolated Pi BSP now validates the complete DTB token stream and requires the root `compatible` string list to contain the exact `raspberrypi,model-zero-2-w` entry. Prefix matches, empty entries, missing terminators and non-printable bytes are rejected. Child properties cannot establish root compatibility. Collected properties are discarded when the complete structural walk fails.

Validation: 22 BSP host tests passed; AArch64 no_std compilation and Clippy with warnings denied passed. The host example passed against the pinned 33,724-byte DTB at a synthetic address of `0x1000000`. This establishes file structure and board identity only, not observed firmware state, RAM safety or boot readiness.

Independent inspection of that unchanged file found `/memory@0/reg` containing address zero and size zero, and `/reserved-memory/linux,cma` requesting a dynamic 64 MiB allocation through `size`, without a static `reg`. Therefore the repository DTB must not be treated as a usable runtime RAM map. Firmware handoff data must be decoded and validated. Dynamic reservations require an explicit supported policy; they must not silently disappear from validation.

Next: decode address/size cells, extract runtime memory and reservations, and define conservative handling of dynamic reservations. Stackless preflight, CPU entry and kernel wiring remain pending. No SD card operation or physical boot was performed.

References: [Devicetree node requirements](https://devicetree-specification.readthedocs.io/en/stable/devicenodes.html), [reserved-memory binding](https://github.com/devicetree-org/dt-schema/blob/main/dtschema/schemas/reserved-memory/reserved-memory.yaml), [implementation](../bsp/rpi-zero2w/src/board.rs).
