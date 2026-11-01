//! Bounded, nonrecursive token validation. Does not interpret board/RAM properties.
use crate::{inspect_dtb, BootDataError, DtbLayout};

const MAX_DEPTH: usize = 16;
const MAX_PROPERTIES_PER_NODE: usize = 256;
const MAX_TOKENS: usize = 16_384;
const MAX_NAME_BYTES: usize = 128;

#[derive(Clone, Copy)]
struct Frame {
    // Absolute offsets into this bounded DTB, rather than stack-heavy fat pointers.
    names: [u32; MAX_PROPERTIES_PER_NODE],
    count: usize,
    children_seen: bool,
}
impl Frame {
    const EMPTY: Self = Self {
        names: [0; MAX_PROPERTIES_PER_NODE],
        count: 0,
        children_seen: false,
    };
}

fn next_word(data: &[u8], cursor: &mut usize, end: usize) -> Result<u32, BootDataError> {
    let next = cursor.checked_add(4).ok_or(BootDataError::Structure)?;
    if next > end {
        return Err(BootDataError::Structure);
    }
    let value = u32::from_be_bytes(data[*cursor..next].try_into().unwrap());
    *cursor = next;
    Ok(value)
}

fn pad(data: &[u8], cursor: usize, end: usize) -> Result<usize, BootDataError> {
    let aligned = cursor.checked_add(3).ok_or(BootDataError::Structure)? & !3;
    if aligned > end || data[cursor..aligned].iter().any(|b| *b != 0) {
        return Err(BootDataError::Structure);
    }
    Ok(aligned)
}

/// Validate all tokens/properties in an already-readable, bounded DTB slice.
/// Limits are deliberate M2 policy. Success says nothing about usable ARM RAM.
pub fn validate_structure(data: &[u8], physical_address: u64) -> Result<DtbLayout, BootDataError> {
    visit_properties(data, physical_address, |_, _, _| {})
}

// Properties are exposed only after their local bounds and duplicate checks pass.
// Callers must discard collected state if the complete walk fails.
pub(crate) fn visit_properties(
    data: &[u8],
    physical_address: u64,
    mut property: impl FnMut(usize, &[u8], &[u8]),
) -> Result<DtbLayout, BootDataError> {
    walk(data, physical_address, |event| {
        if let Event::Property(depth, name, value) = event {
            property(depth, name, value);
        }
    })
}

pub(crate) enum Event<'a> {
    Begin(usize, &'a [u8]),
    Property(usize, &'a [u8], &'a [u8]),
    End(usize),
}

pub(crate) fn walk<'a>(
    data: &'a [u8],
    physical_address: u64,
    mut event: impl FnMut(Event<'a>),
) -> Result<DtbLayout, BootDataError> {
    let layout = inspect_dtb(data, physical_address)?;
    let mut frames = [Frame::EMPTY; MAX_DEPTH];
    let mut depth = 0;
    let mut root_seen = false;
    let mut root_closed = false;
    let mut cursor = layout.structure.start;
    let end = layout.structure.end;
    for _ in 0..MAX_TOKENS {
        match next_word(data, &mut cursor, end)? {
            1 => {
                if root_closed {
                    return Err(BootDataError::Structure);
                }
                if depth == MAX_DEPTH {
                    return Err(BootDataError::DepthLimit);
                }
                let remaining = &data[cursor..end];
                let length = remaining
                    .iter()
                    .take(MAX_NAME_BYTES + 1)
                    .position(|b| *b == 0)
                    .ok_or(BootDataError::Structure)?;
                if depth == 0 {
                    if root_seen || length != 0 {
                        return Err(BootDataError::Structure);
                    }
                    root_seen = true;
                } else {
                    if length == 0 {
                        return Err(BootDataError::Structure);
                    }
                    frames[depth - 1].children_seen = true;
                }
                let name = &data[cursor..cursor + length];
                cursor = pad(data, cursor + length + 1, end)?;
                event(Event::Begin(depth, name));
                frames[depth] = Frame::EMPTY;
                depth += 1;
            }
            2 => {
                if depth == 0 {
                    return Err(BootDataError::Structure);
                }
                depth -= 1;
                event(Event::End(depth));
                if depth == 0 {
                    root_closed = true;
                }
            }
            3 => {
                if depth == 0 || frames[depth - 1].children_seen {
                    return Err(BootDataError::Structure);
                }
                let length = next_word(data, &mut cursor, end)? as usize;
                let name_offset = next_word(data, &mut cursor, end)? as usize;
                let name_start = layout
                    .strings
                    .start
                    .checked_add(name_offset)
                    .ok_or(BootDataError::Structure)?;
                if name_start >= layout.strings.end {
                    return Err(BootDataError::Structure);
                }
                let tail = &data[name_start..layout.strings.end];
                let name_len = tail
                    .iter()
                    .take(MAX_NAME_BYTES + 1)
                    .position(|b| *b == 0)
                    .ok_or(BootDataError::Structure)?;
                if name_len == 0 {
                    return Err(BootDataError::Structure);
                }
                let name = &tail[..name_len + 1];
                let frame = &mut frames[depth - 1];
                if frame.names[..frame.count].iter().any(|offset| {
                    let start = *offset as usize;
                    data.get(start..start + name.len()) == Some(name)
                }) {
                    return Err(BootDataError::Structure);
                }
                if frame.count == MAX_PROPERTIES_PER_NODE {
                    return Err(BootDataError::PropertyLimit);
                }
                frame.names[frame.count] = name_start as u32;
                frame.count += 1;
                let value_start = cursor;
                cursor = cursor.checked_add(length).ok_or(BootDataError::Structure)?;
                if cursor > end {
                    return Err(BootDataError::Structure);
                }
                let padded = pad(data, cursor, end)?;
                event(Event::Property(
                    depth - 1,
                    &name[..name_len],
                    &data[value_start..cursor],
                ));
                cursor = padded;
            }
            4 => {} // FDT_NOP
            9 if root_seen && root_closed && depth == 0 && cursor == end => return Ok(layout),
            _ => return Err(BootDataError::Structure),
        }
    }
    Err(BootDataError::Structure)
}

