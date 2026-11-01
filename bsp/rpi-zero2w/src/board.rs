//! Board identification only; this does not validate firmware memory declarations.
use crate::{structure::visit_properties, BootDataError, DtbLayout};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BoardError {
    Structure(BootDataError),
    MissingCompatible,
    MalformedCompatible,
    WrongBoard,
}

fn compatible(value: &[u8]) -> Result<(), BoardError> {
    if value.is_empty() || value.last() != Some(&0) {
        return Err(BoardError::MalformedCompatible);
    }
    let mut found = false;
    for entry in value[..value.len() - 1].split(|byte| *byte == 0) {
        if entry.is_empty() || !entry.iter().all(|byte| (0x20..=0x7e).contains(byte)) {
            return Err(BoardError::MalformedCompatible);
        }
        found |= entry == b"raspberrypi,model-zero-2-w";
    }
    if found {
        Ok(())
    } else {
        Err(BoardError::WrongBoard)
    }
}

/// Validate the entire bounded tree and its exact root board compatibility.
/// A successful result is not permission to write RAM or start the kernel.
pub fn validate_board(data: &[u8], physical_address: u64) -> Result<DtbLayout, BoardError> {
    let mut board = Err(BoardError::MissingCompatible);
    let layout = visit_properties(data, physical_address, |depth, name, value| {
        if depth == 0 && name == b"compatible" {
            board = compatible(value);
        }
    })
    .map_err(BoardError::Structure)?;
    board?;
    Ok(layout)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_board_in_string_list() {
        assert_eq!(
            compatible(b"raspberrypi,model-zero-2-w\0brcm,bcm2837\0"),
            Ok(())
        );
        assert_eq!(
            compatible(b"brcm,bcm2837\0raspberrypi,model-zero-2-w\0"),
            Ok(())
        );
        assert_eq!(
            compatible(b"raspberrypi,model-zero-2-w-extra\0"),
            Err(BoardError::WrongBoard)
        );
        assert_eq!(
            compatible(b"raspberrypi,5-model-b\0"),
            Err(BoardError::WrongBoard)
        );
    }

    #[test]
    fn malformed_list_rejected_even_after_matching_board() {
        for value in [
            b"".as_slice(),
            b"raspberrypi,model-zero-2-w",
            b"\0",
            b"raspberrypi,model-zero-2-w\0\0",
            b"raspberrypi,model-zero-2-w\0bad\xff\0",
        ] {
            assert_eq!(compatible(value), Err(BoardError::MalformedCompatible));
        }
    }
}
