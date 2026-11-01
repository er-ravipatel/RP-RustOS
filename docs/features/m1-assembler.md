# M1 assembler and emulator verification

Status: complete within the delivered M1 scope. The canonical requirements, review, reproduction commands, evidence and limitations are recorded in [M1 acceptance](../m1-acceptance.md).

The assembler validates and resolves the QEMU target, builds normal and deliberate-panic kernels, publishes a manifest, and verifies both scenarios with bounded process ownership and cleanup checks. This feature does not establish Raspberry Pi image or hardware support; those belong to M2.
