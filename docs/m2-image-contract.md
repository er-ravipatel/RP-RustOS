# M2 SD-image contract proposal

2026-11-01. D17 direction approved by the user; no image produced or hardware boot verified. [Boot contract](m2-boot-contract.md) and [console direction](m2-console-contract.md) are already agreed.

## Deliverables

Produce two separate raw disk images: `rustos-zero2w.img` for normal startup and `rustos-zero2w-panic.img` for deliberate panic. Each is immutable after publication, has its own SHA-256 and contains the applicable flat kernel under the same boot filename. Keep both corresponding ELFs, the resolved manifest, source/asset identities and build diagnostics in the bundle. Hardware evidence must identify which image was written; editing config after packaging invalidates its identity.

The image contains firmware and our bare-metal Rust kernel. No Linux root filesystem is required for M2. Build writes ordinary output files only. Physical media preparation remains a separate operator procedure; no automatic disk enumeration, formatting or flashing is added to build.

## Geometry

| Field | Proposed value |
| --- | --- |
| Complete image | 67,108,864 bytes (64 MiB) |
| Logical sector | 512 bytes |
| Partition table | MBR, one first primary FAT32-LBA partition, type 0x0c |
| Partition start | LBA 2048 (1 MiB alignment) |
| Partition length | 129,024 sectors; ends exactly at image boundary |
| FAT reserved area | 32 sectors |
| FAT copies | Two, 1024 sectors each |
| Cluster size | One sector, 512 bytes |
| Data clusters | 126,944 |

This is a project layout choice, not a claim that firmware requires exactly these dimensions. Larger physical cards retain unused space beyond the image; M2 does not resize a partition on first boot.

Use a standard FAT32 BPB, root cluster 2, matching FAT copies, valid primary/backup boot records and FSInfo, and correct partition-relative versus disk-relative offsets. Include valid VFAT long filenames and collision-free short aliases, especially for the board DTB and firmware licence. Reject duplicate names and unsafe paths. The independent reader must check both long names and their alias/checksum linkage.

## Boot content and provenance

Use only pinned, hashed inputs. Candidate firmware inventory: [asset hashes](evidence/m2-firmware-candidate.json), commit `f2491b71ed49880cc8285e41e03f81b163c6cd59`. It includes bootcode.bin, matched start.elf/fixup.dat, the Zero 2 W DTB and the firmware licence. The candidate is not yet approved as a tested production dependency.

Generate explicit AArch64, kernel-file and load-address settings from the agreed boot contract. Keep the firmware's device-tree handoff. Additional assets or settings required by the final GPIO/clock implementation must be listed, reviewed and hashed before the asset list is frozen. Do not quietly download extras or assume a Linux overlay configures bare-metal pins. Preserve applicable device-tree and other asset licences as well as the firmware notice; the current five-file inventory is not a complete licensing inventory for every potential asset.

## Deterministic packaging and acceptance

Use fixed recorded filesystem timestamps, stable allocation/name ordering, explicit padding and stable volume identifiers. Identical kernel bytes, assets, configuration and packaging version must yield identical image bytes; this does not assert that independent compiler invocations are already reproducible.

After writing a staged image, a reader separate from the writer must inspect the MBR, boundaries, boot records, FAT chains, directory names, file sizes and extracted hashes. Reject cycles, cross-links, out-of-range/truncated allocations, inconsistent metadata, unexpected files and missing licences. Compare both images against their individual declared content; normal and panic must never be confused. Publication retains the existing no-overwrite/atomic-output policy.

Image inspection success is a host result. Hardware boot success needs physical startup and panic captures for these exact images. Neither FAT arithmetic nor a QEMU run proves the Pi firmware accepted this image.

## Two review passes

1. Source review: official Pi documentation describes MBR media and a first FAT boot partition. Microsoft's authored FAT specification describes cluster-based FAT typing and on-disk structures. Scope check: the recommendation for an unpartitioned FAT boot.img in boot-ramdisk documentation is a different artifact, not this physical SD disk image.
2. Arithmetic and inventory review: 131,072 total sectors minus 2048 leading sectors gives 129,024 partition sectors. Subtract 32 reserved and two 1024-sector FATs: 126,944 data clusters, above the FAT32 threshold. Each FAT holds 131,072 entries, enough for data plus reserved entries. Current assets, a conservative 2 MiB kernel and directory allowance use about 10,256 clusters. Checked long-name requirements and paired normal/panic identities separately. Exact populated-image validation remains P8 work.

Both passes are Codex self-review. No generated image has been independently mounted or parsed yet.

## Sources

- [Official Raspberry Pi media/MBR documentation](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Official FAT boot-file documentation](https://www.raspberrypi.com/documentation/computers/configuration.html)
- [Microsoft-authored FAT specification, hosted by Stanford](https://www.scs.stanford.edu/~zyedidia/docs/_other/fat.pdf)

Decision D17: user approved two immutable 64 MiB MBR/FAT32 images, deterministic packaging and independent content inspection on 2026-11-01. Final asset licences, target/profile schemas and physical-media procedure remain required follow-up work.