#[cfg(test)]
mod tests {
    use super::*;
    extern crate std;
    use std::vec::Vec;

    fn blob(tokens: &[u32], strings: &[u8]) -> Vec<u8> {
        let mut data = std::vec![0; 56 + tokens.len() * 4 + strings.len()];
        let length = data.len() as u32;
        for (offset, value) in [
            (0, 0xd00d_feed),
            (4, length),
            (8, 56),
            (12, 56 + tokens.len() as u32 * 4),
            (16, 40),
            (20, 17),
            (24, 16),
            (32, strings.len() as u32),
            (36, tokens.len() as u32 * 4),
        ] {
            data[offset..offset + 4].copy_from_slice(&value.to_be_bytes());
        }
        for (index, token) in tokens.iter().enumerate() {
            data[56 + index * 4..60 + index * 4].copy_from_slice(&token.to_be_bytes());
        }
        let start = 56 + tokens.len() * 4;
        data[start..].copy_from_slice(strings);
        data
    }
    fn check(tokens: &[u32], strings: &[u8]) -> Result<DtbLayout, BootDataError> {
        validate_structure(&blob(tokens, strings), 0x100_0000)
    }

    #[test]
    fn minimal_and_nested_tree_with_property() {
        assert!(check(&[1, 0, 2, 9], b"\0").is_ok());
        assert!(check(&[4, 1, 0, 3, 4, 0, 42, 1, 0x7800_0000, 2, 2, 9], b"value\0").is_ok());
    }
    #[test]
    fn board_requires_root_property_and_complete_valid_tree() {
        use crate::{validate_board, BoardError};
        let valid = [
            1,
            0,
            3,
            25,
            0,
            0x7261_7370,
            0x6265_7272,
            0x7970_692c,
            0x6d6f_6465,
            0x6c2d_7a65,
            0x726f_2d32,
            0x2d77_0000,
            2,
            9,
        ];
        let data = blob(&valid, b"compatible\0");
        // Exact compatible string is 27 bytes including its terminator.
        let mut data = data;
        data[68..72].copy_from_slice(&27_u32.to_be_bytes());
        assert!(validate_board(&data, 0x100_0000).is_ok());
        let mut broken = data.clone();
        let end = 56 + valid.len() * 4;
        broken[end - 4..end].copy_from_slice(&5_u32.to_be_bytes());
        assert_eq!(
            validate_board(&broken, 0x100_0000),
            Err(BoardError::Structure(BootDataError::Structure))
        );
        assert_eq!(
            validate_board(&blob(&[1, 0, 2, 9], b"\0"), 0x100_0000),
            Err(BoardError::MissingCompatible)
        );
    }
    #[test]
    fn hierarchy_termination_and_unknown_tokens_fail() {
        for tokens in [
            &[2, 9][..],
            &[1, 0, 9],
            &[1, 0, 2, 9, 4],
            &[1, 0, 2, 1, 0, 2, 9],
            &[1, 0, 5, 2, 9],
            &[3, 0, 0, 9],
        ] {
            assert!(check(tokens, b"x\0").is_err());
        }
    }
    #[test]
    fn duplicate_property_and_property_after_child_fail() {
        assert!(check(&[1, 0, 3, 0, 0, 3, 0, 0, 2, 9], b"x\0").is_err());
        assert!(check(&[1, 0, 1, 0x7800_0000, 2, 3, 0, 0, 2, 9], b"x\0").is_err());
    }
    #[test]
    fn malformed_names_lengths_and_padding_fail() {
        assert!(check(&[1, 0, 3, 0, 2, 2, 9], b"x\0").is_err());
        assert!(check(&[1, 0, 3, 0, 0, 2, 9], b"unterminated").is_err());
        assert!(check(&[1, 0, 3, u32::MAX, 0, 2, 9], b"x\0").is_err());
        assert!(check(&[1, 0x0000_0001, 2, 9], b"\0").is_err());
    }
    #[test]
    fn nesting_is_bounded_without_recursion() {
        let mut tokens = std::vec![1, 0];
        for _ in 0..MAX_DEPTH {
            tokens.extend([1, 0x7800_0000]);
        }
        assert_eq!(check(&tokens, b"\0"), Err(BootDataError::DepthLimit));
    }

    #[test]
    fn symbol_sized_nodes_pass_and_property_limit_still_holds() {
        for count in [160, MAX_PROPERTIES_PER_NODE, MAX_PROPERTIES_PER_NODE + 1] {
            let mut tokens = std::vec![1, 0];
            let mut strings = Vec::new();
            for i in 0..count {
                tokens.extend([3, 0, strings.len() as u32]);
                strings.extend(std::format!("property{i}\0").as_bytes());
            }
            tokens.extend([2, 9]);
            if count <= MAX_PROPERTIES_PER_NODE {
                assert!(check(&tokens, &strings).is_ok());
            } else {
                assert_eq!(check(&tokens, &strings), Err(BootDataError::PropertyLimit));
            }
        }
        assert!(core::mem::size_of::<Frame>() * MAX_DEPTH < 20 * 1024);
    }

    #[test]
    fn duplicate_property_names_at_different_string_offsets_fail() {
        assert!(check(&[1, 0, 3, 0, 0, 3, 0, 2, 2, 9], b"x\0x\0").is_err());
    }
}
