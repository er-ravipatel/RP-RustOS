#![no_std]
//! Zero 2 W boot-data validation and mailbox protocol; hardware console wiring pending.
use core::ops::Range;
mod structure;
pub use structure::validate_structure;
mod board;
pub use board::{validate_board, BoardError};
mod memory;
pub use memory::{decode_reg, validate_memory_ranges, MemoryError, MemoryRange};
mod boot_memory;
pub use boot_memory::{inspect_boot_memory, validate_boot_memory, BootMemoryError, BootMemoryInfo};
mod cma;
pub use cma::{select_cma_pool, PoolError};
mod entry_abi;
pub use entry_abi::{rustos_validate_boot_memory, BootMemoryResult};
pub mod mailbox;
pub mod uart_clock;
pub mod uart_prepare;

pub const KERNEL_START: u64 = 0x20_0000;
pub const KERNEL_END: u64 = 0x40_0000;
pub const MAX_DTB_SIZE: usize = 2 * 1024 * 1024;
pub const MAX_RESERVATIONS: usize = 128;
// Addressability ceiling only; firmware's usable ARM RAM must be checked later.
const BOARD_RAM_CEILING: u64 = 512 * 1024 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BootDataError {
    Truncated,
    Magic,
    Version,
    Layout,
    Address,
    KernelOverlap,
    ReservationOverflow,
    ReservationOverlap,
    ReservationLimit,
    Structure,
    DepthLimit,
    PropertyLimit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DtbLayout {
    pub total_size: usize,
    pub structure: Range<usize>,
    pub strings: Range<usize>,
    pub reservation_count: usize,
}

fn word(bytes: &[u8], offset: usize) -> Result<u32, BootDataError> {
    let data = bytes
        .get(offset..offset + 4)
        .ok_or(BootDataError::Truncated)?;
    Ok(u32::from_be_bytes(data.try_into().unwrap()))
}

fn overlaps(start: u64, end: u64, other_start: u64, other_end: u64) -> bool {
    start < other_end && other_start < end
}

fn reservation(bytes: &[u8], offset: usize) -> (u64, u64) {
    // Caller has checked that the entire 16-byte record lies in the map block.
    let address = u64::from_be_bytes(bytes[offset..offset + 8].try_into().unwrap());
    let size = u64::from_be_bytes(bytes[offset + 8..offset + 16].try_into().unwrap());
    (address, size)
}

/// Inspect an already-readable byte slice and its claimed physical placement.
/// Does not dereference physical memory, parse tree properties, or prove usable RAM.
pub fn inspect_dtb(bytes: &[u8], physical_address: u64) -> Result<DtbLayout, BootDataError> {
    if bytes.len() < 40 {
        return Err(BootDataError::Truncated);
    }
    if word(bytes, 0)? != 0xd00d_feed {
        return Err(BootDataError::Magic);
    }
    let total = word(bytes, 4)? as usize;
    if !(40..=MAX_DTB_SIZE).contains(&total) || total > bytes.len() {
        return Err(BootDataError::Truncated);
    }
    let version = word(bytes, 20)?;
    let compatible = word(bytes, 24)?;
    if version < 17 || !(16..=17).contains(&compatible) || compatible > version {
        return Err(BootDataError::Version);
    }
    let end_address = physical_address
        .checked_add(total as u64)
        .ok_or(BootDataError::Address)?;
    if physical_address < 0x1000 || physical_address & 7 != 0 || end_address > BOARD_RAM_CEILING {
        return Err(BootDataError::Address);
    }
    if overlaps(physical_address, end_address, KERNEL_START, KERNEL_END) {
        return Err(BootDataError::KernelOverlap);
    }
    let structure_start = word(bytes, 8)? as usize;
    let strings_start = word(bytes, 12)? as usize;
    let map_start = word(bytes, 16)? as usize;
    let strings_len = word(bytes, 32)? as usize;
    let structure_len = word(bytes, 36)? as usize;
    let structure_end = structure_start
        .checked_add(structure_len)
        .ok_or(BootDataError::Layout)?;
    let strings_end = strings_start
        .checked_add(strings_len)
        .ok_or(BootDataError::Layout)?;
    if map_start < 40
        || map_start & 7 != 0
        || map_start > total
        || structure_start < map_start
        || structure_start & 3 != 0
        || structure_len < 4
        || structure_len & 3 != 0
        || structure_end > strings_start
        || strings_end > total
    {
        return Err(BootDataError::Layout);
    }
    let mut cursor = map_start;
    let mut count = 0;
    loop {
        let next = cursor.checked_add(16).ok_or(BootDataError::Layout)?;
        if next > structure_start || next > total {
            return Err(BootDataError::Layout);
        }
        let (address, size) = reservation(bytes, cursor);
        if address == 0 && size == 0 {
            break;
        }
        if count == MAX_RESERVATIONS {
            return Err(BootDataError::ReservationLimit);
        }
        let end = address
            .checked_add(size)
            .ok_or(BootDataError::ReservationOverflow)?;
        if size != 0 {
            if overlaps(address, end, KERNEL_START, KERNEL_END) {
                return Err(BootDataError::KernelOverlap);
            }
            for previous in (map_start..cursor).step_by(16) {
                let (start, length) = reservation(bytes, previous);
                // Each preceding range already passed overflow validation.
                if length != 0 && overlaps(address, end, start, start + length) {
                    return Err(BootDataError::ReservationOverlap);
                }
            }
        }
        count += 1;
        cursor = next;
    }
    Ok(DtbLayout {
        total_size: total,
        structure: structure_start..structure_end,
        strings: strings_start..strings_end,
        reservation_count: count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn put(bytes: &mut [u8], offset: usize, value: u32) {
        bytes[offset..offset + 4].copy_from_slice(&value.to_be_bytes());
    }
    fn fixture() -> [u8; 128] {
        let mut data = [0; 128];
        for (offset, value) in [
            (0, 0xd00d_feed),
            (4, 128),
            (8, 88),
            (12, 104),
            (16, 40),
            (20, 17),
            (24, 16),
            (32, 1),
            (36, 16),
        ] {
            put(&mut data, offset, value);
        }
        // Synthetic empty-root structure; property parsing is outside this helper.
        put(&mut data, 88, 1);
        put(&mut data, 96, 2);
        put(&mut data, 100, 9);
        data
    }
    fn reserve(data: &mut [u8], offset: usize, address: u64, size: u64) {
        data[offset..offset + 8].copy_from_slice(&address.to_be_bytes());
        data[offset + 8..offset + 16].copy_from_slice(&size.to_be_bytes());
    }

    #[test]
    fn minimal_header_and_reserved_range_pass() {
        let mut data = fixture();
        reserve(&mut data, 40, 0, 0x1000);
        assert_eq!(inspect_dtb(&data, 0x100_0000).unwrap().reservation_count, 1);
    }
    #[test]
    fn all_truncations_fail_without_panicking() {
        let data = fixture();
        for end in 0..data.len() {
            assert!(inspect_dtb(&data[..end], 0x100_0000).is_err());
        }
    }
    #[test]
    fn magic_version_and_layout_rejections() {
        for (offset, value) in [
            (0, 0),
            (20, 16),
            (24, 18),
            (8, 89),
            (16, 41),
            (36, u32::MAX),
            (32, u32::MAX),
            (12, 90),
        ] {
            let mut data = fixture();
            put(&mut data, offset, value);
            assert!(inspect_dtb(&data, 0x100_0000).is_err());
        }
    }
    #[test]
    fn pointer_range_and_kernel_overlap_rejections() {
        for address in [
            0,
            0x1001,
            KERNEL_START,
            KERNEL_START - 64,
            BOARD_RAM_CEILING - 8,
            u64::MAX - 7,
        ] {
            assert!(inspect_dtb(&fixture(), address).is_err());
        }
        assert!(inspect_dtb(&fixture(), KERNEL_END).is_ok());
    }
    #[test]
    fn reserved_kernel_overflow_overlap_and_missing_terminator_fail() {
        for (address, size) in [(KERNEL_START, 1), (u64::MAX, 2)] {
            let mut data = fixture();
            reserve(&mut data, 40, address, size);
            assert!(inspect_dtb(&data, 0x100_0000).is_err());
        }
        let mut data = fixture();
        reserve(&mut data, 40, 0x1000, 0x1000);
        reserve(&mut data, 56, 0x1800, 0x100);
        assert_eq!(
            inspect_dtb(&data, 0x100_0000),
            Err(BootDataError::ReservationOverlap)
        );
        let mut data = fixture();
        for offset in [40, 56, 72] {
            reserve(&mut data, offset, 0x1000 + offset as u64, 1);
        }
        assert!(inspect_dtb(&data, 0x100_0000).is_err());
    }

    #[test]
    fn excessive_reservation_count_is_bounded() {
        let mut data = [0; 2200];
        data[..40].copy_from_slice(&fixture()[..40]);
        put(&mut data, 4, 2200);
        put(&mut data, 8, 2120);
        put(&mut data, 12, 2136);
        for i in 0..129 {
            reserve(&mut data, 40 + i * 16, 0x1000 + i as u64 * 2, 1);
        }
        assert_eq!(
            inspect_dtb(&data, 0x100_0000),
            Err(BootDataError::ReservationLimit)
        );
    }
}
