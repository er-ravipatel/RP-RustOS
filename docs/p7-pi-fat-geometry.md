# P7 deterministic FAT32 packaging foundation

2026-11-01. [pi_image.rs](../tools/assembler/src/pi_image.rs) implements an internal root-only image writer using the approved D17 geometry: 64 MiB disk, one FAT32-LBA partition at LBA 2048, 129,024 partition sectors, 32 reserved sectors, two 1024-sector FATs and 512-byte clusters. Primary/backup boot sectors and FSInfo match. Root and file allocations use stable sorted ordering, fixed volume identity and 1980-01-01 file dates. All files retain exact case through VFAT long entries with checksummed short aliases.

Inputs are limited to 32 root files and ASCII names up to 64 characters. Unsafe names, case-insensitive duplicates, short-alias collisions and insufficient cluster capacity reject. Empty files have zero first-cluster and size. Deterministic gaps and slack are zero-filled. This component creates bytes in memory; publication and disk-device access are not part of it.

A [separate Python reader](../tools/check_pi_fat.py) validates partition/BPB geometry, backup metadata, FAT equality, chain bounds/cycles/cross-links, VFAT sequences/checksums, file allocation/padding, extracted file hashes, orphan clusters and FSInfo free count. It imports no writer code. It is a strict engineering reader for this fixed layout, not yet the complete production schema-2 image inspector.

[Synthetic fixture evidence](evidence/p7-pi-fat-geometry.json) includes short and long filenames, a multi-cluster file, a licence-shaped name and an empty file. The reader extracts all exact hashes. Eight mutations reject: MBR signature, partition type, boot backup, FSInfo backup, FAT mirror, long-name checksum, file bytes and a mirrored root-chain cycle. This fixture contains synthetic content, not firmware or a bootable kernel.

43 regular Rust tests pass, including deterministic whole-image byte comparison, metadata mirrors, invalid names, duplicate names and capacity rejection. The explicit fixture acceptance passes. Five M1 CLI and nine M1 build acceptance tests also pass. Scoped Clippy passes with the previously recorded result_large_err allowance.

First self-review checked D17 arithmetic, cluster allocation, file-size rounding, backups and deterministic naming/timestamps. Second self-review checked separate extraction and corruption rejection. Remaining inspector coverage includes real complete inventory, larger directories, additional malformed-name/chain/metadata mutations and full provenance binding. No filesystem mount, firmware boot, normal/panic SD-image publication or physical media operation is claimed.

Next: connect locked firmware/licences/configuration and both flat kernels, inspect the actual populated images, then integrate no-replacement complete-bundle publication. Hardware testing is not ready yet.

```powershell
cargo test --manifest-path tools/assembler/Cargo.toml synthetic_image_acceptance -- --ignored --nocapture
python tools/test_pi_fat.py --fixture target/pi-fat-1793538949820740200
```
