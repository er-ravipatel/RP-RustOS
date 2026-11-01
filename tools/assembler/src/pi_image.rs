//! Deterministic root-only FAT32 image writer for the approved D17 geometry.
use std::collections::{BTreeMap, BTreeSet};

const SECTOR: usize = 512;
const START: usize = 2048;
const TOTAL: usize = 131072;
const RESERVED: usize = 32;
const FAT: usize = 1024;
const CLUSTERS: usize = TOTAL - START - RESERVED - 2 * FAT;
const DATA: usize = (START + RESERVED + 2 * FAT) * SECTOR;

fn put16(bytes: &mut [u8], offset: usize, value: u16) {
    bytes[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}
fn put32(bytes: &mut [u8], offset: usize, value: u32) {
    bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}
fn checksum(alias: &[u8; 11]) -> u8 {
    alias
        .iter()
        .fold(0u8, |sum, byte| sum.rotate_right(1).wrapping_add(*byte))
}
fn alias(name: &str, index: usize) -> [u8; 11] {
    let mut result = [b' '; 11];
    let parts: Vec<_> = name.split('.').collect();
    if parts.len() <= 2
        && parts[0].len() <= 8
        && parts
            .last()
            .is_some_and(|p| p.len() <= 3 || parts.len() == 1)
        && parts
            .iter()
            .all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_'))
    {
        let stem = parts[0].to_ascii_uppercase();
        result[..stem.len()].copy_from_slice(stem.as_bytes());
        if parts.len() == 2 {
            let ext = parts[1].to_ascii_uppercase();
            result[8..8 + ext.len()].copy_from_slice(ext.as_bytes());
        }
    } else {
        result.copy_from_slice(format!("F{index:07}BIN").as_bytes());
    }
    result
}

pub(crate) fn image(files: &BTreeMap<String, Vec<u8>>) -> Result<Vec<u8>, &'static str> {
    if files.is_empty() || files.len() > 32 {
        return Err("Image requires 1..32 root files");
    }
    let mut seen = BTreeSet::new();
    let mut aliases = BTreeSet::new();
    let mut entries = Vec::new();
    for (index, (name, bytes)) in files.iter().enumerate() {
        if name.is_empty()
            || name.len() > 64
            || name.ends_with([' ', '.'])
            || !name
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b))
            || matches!(name.as_str(), "." | "..")
            || !seen.insert(name.to_ascii_uppercase())
        {
            return Err("Unsafe or duplicate FAT name");
        }
        let short = alias(name, index + 1);
        if !aliases.insert(short) {
            return Err("FAT alias collision");
        }
        entries.push((name, bytes, short));
    }
    // Always retain exact case through VFAT, including otherwise valid 8.3 names.
    let dir_entries: usize = entries
        .iter()
        .map(|(name, _, _)| name.len().div_ceil(13) + 1)
        .sum();
    let root_clusters = ((dir_entries + 1) * 32).div_ceil(SECTOR);
    let used = root_clusters
        + entries
            .iter()
            .map(|(_, bytes, _)| bytes.len().div_ceil(SECTOR))
            .sum::<usize>();
    if used > CLUSTERS {
        return Err("Boot files exceed FAT32 capacity");
    }
    let mut disk = vec![0; TOTAL * SECTOR];
    // Saturated CHS fields; LBA fields are authoritative.
    disk[446..462].copy_from_slice(&[
        0, 0x20, 0x21, 0, 0x0c, 0xfe, 0xff, 0xff, 0, 8, 0, 0, 0, 0xf8, 1, 0,
    ]);
    disk[510..512].copy_from_slice(&[0x55, 0xaa]);
    let mut boot = [0u8; SECTOR];
    boot[..3].copy_from_slice(&[0xeb, 0x58, 0x90]);
    boot[3..11].copy_from_slice(b"RUSTOS  ");
    put16(&mut boot, 11, 512);
    boot[13] = 1;
    put16(&mut boot, 14, 32);
    boot[16] = 2;
    boot[21] = 0xf8;
    put16(&mut boot, 24, 63);
    put16(&mut boot, 26, 255);
    put32(&mut boot, 28, START as u32);
    put32(&mut boot, 32, (TOTAL - START) as u32);
    put32(&mut boot, 36, FAT as u32);
    put32(&mut boot, 44, 2);
    put16(&mut boot, 48, 1);
    put16(&mut boot, 50, 6);
    boot[64] = 0x80;
    boot[66] = 0x29;
    put32(&mut boot, 67, 0x52555354);
    boot[71..82].copy_from_slice(b"RUSTOS     ");
    boot[82..90].copy_from_slice(b"FAT32   ");
    boot[510..512].copy_from_slice(&[0x55, 0xaa]);
    for sector in [START, START + 6] {
        disk[sector * SECTOR..(sector + 1) * SECTOR].copy_from_slice(&boot);
    }
    let mut info = [0u8; SECTOR];
    put32(&mut info, 0, 0x41615252);
    put32(&mut info, 484, 0x61417272);
    put32(&mut info, 488, (CLUSTERS - used) as u32);
    put32(
        &mut info,
        492,
        if used < CLUSTERS {
            (used + 2) as u32
        } else {
            u32::MAX
        },
    );
    put32(&mut info, 508, 0xaa550000);
    for sector in [START + 1, START + 7] {
        disk[sector * SECTOR..(sector + 1) * SECTOR].copy_from_slice(&info);
    }
    let mut fat = vec![0u8; FAT * SECTOR];
    put32(&mut fat, 0, 0x0ffffff8);
    put32(&mut fat, 4, 0xffffffff);
    let chain = |fat: &mut [u8], first: usize, count: usize| {
        for c in first..first + count {
            put32(
                fat,
                c * 4,
                if c + 1 == first + count {
                    0x0fffffff
                } else {
                    (c + 1) as u32
                },
            );
        }
    };
    chain(&mut fat, 2, root_clusters);
    let mut next = root_clusters + 2;
    let mut directory = Vec::new();
    for (name, bytes, short) in entries {
        let units: Vec<u16> = name.encode_utf16().collect();
        let slots = units.len().div_ceil(13);
        for ordinal in (1..=slots).rev() {
            let mut entry = [0xffu8; 32];
            entry[0] = ordinal as u8 | if ordinal == slots { 0x40 } else { 0 };
            entry[11] = 0x0f;
            entry[12] = 0;
            entry[13] = checksum(&short);
            put16(&mut entry, 26, 0);
            for (i, offset) in [1, 3, 5, 7, 9, 14, 16, 18, 20, 22, 24, 28, 30]
                .into_iter()
                .enumerate()
            {
                let index = (ordinal - 1) * 13 + i;
                put16(
                    &mut entry,
                    offset,
                    if index < units.len() {
                        units[index]
                    } else if index == units.len() {
                        0
                    } else {
                        0xffff
                    },
                );
            }
            directory.extend_from_slice(&entry);
        }
        let clusters = bytes.len().div_ceil(SECTOR);
        let first = if clusters == 0 { 0 } else { next };
        let mut entry = [0u8; 32];
        entry[..11].copy_from_slice(&short);
        entry[11] = 0x20;
        for offset in [16, 18, 24] {
            put16(&mut entry, offset, 0x21);
        } // 1980-01-01
        put16(&mut entry, 20, (first >> 16) as u16);
        put16(&mut entry, 26, first as u16);
        put32(&mut entry, 28, bytes.len() as u32);
        directory.extend_from_slice(&entry);
        if clusters > 0 {
            chain(&mut fat, next, clusters);
            let start = DATA + (next - 2) * SECTOR;
            disk[start..start + bytes.len()].copy_from_slice(bytes);
            next += clusters;
        }
    }
    disk[DATA..DATA + directory.len()].copy_from_slice(&directory);
    for sector in [START + RESERVED, START + RESERVED + FAT] {
        disk[sector * SECTOR..sector * SECTOR + fat.len()].copy_from_slice(&fat);
    }
    Ok(disk)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[ignore = "writes a synthetic 64 MiB image for independent reader acceptance"]
    fn synthetic_image_acceptance() {
        let repo = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap();
        let id = std::time::SystemTime::now()
            .duration_since(std::time::SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let output = repo.join(format!("target/pi-fat-{id}"));
        std::fs::create_dir(&output).unwrap();
        let files = BTreeMap::from([
            ("config.txt".into(), b"arm_64bit=1\n".to_vec()),
            ("bcm2710-rpi-zero-2-w.dtb".into(), vec![0xa5; 700]),
            (
                "LICENCE.broadcom".into(),
                b"synthetic fixture only".to_vec(),
            ),
            ("empty.txt".into(), vec![]),
        ]);
        let bytes = image(&files).unwrap();
        std::fs::write(output.join("fixture.img"), &bytes).unwrap();
        let expected: BTreeMap<_, _> = files
            .iter()
            .map(|(name, data)| (name, crate::build::hash(data)))
            .collect();
        std::fs::write(
            output.join("expected.json"),
            serde_json::to_vec_pretty(&expected).unwrap(),
        )
        .unwrap();
        println!("Synthetic image: {}", output.display());
    }
    #[test]
    fn deterministic_geometry_and_matching_backup_metadata() {
        let files = BTreeMap::from([
            ("config.txt".into(), b"arm_64bit=1\n".to_vec()),
            ("bcm2710-rpi-zero-2-w.dtb".into(), vec![0xa5; 700]),
        ]);
        let disk = image(&files).unwrap();
        assert_eq!(disk, image(&files).unwrap());
        assert_eq!(disk.len(), 67108864);
        assert_eq!(&disk[510..512], &[0x55, 0xaa]);
        assert_eq!(
            &disk[START * 512..(START + 1) * 512],
            &disk[(START + 6) * 512..(START + 7) * 512]
        );
        assert_eq!(
            &disk[(START + 1) * 512..(START + 2) * 512],
            &disk[(START + 7) * 512..(START + 8) * 512]
        );
        assert_eq!(
            &disk[(START + 32) * 512..(START + 32 + 1024) * 512],
            &disk[(START + 32 + 1024) * 512..(START + 32 + 2048) * 512]
        );
    }
    #[test]
    fn unsafe_duplicate_and_over_capacity_inputs_reject() {
        for name in ["../kernel", "a/b", "..", "bad name", "trailing."] {
            assert!(image(&BTreeMap::from([(name.into(), vec![])])).is_err());
        }
        assert!(image(&BTreeMap::from([
            ("A.TXT".into(), vec![]),
            ("a.txt".into(), vec![])
        ]))
        .is_err());
        assert!(image(&BTreeMap::from([(
            "kernel8.img".into(),
            vec![0; CLUSTERS * 512]
        )]))
        .is_err());
    }
}
