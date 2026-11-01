//! D22 board preparation. Only the exclusive primary core may call this.
use crate::{
    mailbox::{Budget, MailboxError},
    uart_clock::{Registers, TIMER_CLO},
};

pub const GPIO_BASE: usize = 0x3f20_0000;
pub const UART_BASE: usize = 0x3f20_1000;

fn idle(registers: &mut impl Registers) -> Result<(), MailboxError> {
    let mut budget = Budget::new(registers.read(TIMER_CLO));
    loop {
        budget.poll(registers.read(TIMER_CLO))?;
        if registers.read(UART_BASE + 0x18) & (1 << 3) == 0 {
            return Ok(());
        }
    }
}

/// Finish inherited TX, then disable UART/DMA/interrupts before pin/clock changes.
pub fn quiesce(registers: &mut impl Registers) -> Result<(), MailboxError> {
    registers.barrier();
    idle(registers)?;
    registers.write(UART_BASE + 0x30, 0);
    registers.write(UART_BASE + 0x48, 0);
    registers.write(UART_BASE + 0x38, 0);
    registers.write(UART_BASE + 0x44, 0x7ff);
    registers.barrier();
    idle(registers)
}

fn pull_delay(registers: &mut impl Registers) -> Result<(), MailboxError> {
    let start = registers.read(TIMER_CLO);
    let mut budget = Budget::new(start);
    loop {
        let now = registers.read(TIMER_CLO);
        budget.poll(now)?;
        if now.wrapping_sub(start) >= 150 {
            return Ok(());
        }
    }
}

/// UART must already be quiescent. Configure only owned diagnostic/BT UART pins.
/// Call before enabling PL011; failure must park without enabling transmission.
pub fn route_tx(registers: &mut impl Registers) -> Result<(), MailboxError> {
    registers.barrier();
    let bt = registers.read(GPIO_BASE + 0x0c);
    registers.write(GPIO_BASE + 0x0c, bt & !0xfff); // GPIO30-33 inputs.
    let pins = registers.read(GPIO_BASE + 0x04);
    registers.write(
        GPIO_BASE + 0x04,
        (pins & !((7 << 12) | (7 << 15))) | (4 << 12),
    ); // TX14 ALT0, RX15 input.
    registers.write(GPIO_BASE + 0x94, 0);
    registers.barrier();
    pull_delay(registers)?;
    registers.write(GPIO_BASE + 0x98, 1 << 14);
    registers.barrier();
    let hold = pull_delay(registers);
    // Always release the pull clock even when the timer stops during the hold.
    registers.write(GPIO_BASE + 0x94, 0);
    registers.write(GPIO_BASE + 0x98, 0);
    registers.barrier();
    hold
}

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;
    use std::vec::Vec;
    struct Mock {
        now: u32,
        step: u32,
        busy: bool,
        writes: Vec<(usize, u32)>,
        reads: usize,
        freeze_at: Option<u32>,
    }
    impl Registers for Mock {
        fn read(&mut self, address: usize) -> u32 {
            self.reads += 1;
            match address {
                TIMER_CLO => {
                    if self.freeze_at.is_none_or(|limit| self.now < limit) {
                        self.now = self.now.wrapping_add(self.step);
                    }
                    self.now
                }
                a if a == UART_BASE + 0x18 => {
                    if self.busy {
                        8
                    } else {
                        0
                    }
                }
                a if a == GPIO_BASE + 4 || a == GPIO_BASE + 12 => u32::MAX,
                _ => panic!("unexpected register read"),
            }
        }
        fn write(&mut self, address: usize, value: u32) {
            self.writes.push((address, value));
        }
        fn barrier(&mut self) {}
    }
    fn mock() -> Mock {
        Mock {
            now: 0,
            step: 50,
            busy: false,
            writes: Vec::new(),
            reads: 0,
            freeze_at: None,
        }
    }

    #[test]
    fn disable_sequence_and_owned_gpio_fields() {
        let mut io = mock();
        quiesce(&mut io).unwrap();
        route_tx(&mut io).unwrap();
        assert_eq!(
            &io.writes[..4],
            &[
                (UART_BASE + 0x30, 0),
                (UART_BASE + 0x48, 0),
                (UART_BASE + 0x38, 0),
                (UART_BASE + 0x44, 0x7ff)
            ]
        );
        assert_eq!(
            &io.writes[4..],
            &[
                (GPIO_BASE + 12, u32::MAX & !0xfff),
                (
                    GPIO_BASE + 4,
                    (u32::MAX & !((7 << 12) | (7 << 15))) | (4 << 12)
                ),
                (GPIO_BASE + 0x94, 0),
                (GPIO_BASE + 0x98, 1 << 14),
                (GPIO_BASE + 0x94, 0),
                (GPIO_BASE + 0x98, 0)
            ]
        );
        assert!(io.now >= 300);
    }

    #[test]
    fn stuck_uart_or_timer_never_enables_tx() {
        let mut io = mock();
        io.busy = true;
        assert_eq!(quiesce(&mut io), Err(MailboxError::Timeout));
        assert!(io.writes.is_empty());
        let mut io = mock();
        io.step = 0;
        assert_eq!(route_tx(&mut io), Err(MailboxError::Timeout));
        assert!(!io.writes.contains(&(GPIO_BASE + 0x98, 1 << 14)));
        assert!(!io
            .writes
            .iter()
            .any(|(address, value)| *address == UART_BASE + 0x30 && *value != 0));
    }

    #[test]
    fn hold_timeout_releases_pull_clock() {
        let mut io = mock();
        io.freeze_at = Some(250);
        assert_eq!(route_tx(&mut io), Err(MailboxError::Timeout));
        assert!(io.writes.contains(&(GPIO_BASE + 0x98, 1 << 14)));
        assert_eq!(
            &io.writes[io.writes.len() - 2..],
            &[(GPIO_BASE + 0x94, 0), (GPIO_BASE + 0x98, 0)]
        );
    }
}
