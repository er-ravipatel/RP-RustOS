//! D20 pool placement only. Does not allocate or write physical memory.
use crate::{validate_memory_ranges, MemoryError, MemoryRange, MAX_RESERVATIONS};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PoolError {
    Map(MemoryError),
    Size,
    Capacity,
    NoSpace,
}

/// Select the highest 4 KiB aligned pool fitting a single validated RAM bank.
/// Excludes all existing reservations, low memory, the kernel and the full DTB.
/// The caller must retain the returned range as unavailable memory.
pub fn select_cma_pool(
    ram: &[MemoryRange],
    reserved: &[MemoryRange],
    dtb: MemoryRange,
    size: u64,
) -> Result<MemoryRange, PoolError> {
    validate_memory_ranges(ram, reserved, dtb).map_err(PoolError::Map)?;
    if size == 0 || size > crate::BOARD_RAM_CEILING {
        return Err(PoolError::Size);
    }
    if reserved.len() == MAX_RESERVATIONS {
        return Err(PoolError::Capacity);
    }
    let fixed = [
        MemoryRange {
            start: 0,
            size: 0x1000,
        },
        MemoryRange {
            start: crate::KERNEL_START,
            size: crate::KERNEL_END - crate::KERNEL_START,
        },
        dtb,
    ];
    let mut best = None;
    for bank in ram {
        // Every maximal free interval ends at a bank end or an exclusion start.
        for boundary in core::iter::once(bank.start + bank.size)
            .chain(reserved.iter().chain(fixed.iter()).map(|r| r.start))
        {
            let Some(raw) = boundary.checked_sub(size) else {
                continue;
            };
            let start = raw & !0xfff;
            let finish = start + size; // Validated ceiling and subtraction bound this sum.
            if start < bank.start || finish > bank.start + bank.size {
                continue;
            }
            if reserved
                .iter()
                .chain(fixed.iter())
                .any(|r| crate::overlaps(start, finish, r.start, r.start + r.size))
            {
                continue;
            }
            if best.is_none_or(|previous: MemoryRange| start > previous.start) {
                best = Some(MemoryRange { start, size });
            }
        }
    }
    best.ok_or(PoolError::NoSpace)
}

#[cfg(test)]
mod tests {
    use super::*;
    const RAM: MemoryRange = MemoryRange {
        start: 0,
        size: 128 * 1024 * 1024,
    };
    const DTB: MemoryRange = MemoryRange {
        start: 0x1000000,
        size: 33724,
    };
    #[test]
    fn highest_pool_and_order_independence() {
        let a = MemoryRange {
            start: 0x7000000,
            size: 0x1000000,
        };
        let b = MemoryRange {
            start: 0x6000000,
            size: 0x100000,
        };
        let expected = MemoryRange {
            start: 0x2000000,
            size: 0x4000000,
        };
        assert_eq!(
            select_cma_pool(&[RAM], &[a, b], DTB, expected.size),
            Ok(expected)
        );
        assert_eq!(
            select_cma_pool(&[RAM], &[b, a], DTB, expected.size),
            Ok(expected)
        );
        let banks = [
            MemoryRange {
                start: 0,
                size: 0x2000000,
            },
            MemoryRange {
                start: 0x4000000,
                size: 0x4000000,
            },
        ];
        assert_eq!(
            select_cma_pool(&banks, &[], DTB, 0x100000),
            select_cma_pool(&[banks[1], banks[0]], &[], DTB, 0x100000)
        );
    }
    #[test]
    fn avoids_dtb_and_kernel_and_aligns_down() {
        let bank = MemoryRange {
            start: 0,
            size: 0x1100001,
        };
        assert_eq!(
            select_cma_pool(&[bank], &[], DTB, 0x100000),
            Ok(MemoryRange {
                start: 0xf00000,
                size: 0x100000
            })
        );
        let small = MemoryRange {
            start: 0,
            size: 0x400000,
        };
        let low_dtb = MemoryRange {
            start: 0x1000,
            size: 0x1000,
        };
        assert_eq!(
            select_cma_pool(&[small], &[], low_dtb, 0x1ff000),
            Err(PoolError::NoSpace)
        );
    }
    #[test]
    fn rejects_invalid_map_size_and_insufficient_capacity() {
        assert_eq!(select_cma_pool(&[RAM], &[], DTB, 0), Err(PoolError::Size));
        assert_eq!(
            select_cma_pool(&[RAM], &[], DTB, u64::MAX),
            Err(PoolError::Size)
        );
        assert_eq!(
            select_cma_pool(&[RAM], &[], DTB, RAM.size),
            Err(PoolError::NoSpace)
        );
        assert_eq!(
            select_cma_pool(&[], &[], DTB, 1),
            Err(PoolError::Map(MemoryError::Count))
        );
        let mut reservations = [MemoryRange { start: 0, size: 1 }; MAX_RESERVATIONS];
        for (i, r) in reservations.iter_mut().enumerate() {
            r.start = i as u64;
        }
        assert_eq!(
            select_cma_pool(&[RAM], &reservations, DTB, 1),
            Err(PoolError::Capacity)
        );
    }
}
