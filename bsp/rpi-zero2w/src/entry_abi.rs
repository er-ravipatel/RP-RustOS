//! Explicit D21 interface. Entry must prove readable DTB and private stack first.
use crate::{inspect_boot_memory, MAX_DTB_SIZE};

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BootMemoryResult {
    /// Zero/zero means there was no dynamic pool request.
    pub cma_base: u64,
    pub cma_size: u64,
}

/// Validate firmware data without BSS, logging or heap allocation.
/// Returns zero on success, one on rejected input. Output is untouched on failure.
///
/// # Safety
/// Caller must already prove `ptr..ptr+len` is readable, initialized, immutable
/// and directly mapped at its numeric physical address. `out` must be aligned,
/// writable for one result, inside the proven private stack, and disjoint from
/// the DTB. No other core may mutate either region. CPU/stack setup must satisfy
/// AAPCS64. These obligations cannot be established by this function itself.
#[no_mangle]
pub unsafe extern "C" fn rustos_validate_boot_memory(
    ptr: *const u8,
    len: usize,
    out: *mut BootMemoryResult,
) -> u32 {
    if !(40..=MAX_DTB_SIZE).contains(&len) {
        return 1;
    }
    // SAFETY: the assembly caller establishes the readable immutable extent.
    let data = unsafe { core::slice::from_raw_parts(ptr, len) };
    let Ok(info) = inspect_boot_memory(data, ptr as u64) else {
        return 1;
    };
    let result = match info.cma_pool {
        Some(pool) => BootMemoryResult {
            cma_base: pool.start,
            cma_size: pool.size,
        },
        None => BootMemoryResult {
            cma_base: 0,
            cma_size: 0,
        },
    };
    // SAFETY: caller provides a distinct aligned writable private stack buffer.
    unsafe { out.write(result) };
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejected_header_preserves_output_and_guards() {
        #[repr(C)]
        struct Guarded {
            before: u64,
            result: BootMemoryResult,
            after: u64,
        }
        let mut guarded = Guarded {
            before: 0x1234,
            result: BootMemoryResult {
                cma_base: 0x5678,
                cma_size: 0x9abc,
            },
            after: 0xdef0,
        };
        let bytes = [0u8; 40];
        let status = unsafe {
            rustos_validate_boot_memory(bytes.as_ptr(), bytes.len(), &mut guarded.result)
        };
        assert_eq!(status, 1);
        assert_eq!(
            (
                guarded.before,
                guarded.result.cma_base,
                guarded.result.cma_size,
                guarded.after
            ),
            (0x1234, 0x5678, 0x9abc, 0xdef0)
        );
        assert_eq!(core::mem::size_of::<BootMemoryResult>(), 16);
    }
}
