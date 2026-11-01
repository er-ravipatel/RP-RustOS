//! Validation of declared ranges only; no DTB extraction or physical memory access.
use crate::{
    overlaps, BOARD_RAM_CEILING, KERNEL_END, KERNEL_START, MAX_DTB_SIZE, MAX_RESERVATIONS,
};

pub const MAX_RAM_RANGES: usize = 16;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MemoryRange {
    pub start: u64,
    pub size: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MemoryError {
    Cells,
    RegLength,
    Count,
    Empty,
    Overflow,
    AddressBounds,
    OverlappingRam,
    OverlappingReservations,
    KernelNotInRam,
    DtbNotInRam,
    DtbPlacement,
    KernelReserved,
}

/// Decode explicit big-endian DTB `reg` tuples into caller-owned bounded storage.
/// Both cell counts must be supplied from the parent node, never guessed.
/// This checks range syntax and addressability, not RAM/reservation semantics.
pub fn decode_reg<'a>(
    value: &[u8],
    address_cells: u32,
    size_cells: u32,
    output: &'a mut [MemoryRange],
) -> Result<&'a [MemoryRange], MemoryError> {
    if !(1..=2).contains(&address_cells) || !(1..=2).contains(&size_cells) {
        return Err(MemoryError::Cells);
    }
    let address_bytes = address_cells as usize * 4;
    let tuple_bytes = address_bytes + size_cells as usize * 4;
    if value.is_empty() || value.len() % tuple_bytes != 0 {
        return Err(MemoryError::RegLength);
    }
    let count = value.len() / tuple_bytes;
    if count > output.len() || count > MAX_RESERVATIONS {
        return Err(MemoryError::Count);
    }
    fn integer(bytes: &[u8]) -> u64 {
        bytes
            .iter()
            .fold(0, |value, byte| (value << 8) | u64::from(*byte))
    }
    let range = |tuple: &[u8]| MemoryRange {
        start: integer(&tuple[..address_bytes]),
        size: integer(&tuple[address_bytes..]),
    };
    // Validate the entire property before changing caller-owned output.
    for tuple in value.chunks_exact(tuple_bytes) {
        end(range(tuple))?;
    }
    for (slot, tuple) in output.iter_mut().zip(value.chunks_exact(tuple_bytes)) {
        *slot = range(tuple);
    }
    Ok(&output[..count])
}

fn end(range: MemoryRange) -> Result<u64, MemoryError> {
    if range.size == 0 {
        return Err(MemoryError::Empty);
    }
    let end = range
        .start
        .checked_add(range.size)
        .ok_or(MemoryError::Overflow)?;
    if end > BOARD_RAM_CEILING {
        return Err(MemoryError::AddressBounds);
    }
    Ok(end)
}

fn contains(range: MemoryRange, start: u64, end_address: u64) -> bool {
    // All ranges are checked before containment checks.
    range.start <= start && end_address <= range.start + range.size
}

