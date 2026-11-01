# M2 second review: source and implementation findings

2026-11-01. This is Codex self-review using a second method: published source and current implementation inspection following the initial documentation review. It is not independent human review or hardware verification.

## Confirmed implementation gaps

- Current entry assembly accepts EL1 only and overwrites x0 immediately. The published Pi Arm stub transitions to EL2, passes the device-tree pointer in x0, and parks secondary cores. Proposed Pi startup must preserve the handoff, identify the primary core and establish an explicit EL2-to-EL1 transition before common Rust initialization. The published stub is evidence of the intended path, not proof of the exact embedded stub in a firmware binary.
- Current linker address is 0x40080000 and console MMIO is QEMU-specific. Both require a separate board contract. The official legacy documentation now describes a 64-bit default load address of 0x200000; relying on remembered 0x80000 defaults is unsafe. Propose explicit load-address configuration and matching linker assertions after confirming the selected firmware behaviour.
- The kernel directly depends on the QEMU BSP; assembler profiles require an emulator table; build layouts admit only the four M1 modules. A Pi profile alone cannot select a working Pi build. Propose strict target-specific profile variants and mutually exclusive board selection, keeping existing M1 inputs valid and testing rejection of mixed board modules.

## Recommendations checked by documentation and source inspection

| Proposal | Second check and limit |
| --- | --- |
| Explicit AArch64 kernel selection | Official boot-option source supports 64-bit mode and uncompressed kernel images; current build emits ELF, so a checked ELF-to-flat conversion is required. |
| Reuse PL011 polling logic with separate board initialization | Board device tree assigns the primary serial alias to UART1 and UART0 to Bluetooth. The disable-bt overlay changes device-tree properties, not a bare-metal driver's pin initialization. Our BSP must program and verify its GPIO/clock setup explicitly. Final register sequence is still open. |
| Pin boot assets and preserve licences | Five official candidate files were read and hashed twice at immutable commit URLs. The normal start/fixup files must remain a matched pair. This is a candidate inventory, not an approved release or a hardware-tested combination. |
| Separate normal and panic images | Two independently hashed images avoid editing configuration after image verification. This is a project design choice; it requires user confirmation. |
| Keep image inspection and physical verification separate | Existing verification is QEMU-specific. Physical capture needs board/image identity, bounded serial collection and explicit operator power-cycle records; it cannot inherit an emulator pass. |

Candidate details and per-file hashes: [firmware candidate](evidence/m2-firmware-candidate.json). These are research metadata; asset bytes have not been added to a production bundle. Downloaded bytes total about 3.1 MB; no full Raspberry Pi OS image was needed.

## Remaining design gates

1. Finish register-level GPIO/UART and EL2 transition review against architecture/peripheral specifications.
2. Choose explicit image load address, memory reservations and DTB bounds; validate against selected firmware.
3. Specify image geometry and FAT constraints with an independent image-reader acceptance check.
4. Specify concrete target-profile versioning and artifact/report contracts before changing parsers.
5. Record available SD media, power and serial hardware. This information remains unanswered; it blocks physical setup, not ongoing host-side design.

Do not ask for blanket implementation approval yet. The concrete proposal must resolve these gates and receive the requested two checks first. P6 remains in progress; no boot or image test has passed.

## Sources inspected

- [Official Arm stub source](https://github.com/raspberrypi/tools/blob/master/armstubs/armstub8.S)
- [Official boot-option source](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/config_txt/boot.adoc)
- [Official legacy load-address and UART-clock settings](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/legacy_config_txt/boot.adoc)
- [Official board device tree](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/broadcom/bcm2710-rpi-zero-2-w.dts)
- [Official disable-bt overlay](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/overlays/disable-bt-overlay.dts)
- [Firmware licence](https://github.com/raspberrypi/firmware/blob/f2491b71ed49880cc8285e41e03f81b163c6cd59/boot/LICENCE.broadcom)

Local inspection: kernel entry/linker, QEMU BSP, kernel Cargo dependencies, assembler Profile/profile_valid and fixed build layouts. These findings describe the current M1 implementation; they do not invalidate M1's accepted scope.
