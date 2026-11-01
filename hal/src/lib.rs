#![no_std]

/// Bounded console operations; callers must not emit success after an error.
pub trait Console: core::fmt::Write {
    fn flush(&mut self) -> Result<(), ConsoleError>;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsoleError {
    Timeout,
}

pub struct ConsoleConfig {
    pub base: usize,
    pub integer_divisor: u32,
    pub fractional_divisor: u32,
}
