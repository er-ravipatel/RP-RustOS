# Zero 2 W DTB reproduced twice

2026-11-01. The supplied Zero 2 W DTB was rebuilt from the pinned Linux source in two fresh containers. Both builds returned zero and produced the exact candidate bytes:

`5b31bc70011e454f482ba323b1eca22bf54fa2fa4682576ee73816a2eccfa277`

This closes the DTB source-to-binary reproduction gap for the selected candidate. It does not establish a RustOS image build, firmware boot or physical-board test.

## Evidence and environment

[Reproduction evidence](evidence/m2-dtb-reproduction.json) records both runs, immutable container image identity, commands and retained-file hashes. The [source package](../out/research/m2-source-9b488bc7a1e9/README.md) contains the archive, notices, boot assets and both output directories. Each run retained its complete build log, compiler/package versions, config and exact generated dtc command.

The existing Docker Desktop Linux engine was started. A pinned Debian base digest was used to install build tools inside an isolated image; no Windows compiler/toolchain was installed. The first registry layer download failed and its retry succeeded. Image construction used package repositories; the exact resulting image ID and installed package versions are recorded. The Dockerfile's package versions are not independently snapshot-pinned, so rebuilding that image later is not claimed byte-reproducible.

Compilation ran with no network, a read-only source-archive mount, a fresh output directory, two CPUs, 2 GiB memory limit, process limit, dropped capabilities and no new privileges. Temporary build containers were removed and no matching container remained after both runs. Docker Desktop and the compiler image remain available for future work.

## Reproduction method

The [Dockerfile](../tools/dtb-repro/Dockerfile), [build script](../tools/dtb-repro/run.sh) and [bounded runner](../tools/dtb-repro/run.py) capture the actual method. Each container verified the source archive hash, extracted its own copy, generated the upstream bcm2711 AArch64 configuration, and built only the Zero 2 W DTB using the pinned kernel build system. The generated config SHA-256 matched across both runs. DTC reports `1.7.2-g52f07dcc`.

Re-run from the repository root:

```text
docker build --tag rustos-dtb-repro:p6 tools/dtb-repro
python tools/dtb-repro/run.py
```

The runner resolves and records the actual image ID before execution and uses that identity for the container. Every invocation keeps a new evidence directory. A rebuilt-DTB mismatch returns nonzero even if compilation itself succeeded.

Two checks: first source build versus the retained official candidate; then an independent fresh-container rebuild using the same identified environment. Both rebuilt outputs were also compared directly with the retained candidate bytes, not solely their printed checksums. These are real source-compilation checks, distinct from the 58 synthetic M2 schema tests and from M1/QEMU acceptance.

Next: bind the source archive, build instructions and notices into the real asset lock, review its completeness, and proceed to Pi runtime implementation. Physical hardware setup remains unrecorded.