/// Check complete kernel/DTB containment and reserved-range conflicts.
/// Caller must supply all firmware RAM/reservation declarations; this function
/// neither authenticates those declarations nor authorizes physical writes.
pub fn validate_memory_ranges(
    ram: &[MemoryRange],
    reserved: &[MemoryRange],
    dtb: MemoryRange,
) -> Result<(), MemoryError> {
    if ram.is_empty() || ram.len() > MAX_RAM_RANGES || reserved.len() > MAX_RESERVATIONS {
        return Err(MemoryError::Count);
    }
    for (index, range) in ram.iter().copied().enumerate() {
        let finish = end(range)?;
        for previous in &ram[..index] {
            if overlaps(
                range.start,
                finish,
                previous.start,
                previous.start + previous.size,
            ) {
                return Err(MemoryError::OverlappingRam);
            }
        }
    }
    for (index, range) in reserved.iter().copied().enumerate() {
        let finish = end(range)?;
        if overlaps(range.start, finish, KERNEL_START, KERNEL_END) {
            return Err(MemoryError::KernelReserved);
        }
        for previous in &reserved[..index] {
            if overlaps(
                range.start,
                finish,
                previous.start,
                previous.start + previous.size,
            ) {
                return Err(MemoryError::OverlappingReservations);
            }
        }
    }
    let dtb_end = end(dtb)?;
    if dtb.start < 0x1000
        || dtb.start & 7 != 0
        || dtb.size > MAX_DTB_SIZE as u64
        || overlaps(dtb.start, dtb_end, KERNEL_START, KERNEL_END)
    {
        return Err(MemoryError::DtbPlacement);
    }
    // Conservative M2 contract: each complete object fits one declared bank.
    if !ram.iter().any(|r| contains(*r, KERNEL_START, KERNEL_END)) {
        return Err(MemoryError::KernelNotInRam);
    }
    if !ram.iter().any(|r| contains(*r, dtb.start, dtb_end)) {
        return Err(MemoryError::DtbNotInRam);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;
    const RAM: MemoryRange = MemoryRange {
        start: 0,
        size: 128 * 1024 * 1024,
    };
    const DTB: MemoryRange = MemoryRange {
        start: 0x100_0000,
        size: 33724,
    };

    #[test]
    fn reg_decodes_all_supported_cell_widths_and_multiple_banks() {
        for addresses in 1..=2 {
            for sizes in 1..=2 {
                let mut bytes = std::vec::Vec::new();
                for (start, size) in [(0_u64, 0x800_0000_u64), (0x1000_0000, 0x1000)] {
                    bytes.extend_from_slice(&start.to_be_bytes()[8 - addresses as usize * 4..]);
                    bytes.extend_from_slice(&size.to_be_bytes()[8 - sizes as usize * 4..]);
                }
                let mut output = [DTB; 2];
                let decoded = decode_reg(&bytes, addresses, sizes, &mut output).unwrap();
                assert_eq!(
                    decoded,
                    &[
                        RAM,
                        MemoryRange {
                            start: 0x1000_0000,
                            size: 0x1000
                        }
                    ]
                );
            }
        }
    }

    #[test]
    fn invalid_reg_never_changes_output() {
        let mut output = [DTB; 2];
        for cells in [0, 3, u32::MAX] {
            assert_eq!(
                decode_reg(&[0; 8], cells, 1, &mut output),
                Err(MemoryError::Cells)
            );
            assert_eq!(
                decode_reg(&[0; 8], 1, cells, &mut output),
                Err(MemoryError::Cells)
            );
        }
        for length in [0, 1, 7, 9, 15] {
            assert_eq!(
                decode_reg(&[0; 16][..length], 1, 1, &mut output),
                Err(MemoryError::RegLength)
            );
        }
        assert_eq!(
            decode_reg(&[0; 8], 1, 1, &mut output),
            Err(MemoryError::Empty)
        );
        assert_eq!(
            decode_reg(&[0xff; 16], 2, 2, &mut output),
            Err(MemoryError::Overflow)
        );
        let bad_second = [0, 0, 0, 0, 0, 0, 16, 0, 0x20, 0, 0, 0, 0, 0, 0, 1];
        assert_eq!(
            decode_reg(&bad_second, 1, 1, &mut output),
            Err(MemoryError::AddressBounds)
        );
        assert_eq!(output, [DTB; 2]);
        assert_eq!(
            decode_reg(&bad_second, 1, 1, &mut output[..1]),
            Err(MemoryError::Count)
        );
    }

    #[test]
    fn kernel_and_dtb_fit_with_low_memory_and_dtb_reservations() {
        assert_eq!(
            validate_memory_ranges(
                &[RAM],
                &[
                    MemoryRange {
                        start: 0,
                        size: 0x1000
                    },
                    DTB
                ],
                DTB
            ),
            Ok(())
        );
    }

    #[test]
    fn empty_overflowing_and_out_of_board_ranges_fail() {
        for range in [
            MemoryRange { start: 0, size: 0 },
            MemoryRange {
                start: u64::MAX,
                size: 2,
            },
            MemoryRange {
                start: 0,
                size: BOARD_RAM_CEILING + 1,
            },
        ] {
            assert!(validate_memory_ranges(&[range], &[], DTB).is_err());
            assert!(validate_memory_ranges(&[RAM], &[range], DTB).is_err());
        }
    }

    #[test]
    fn declared_ram_must_contain_entire_kernel_and_dtb() {
        assert_eq!(
            validate_memory_ranges(
                &[MemoryRange {
                    start: 0,
                    size: KERNEL_END - 1
                }],
                &[],
                DTB
            ),
            Err(MemoryError::KernelNotInRam)
        );
        assert_eq!(
            validate_memory_ranges(
                &[MemoryRange {
                    start: 0,
                    size: DTB.start + DTB.size - 1
                }],
                &[],
                DTB
            ),
            Err(MemoryError::DtbNotInRam)
        );
    }

    #[test]
    fn reserved_kernel_byte_fails_but_touching_boundary_is_allowed() {
        for range in [
            MemoryRange {
                start: KERNEL_START - 1,
                size: 2,
            },
            MemoryRange {
                start: KERNEL_END - 1,
                size: 1,
            },
        ] {
            assert_eq!(
                validate_memory_ranges(&[RAM], &[range], DTB),
                Err(MemoryError::KernelReserved)
            );
        }
        assert_eq!(
            validate_memory_ranges(
                &[RAM],
                &[MemoryRange {
                    start: KERNEL_END,
                    size: 1
                }],
                DTB
            ),
            Ok(())
        );
    }

    #[test]
    fn duplicate_or_overlapping_declarations_are_rejected() {
        assert_eq!(
            validate_memory_ranges(&[RAM, RAM], &[], DTB),
            Err(MemoryError::OverlappingRam)
        );
        let range = MemoryRange {
            start: 0,
            size: 0x1000,
        };
        assert_eq!(
            validate_memory_ranges(&[RAM], &[range, range], DTB),
            Err(MemoryError::OverlappingReservations)
        );
    }

    #[test]
    fn dtb_placement_and_count_limits_are_enforced() {
        for dtb in [
            MemoryRange { start: 0, ..DTB },
            MemoryRange {
                start: DTB.start + 1,
                ..DTB
            },
            MemoryRange {
                start: KERNEL_START,
                ..DTB
            },
            MemoryRange {
                size: MAX_DTB_SIZE as u64 + 1,
                ..DTB
            },
        ] {
            assert!(validate_memory_ranges(&[RAM], &[], dtb).is_err());
        }
        assert_eq!(
            validate_memory_ranges(&[], &[], DTB),
            Err(MemoryError::Count)
        );
        assert_eq!(
            validate_memory_ranges(&[RAM; MAX_RAM_RANGES + 1], &[], DTB),
            Err(MemoryError::Count)
        );
        assert_eq!(
            validate_memory_ranges(&[RAM], &[DTB; MAX_RESERVATIONS + 1], DTB),
            Err(MemoryError::Count)
        );
    }
}
