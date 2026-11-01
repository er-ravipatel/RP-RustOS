//! Conservative extraction from an already-readable DTB; no physical writes.
use crate::memory::MAX_RAM_RANGES;
use crate::structure::{walk, Event};
use crate::{
    decode_reg, validate_board, validate_memory_ranges, BoardError, MemoryError, MemoryRange,
    MAX_RESERVATIONS,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BootMemoryError {
    Board(BoardError),
    Cells,
    Node,
    Status,
    ReservedMapping,
    DynamicReservation,
    Ranges(MemoryError),
    Pool(crate::PoolError),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BootMemoryInfo {
    /// Reserved and unavailable even though M2 has no DMA consumer.
    pub cma_pool: Option<MemoryRange>,
}

#[derive(Clone, Copy, Default)]
struct Node<'a> {
    memory: bool,
    reservation: bool,
    reg: Option<&'a [u8]>,
    device_type: Option<&'a [u8]>,
    status: Option<&'a [u8]>,
    dynamic: bool,
    no_map: bool,
    reusable: bool,
    cma_name: bool,
    cma_compatible: bool,
    cma_default: bool,
    cma_size: Option<&'a [u8]>,
    cma_unsupported: bool,
}

fn cells(value: &[u8]) -> Result<u32, BootMemoryError> {
    let bytes: [u8; 4] = value.try_into().map_err(|_| BootMemoryError::Cells)?;
    match u32::from_be_bytes(bytes) {
        n @ 1..=2 => Ok(n),
        _ => Err(BootMemoryError::Cells),
    }
}

fn active(status: Option<&[u8]>) -> Result<bool, BootMemoryError> {
    match status {
        None | Some(b"okay\0") | Some(b"ok\0") => Ok(true),
        Some(b"disabled\0") => Ok(false),
        _ => Err(BootMemoryError::Status),
    }
}

/// Check board identity, explicit root cells, RAM and static reservations together.
/// Only the narrowly approved D20 CMA request is supported dynamically.
/// This Rust function requires a safe stack and does not solve stackless entry.
pub fn validate_boot_memory(data: &[u8], physical_address: u64) -> Result<(), BootMemoryError> {
    inspect_boot_memory(data, physical_address).map(|_| ())
}

/// Return the selected reserved pool after complete memory validation.
pub fn inspect_boot_memory(
    data: &[u8],
    physical_address: u64,
) -> Result<BootMemoryInfo, BootMemoryError> {
    let layout = validate_board(data, physical_address).map_err(BootMemoryError::Board)?;
    let empty = MemoryRange { start: 0, size: 0 };
    let mut ram = [empty; MAX_RAM_RANGES];
    let mut reserved = [empty; MAX_RESERVATIONS];
    let (mut ram_count, mut reserved_count) = (0, 0);
    let (mut addresses, mut sizes) = (None, None);
    let (mut reserved_addresses, mut reserved_sizes) = (None, None);
    let (mut reserved_parent, mut reserved_seen, mut mapping) = (false, false, false);
    let mut nodes = [Node::default(); 16];
    let mut result = Ok(());
    let mut cma_size = None;
    walk(data, physical_address, |event| {
        if result.is_err() {
            return;
        }
        result = (|| {
            match event {
                Event::Begin(depth, name) => {
                    if depth == 1 {
                        reserved_parent = name == b"reserved-memory";
                        if reserved_parent {
                            if reserved_seen {
                                return Err(BootMemoryError::Node);
                            }
                            reserved_seen = true;
                        }
                    }
                    if depth > 0 && (nodes[depth - 1].reservation || nodes[depth - 1].memory) {
                        return Err(BootMemoryError::Node);
                    }
                    nodes[depth] = Node {
                        memory: depth == 1 && (name == b"memory" || name.starts_with(b"memory@")),
                        reservation: depth == 2 && reserved_parent,
                        cma_name: depth == 2 && reserved_parent && name == b"linux,cma",
                        ..Node::default()
                    };
                }
                Event::Property(depth, name, value) => {
                    if depth == 0 {
                        match name {
                            b"#address-cells" => addresses = Some(cells(value)?),
                            b"#size-cells" => sizes = Some(cells(value)?),
                            _ => {}
                        }
                    } else if depth == 1 && reserved_parent {
                        match name {
                            b"#address-cells" => reserved_addresses = Some(cells(value)?),
                            b"#size-cells" => reserved_sizes = Some(cells(value)?),
                            b"ranges" if value.is_empty() => mapping = true,
                            b"ranges" | b"status" => return Err(BootMemoryError::ReservedMapping),
                            _ => {}
                        }
                    } else {
                        let node = &mut nodes[depth];
                        if node.reservation {
                            match name {
                                b"compatible" => {
                                    node.cma_compatible = value == b"shared-dma-pool\0"
                                }
                                b"linux,cma-default" if value.is_empty() => node.cma_default = true,
                                b"size" => node.cma_size = Some(value),
                                b"phandle"
                                    if value.len() == 4
                                        && value != [0; 4]
                                        && value != [0xff; 4] => {}
                                b"reusable" | b"no-map" | b"reg" | b"status" => {}
                                _ => node.cma_unsupported = true,
                            }
                        }
                        match name {
                            b"reg" => node.reg = Some(value),
                            b"device_type" => node.device_type = Some(value),
                            b"status" => node.status = Some(value),
                            b"size" | b"alignment" | b"alloc-ranges" => node.dynamic = true,
                            b"no-map" if value.is_empty() => node.no_map = true,
                            b"reusable" if value.is_empty() => node.reusable = true,
                            b"no-map" | b"reusable" if node.reservation => {
                                return Err(BootMemoryError::Node)
                            }
                            _ => {}
                        }
                    }
                }
                Event::End(depth) => {
                    let node = nodes[depth];
                    if node.memory
                        || node.reservation
                        || (depth == 1 && node.device_type == Some(b"memory\0"))
                    {
                        if !active(node.status)? {
                            return Ok(());
                        }
                        if node.memory && node.device_type != Some(b"memory\0") {
                            return Err(BootMemoryError::Node);
                        }
                        if !node.memory && !node.reservation {
                            return Err(BootMemoryError::Node);
                        }
                        if node.reservation && node.dynamic {
                            let s = sizes.ok_or(BootMemoryError::Cells)?;
                            if !node.cma_name
                                || !node.cma_compatible
                                || !node.cma_default
                                || !node.reusable
                                || node.no_map
                                || node.reg.is_some()
                                || node.cma_unsupported
                                || cma_size.is_some()
                                || !mapping
                                || reserved_addresses != addresses
                                || reserved_sizes != sizes
                            {
                                return Err(BootMemoryError::DynamicReservation);
                            }
                            let value = node.cma_size.ok_or(BootMemoryError::DynamicReservation)?;
                            if value.len() != s as usize * 4 {
                                return Err(BootMemoryError::DynamicReservation);
                            }
                            let size = value
                                .iter()
                                .fold(0_u64, |acc, byte| (acc << 8) | u64::from(*byte));
                            if size == 0 || size > crate::BOARD_RAM_CEILING {
                                return Err(BootMemoryError::DynamicReservation);
                            }
                            cma_size = Some(size);
                            return Ok(());
                        }
                        if node.no_map && node.reusable {
                            return Err(BootMemoryError::Node);
                        }
                        let reg = node.reg.ok_or(BootMemoryError::Node)?;
                        let a = addresses.ok_or(BootMemoryError::Cells)?;
                        let s = sizes.ok_or(BootMemoryError::Cells)?;
                        if node.reservation {
                            if !mapping
                                || reserved_addresses != Some(a)
                                || reserved_sizes != Some(s)
                            {
                                return Err(BootMemoryError::ReservedMapping);
                            }
                            reserved_count +=
                                decode_reg(reg, a, s, &mut reserved[reserved_count..])
                                    .map_err(BootMemoryError::Ranges)?
                                    .len();
                        } else {
                            ram_count += decode_reg(reg, a, s, &mut ram[ram_count..])
                                .map_err(BootMemoryError::Ranges)?
                                .len();
                        }
                    }
                    if depth == 1 && reserved_parent {
                        if !mapping || reserved_addresses != addresses || reserved_sizes != sizes {
                            return Err(BootMemoryError::ReservedMapping);
                        }
                        reserved_parent = false;
                    }
                }
            }
            Ok(())
        })();
    })
    .map_err(|error| BootMemoryError::Board(BoardError::Structure(error)))?;
    result?;
    if addresses.is_none() || sizes.is_none() {
        return Err(BootMemoryError::Cells);
    }
    let map = crate::word(data, 16).map_err(|e| BootMemoryError::Board(BoardError::Structure(e)))?
        as usize;
    for index in 0..layout.reservation_count {
        let (start, size) = crate::reservation(data, map + index * 16);
        if size == 0 {
            continue;
        }
        if reserved_count == MAX_RESERVATIONS {
            return Err(BootMemoryError::Ranges(MemoryError::Count));
        }
        reserved[reserved_count] = MemoryRange { start, size };
        reserved_count += 1;
    }
    let dtb = MemoryRange {
        start: physical_address,
        size: layout.total_size as u64,
    };
    let pool = cma_size
        .map(|size| {
            crate::select_cma_pool(&ram[..ram_count], &reserved[..reserved_count], dtb, size)
        })
        .transpose()
        .map_err(BootMemoryError::Pool)?;
    if let Some(pool) = pool {
        reserved[reserved_count] = pool; // Selector already enforces remaining capacity.
        reserved_count += 1;
    }
    validate_memory_ranges(
        &ram[..ram_count],
        &reserved[..reserved_count],
        MemoryRange {
            start: physical_address,
            size: layout.total_size as u64,
        },
    )
    .map_err(BootMemoryError::Ranges)?;
    Ok(BootMemoryInfo { cma_pool: pool })
}

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;
    use std::vec::Vec;

    struct Tree {
        tokens: Vec<u8>,
        strings: Vec<u8>,
    }
    impl Tree {
        fn word(&mut self, value: u32) {
            self.tokens.extend_from_slice(&value.to_be_bytes());
        }
        fn begin(&mut self, name: &[u8]) {
            self.word(1);
            self.tokens.extend_from_slice(name);
            self.tokens.push(0);
            while self.tokens.len() % 4 != 0 {
                self.tokens.push(0);
            }
        }
        fn prop(&mut self, name: &[u8], value: &[u8]) {
            let offset = self.strings.len() as u32;
            self.strings.extend_from_slice(name);
            self.strings.push(0);
            self.word(3);
            self.word(value.len() as u32);
            self.word(offset);
            self.tokens.extend_from_slice(value);
            while self.tokens.len() % 4 != 0 {
                self.tokens.push(0);
            }
        }
        fn finish(mut self, header_reserved: bool) -> Vec<u8> {
            self.word(2);
            self.word(9);
            let start = if header_reserved { 72 } else { 56 };
            let mut data = std::vec![0; start];
            for (offset, value) in [
                (0, 0xd00d_feed),
                (4, (start + self.tokens.len() + self.strings.len()) as u32),
                (8, start as u32),
                (12, (start + self.tokens.len()) as u32),
                (16, 40),
                (20, 17),
                (24, 16),
                (32, self.strings.len() as u32),
                (36, self.tokens.len() as u32),
            ] {
                data[offset..offset + 4].copy_from_slice(&value.to_be_bytes());
            }
            if header_reserved {
                data[48..56].copy_from_slice(&0x1000_u64.to_be_bytes());
            }
            data.extend(self.tokens);
            data.extend(self.strings);
            data
        }
    }
    fn fixture(
        size: u32,
        reservation: Option<u32>,
        dynamic: bool,
        disabled: bool,
        header: bool,
    ) -> Vec<u8> {
        let mut t = Tree {
            tokens: Vec::new(),
            strings: Vec::new(),
        };
        t.begin(b"");
        t.prop(b"compatible", b"raspberrypi,model-zero-2-w\0");
        t.prop(b"#address-cells", &1_u32.to_be_bytes());
        t.prop(b"#size-cells", &1_u32.to_be_bytes());
        t.begin(b"memory@0");
        t.prop(b"device_type", b"memory\0");
        let mut reg = [0; 8];
        reg[4..].copy_from_slice(&size.to_be_bytes());
        t.prop(b"reg", &reg);
        if disabled {
            t.prop(b"status", b"disabled\0");
        }
        t.word(2);
        if let Some(address) = reservation {
            t.begin(b"reserved-memory");
            t.prop(b"#address-cells", &1_u32.to_be_bytes());
            t.prop(b"#size-cells", &1_u32.to_be_bytes());
            t.prop(b"ranges", b"");
            t.begin(b"region");
            if dynamic {
                t.prop(b"size", &0x1000_u32.to_be_bytes());
            } else {
                reg[..4].copy_from_slice(&address.to_be_bytes());
                reg[4..].copy_from_slice(&0x1000_u32.to_be_bytes());
                t.prop(b"reg", &reg);
            }
            t.word(2);
            t.word(2);
        }
        t.finish(header)
    }
    #[test]
    fn complete_synthetic_firmware_tree_and_header_reservation() {
        assert_eq!(
            validate_boot_memory(
                &fixture(0x800_0000, Some(0x1000), false, false, true),
                0x100_0000
            ),
            Ok(())
        );
    }
    #[test]
    fn kernel_and_dtb_must_fit_runtime_ram() {
        assert_eq!(
            validate_boot_memory(&fixture(0x300000, None, false, false, false), 0x1000000),
            Err(BootMemoryError::Ranges(MemoryError::KernelNotInRam))
        );
        assert_eq!(
            validate_boot_memory(&fixture(0x800000, None, false, false, false), 0x1000000),
            Err(BootMemoryError::Ranges(MemoryError::DtbNotInRam))
        );
        assert_eq!(
            validate_boot_memory(&fixture(0, None, false, false, false), 0x1000000),
            Err(BootMemoryError::Ranges(MemoryError::Empty))
        );
    }
    #[test]
    fn reservations_and_disabled_ram_fail_closed() {
        assert_eq!(
            validate_boot_memory(
                &fixture(0x8000000, Some(0x200000), false, false, false),
                0x1000000
            ),
            Err(BootMemoryError::Ranges(MemoryError::KernelReserved))
        );
        assert_eq!(
            validate_boot_memory(&fixture(0x8000000, Some(0), true, false, false), 0x1000000),
            Err(BootMemoryError::DynamicReservation)
        );
        assert_eq!(
            validate_boot_memory(&fixture(0x8000000, None, false, true, false), 0x1000000),
            Err(BootMemoryError::Ranges(MemoryError::Count))
        );
    }
    #[test]
    fn overlapping_header_and_tree_reservations_are_rejected() {
        assert_eq!(
            validate_boot_memory(&fixture(0x8000000, Some(0), false, false, true), 0x1000000),
            Err(BootMemoryError::Ranges(
                MemoryError::OverlappingReservations
            ))
        );
    }
    #[test]
    fn unsupported_status_and_missing_cells_are_rejected() {
        let mut data = fixture(0x8000000, None, false, true, false);
        let status = data.windows(9).position(|b| b == b"disabled\0").unwrap();
        data[status..status + 9].copy_from_slice(b"unknown!\0");
        assert_eq!(
            validate_boot_memory(&data, 0x1000000),
            Err(BootMemoryError::Status)
        );
        let mut t = Tree {
            tokens: Vec::new(),
            strings: Vec::new(),
        };
        t.begin(b"");
        t.prop(b"compatible", b"raspberrypi,model-zero-2-w\0");
        assert_eq!(
            validate_boot_memory(&t.finish(false), 0x1000000),
            Err(BootMemoryError::Cells)
        );
    }

    fn cma_fixture(
        extra: Option<(&[u8], &[u8])>,
        omit_reusable: bool,
        name: &[u8],
        pool_size: u32,
    ) -> Vec<u8> {
        let mut t = Tree {
            tokens: Vec::new(),
            strings: Vec::new(),
        };
        t.begin(b"");
        t.prop(b"compatible", b"raspberrypi,model-zero-2-w\0");
        t.prop(b"#address-cells", &1_u32.to_be_bytes());
        t.prop(b"#size-cells", &1_u32.to_be_bytes());
        t.begin(b"reserved-memory");
        t.prop(b"#address-cells", &1_u32.to_be_bytes());
        t.prop(b"#size-cells", &1_u32.to_be_bytes());
        t.prop(b"ranges", b"");
        t.begin(name);
        t.prop(b"compatible", b"shared-dma-pool\0");
        t.prop(b"size", &pool_size.to_be_bytes());
        t.prop(b"linux,cma-default", b"");
        if !omit_reusable {
            t.prop(b"reusable", b"");
        }
        if let Some((name, value)) = extra {
            t.prop(name, value);
        }
        t.word(2);
        t.word(2);
        t.begin(b"memory@0");
        t.prop(b"device_type", b"memory\0");
        t.prop(b"reg", &[0, 0, 0, 0, 8, 0, 0, 0]);
        t.word(2);
        t.finish(true)
    }

    #[test]
    fn approved_cma_request_returns_reserved_pool_after_all_ram_is_collected() {
        let data = cma_fixture(
            Some((b"phandle", &[0, 0, 0, 61])),
            false,
            b"linux,cma",
            0x4000000,
        );
        assert_eq!(
            inspect_boot_memory(&data, 0x1000000),
            Ok(BootMemoryInfo {
                cma_pool: Some(MemoryRange {
                    start: 0x4000000,
                    size: 0x4000000
                })
            })
        );
        assert_eq!(validate_boot_memory(&data, 0x1000000), Ok(()));
    }

    #[test]
    fn unknown_cma_constraints_and_properties_fail() {
        for (name, value) in [
            (b"alignment".as_slice(), &[0, 0, 16, 0][..]),
            (b"alloc-ranges", &[0; 8][..]),
            (b"no-map", &[][..]),
            (b"vendor,unknown", &[][..]),
            (b"phandle", &[0; 4][..]),
            (b"reg", &[0; 8][..]),
        ] {
            assert!(inspect_boot_memory(
                &cma_fixture(Some((name, value)), false, b"linux,cma", 0x4000000),
                0x1000000
            )
            .is_err());
        }
        assert_eq!(
            inspect_boot_memory(&cma_fixture(None, true, b"linux,cma", 0x4000000), 0x1000000),
            Err(BootMemoryError::DynamicReservation)
        );
        assert_eq!(
            inspect_boot_memory(
                &cma_fixture(None, false, b"other-pool", 0x4000000),
                0x1000000
            ),
            Err(BootMemoryError::DynamicReservation)
        );
    }

    #[test]
    fn cma_zero_and_no_space_requests_fail() {
        assert_eq!(
            inspect_boot_memory(&cma_fixture(None, false, b"linux,cma", 0), 0x1000000),
            Err(BootMemoryError::DynamicReservation)
        );
        assert_eq!(
            inspect_boot_memory(
                &cma_fixture(None, false, b"linux,cma", 0x8000000),
                0x1000000
            ),
            Err(BootMemoryError::Pool(crate::PoolError::NoSpace))
        );
    }
}
