//! D22 wire formats and bounds. These pure helpers do not submit MMIO requests.
//! A message copy is not the lifetime-long firmware-owned allocation.

pub const BUFFER_BYTES: u64 = 64;
pub const UART_CLOCK_ID: u32 = 2;
pub const REQUESTED_HZ: u32 = 48_000_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ClockOperation {
    Enable,
    SetRate,
    MeasuredRate,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MailboxError {
    Address,
    Layout,
    Firmware,
    Tag,
    Clock,
    Timeout,
    AlreadyUsed,
}

impl ClockOperation {
    fn layout(self) -> (u32, u32, usize) {
        match self {
            Self::Enable => (0x0003_8001, 8, 7),
            Self::SetRate => (0x0003_8002, 12, 8),
            Self::MeasuredRate => (0x0003_0047, 8, 7),
        }
    }

    pub fn request(self) -> [u32; 16] {
        let (tag, capacity, end) = self.layout();
        let mut words = [0; 16];
        words[0] = ((end + 1) * 4) as u32;
        words[2] = tag;
        words[3] = capacity;
        words[4] = if self == Self::MeasuredRate {
            4
        } else {
            capacity
        };
        words[5] = UART_CLOCK_ID;
        words[6] = match self {
            Self::Enable => 1,
            Self::SetRate => REQUESTED_HZ,
            Self::MeasuredRate => 0,
        };
        if self == Self::SetRate {
            words[7] = 1; // Skip changing turbo settings.
        }
        words
    }

    /// Parse a volatile snapshot taken only after correlated completion/barrier.
    /// Returns state=1 for Enable; Hz for the two rate operations.
    pub fn response(self, words: &[u32; 16]) -> Result<u32, MailboxError> {
        let (tag, capacity, end) = self.layout();
        if words[0] != ((end + 1) * 4) as u32 || words[end] != 0 {
            return Err(MailboxError::Layout);
        }
        if words[1] != 0x8000_0000 {
            return Err(MailboxError::Firmware);
        }
        if words[2] != tag || words[3] != capacity || words[4] != 0x8000_0008 {
            return Err(MailboxError::Tag);
        }
        if words[5] != UART_CLOCK_ID || words[6] == 0 || (self == Self::Enable && words[6] != 1) {
            return Err(MailboxError::Clock);
        }
        Ok(words[6])
    }
}

/// Validate an entire dedicated 64-byte buffer inside the proven kernel BSS.
/// This does not prove exclusive ownership or firmware completion.
pub fn property_word(address: u64, bss_start: u64, bss_end: u64) -> Result<u32, MailboxError> {
    let end = address
        .checked_add(BUFFER_BYTES)
        .ok_or(MailboxError::Address)?;
    if address & 63 != 0
        || bss_start < crate::KERNEL_START
        || bss_end > 0x3f_0000 // Code/BSS must not enter the private stack.
        || bss_start > bss_end
        || address < bss_start
        || end > bss_end
        || end > 0x3f00_0000
    // Board-specific DMA window.
    {
        return Err(MailboxError::Address);
    }
    Ok((address as u32) | 0xc000_0000 | 8)
}

/// One budget spans stale-drain, transmit and receive; never reset on progress.
pub struct Budget {
    start_us: u32,
    remaining: u32,
}

impl Budget {
    pub fn new(start_us: u32) -> Self {
        Self {
            start_us,
            remaining: 1_000_000,
        }
    }

    pub fn poll(&mut self, now_us: u32) -> Result<(), MailboxError> {
        if self.remaining == 0 || now_us.wrapping_sub(self.start_us) >= 1_000_000 {
            return Err(MailboxError::Timeout);
        }
        self.remaining -= 1;
        Ok(())
    }
}

/// Primary-core-owned one-shot slots. No public reset or release operation.
/// Buffers themselves must remain allocated even when this state is poisoned.
#[derive(Default)]
pub struct ClockSlots {
    used: u8,
    poisoned: bool,
}

impl ClockSlots {
    pub fn claim(&mut self, operation: ClockOperation) -> Result<(), MailboxError> {
        let bit = 1 << operation as u8;
        if self.poisoned || self.used & bit != 0 {
            return Err(MailboxError::AlreadyUsed);
        }
        self.used |= bit;
        Ok(())
    }

    pub fn poison(&mut self) {
        self.poisoned = true;
    }

    /// Backend must select the lifetime-long slot identified by `operation` and
    /// `address`; buffer methods must not expose references while VC owns it.
    /// Real MMIO construction is a separate unsafe board-ownership boundary.
    pub fn exchange<I: MailboxIo>(
        &mut self,
        io: &mut I,
        operation: ClockOperation,
        address: u64,
        bss_start: u64,
        bss_end: u64,
    ) -> Result<u32, MailboxError> {
        let result = self.exchange_inner(io, operation, address, bss_start, bss_end);
        if result.is_err() {
            self.poison();
        }
        result
    }

    fn exchange_inner<I: MailboxIo>(
        &mut self,
        io: &mut I,
        operation: ClockOperation,
        address: u64,
        bss_start: u64,
        bss_end: u64,
    ) -> Result<u32, MailboxError> {
        self.claim(operation)?;
        let word = property_word(address, bss_start, bss_end)?;
        let mut budget = Budget::new(io.now_us());
        // Empty stale RX first; unrelated traffic never extends this budget.
        loop {
            budget.poll(io.now_us())?;
            if io.rx_status() & (1 << 30) != 0 {
                break;
            }
            io.receive();
        }
        for (index, value) in operation.request().into_iter().enumerate() {
            io.buffer_write(index, value);
        }
        loop {
            budget.poll(io.now_us())?;
            if io.tx_status() & (1 << 31) == 0 {
                break;
            }
        }
        io.barrier();
        io.submit(word);
        loop {
            budget.poll(io.now_us())?;
            if io.rx_status() & (1 << 30) == 0 && io.receive() == word {
                break;
            }
        }
        io.barrier();
        let mut snapshot = [0; 16];
        for (index, value) in snapshot.iter_mut().enumerate() {
            *value = io.buffer_read(index);
        }
        operation.response(&snapshot)
    }
}

/// Register/buffer boundary for deterministic transport tests. No IRQ client.
/// Hardware implementations must use volatile accesses and D22 lifetime rules.
pub trait MailboxIo {
    fn now_us(&mut self) -> u32;
    fn rx_status(&mut self) -> u32;
    fn tx_status(&mut self) -> u32;
    fn receive(&mut self) -> u32;
    fn submit(&mut self, word: u32);
    fn barrier(&mut self);
    fn buffer_write(&mut self, index: usize, value: u32);
    fn buffer_read(&mut self, index: usize) -> u32;
}

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;
    use std::{collections::VecDeque, vec::Vec};

    #[derive(Clone, Copy)]
    enum Mode {
        Good,
        TxFull,
        NoReply,
        Malformed,
        StaleFlood,
    }

    struct Mock {
        mode: Mode,
        words: [u32; 16],
        responses: VecDeque<u32>,
        submitted: Option<u32>,
        reads: usize,
        writes: usize,
        received: usize,
        barriers: usize,
        completed: bool,
        trace: Vec<&'static str>,
    }

    impl Mock {
        fn new(mode: Mode) -> Self {
            Self {
                mode,
                words: [0; 16],
                responses: VecDeque::new(),
                submitted: None,
                reads: 0,
                writes: 0,
                received: 0,
                barriers: 0,
                completed: false,
                trace: Vec::new(),
            }
        }
    }

    impl MailboxIo for Mock {
        fn now_us(&mut self) -> u32 {
            0
        } // Independent iteration cap must terminate.
        fn rx_status(&mut self) -> u32 {
            if matches!(self.mode, Mode::StaleFlood) || !self.responses.is_empty() {
                0
            } else {
                1 << 30
            }
        }
        fn tx_status(&mut self) -> u32 {
            if matches!(self.mode, Mode::TxFull) {
                1 << 31
            } else {
                0
            }
        }
        fn receive(&mut self) -> u32 {
            self.received += 1;
            let word = self.responses.pop_front().unwrap_or(0);
            if self.submitted == Some(word) {
                self.completed = true;
            }
            word
        }
        fn submit(&mut self, word: u32) {
            assert_eq!(self.barriers, 1);
            assert_eq!(self.writes, 16);
            self.trace.push("submit");
            self.submitted = Some(word);
            if !matches!(self.mode, Mode::NoReply) {
                self.words[1] = 0x8000_0000;
                self.words[4] = 0x8000_0008;
                self.words[6] = if self.words[2] == 0x38001 {
                    1
                } else {
                    48_000_000
                };
                if matches!(self.mode, Mode::Malformed) {
                    self.words[5] = 3;
                }
                self.responses.extend([word ^ 1, word + 64, word]);
            }
        }
        fn barrier(&mut self) {
            self.barriers += 1;
            self.trace.push("barrier");
        }
        fn buffer_write(&mut self, index: usize, value: u32) {
            assert!(self.submitted.is_none());
            self.writes += 1;
            self.words[index] = value;
            self.trace.push("write");
        }
        fn buffer_read(&mut self, index: usize) -> u32 {
            assert!(self.completed);
            assert_eq!(self.barriers, 2);
            self.reads += 1;
            self.trace.push("read");
            self.words[index]
        }
    }

    fn exchange(slots: &mut ClockSlots, io: &mut Mock) -> Result<u32, MailboxError> {
        slots.exchange(io, ClockOperation::Enable, 0x210000, 0x210000, 0x2100c0)
    }

    #[test]
    fn transport_correlates_address_and_channel_before_snapshot() {
        let mut io = Mock::new(Mode::Good);
        assert_eq!(exchange(&mut ClockSlots::default(), &mut io), Ok(1));
        assert_eq!((io.received, io.reads, io.writes), (3, 16, 16));
        assert_eq!(&io.trace[16..19], &["barrier", "submit", "barrier"]);
    }

    #[test]
    fn full_fifo_and_infinite_stale_traffic_stop_without_submission() {
        for mode in [Mode::TxFull, Mode::StaleFlood] {
            let mut io = Mock::new(mode);
            let mut slots = ClockSlots::default();
            assert_eq!(exchange(&mut slots, &mut io), Err(MailboxError::Timeout));
            assert!(io.submitted.is_none());
            assert_eq!(io.reads, 0);
            assert_eq!(
                slots.claim(ClockOperation::MeasuredRate),
                Err(MailboxError::AlreadyUsed)
            );
        }
    }

    #[test]
    fn late_response_after_timeout_never_reuses_slot() {
        let mut io = Mock::new(Mode::NoReply);
        let mut slots = ClockSlots::default();
        assert_eq!(exchange(&mut slots, &mut io), Err(MailboxError::Timeout));
        assert_eq!(io.reads, 0);
        assert_eq!(io.writes, 16);
        // Model firmware writing the dedicated allocation after our timeout.
        io.words[6] = 123;
        io.responses.push_back(io.submitted.unwrap());
        assert_eq!(
            exchange(&mut slots, &mut io),
            Err(MailboxError::AlreadyUsed)
        );
        assert_eq!(io.words[6], 123);
        assert_eq!(io.writes, 16);
        assert_eq!(io.reads, 0);
    }

    #[test]
    fn malformed_correlated_reply_poisoned_without_retry() {
        let mut io = Mock::new(Mode::Malformed);
        let mut slots = ClockSlots::default();
        assert_eq!(exchange(&mut slots, &mut io), Err(MailboxError::Clock));
        assert_eq!(
            exchange(&mut slots, &mut io),
            Err(MailboxError::AlreadyUsed)
        );
        assert_eq!(io.writes, 16);
    }

    fn reply(operation: ClockOperation) -> [u32; 16] {
        let mut words = operation.request();
        words[1] = 0x8000_0000;
        words[4] = 0x8000_0008;
        words[6] = if operation == ClockOperation::Enable {
            1
        } else {
            48_000_000
        };
        words
    }

    #[test]
    fn request_wire_layouts_and_positive_responses() {
        for (operation, bytes, request_length) in [
            (ClockOperation::Enable, 32, 8),
            (ClockOperation::SetRate, 36, 12),
            (ClockOperation::MeasuredRate, 32, 4),
        ] {
            let words = operation.request();
            assert_eq!(
                (words[0], words[1], words[4], words[5]),
                (bytes, 0, request_length, 2)
            );
            assert_eq!(words[(bytes / 4 - 1) as usize], 0);
            assert!(operation.response(&reply(operation)).is_ok());
        }
        assert_eq!(&ClockOperation::SetRate.request()[6..8], &[48_000_000, 1]);
    }

    #[test]
    fn malformed_and_unsupported_responses_fail() {
        for operation in [
            ClockOperation::Enable,
            ClockOperation::SetRate,
            ClockOperation::MeasuredRate,
        ] {
            for (index, value) in [
                (0, 64),
                (1, 0),
                (1, 0x8000_0001),
                (2, 0),
                (3, 4),
                (4, 8),
                (4, 0x8000_0004),
                (4, 0x8000_0010),
                (5, 3),
                (6, 0),
            ] {
                let mut words = reply(operation);
                words[index] = value;
                assert!(
                    operation.response(&words).is_err(),
                    "{operation:?} field {index}"
                );
            }
            let mut words = reply(operation);
            words[operation.layout().2] = 1;
            assert_eq!(operation.response(&words), Err(MailboxError::Layout));
        }
        let mut words = reply(ClockOperation::Enable);
        words[6] = 3;
        assert_eq!(
            ClockOperation::Enable.response(&words),
            Err(MailboxError::Clock)
        );
    }

    #[test]
    fn only_owned_aligned_bss_extents_form_bus_words() {
        assert_eq!(property_word(0x210000, 0x210000, 0x210040), Ok(0xc0210008));
        for (address, begin, end) in [
            (0x210001, 0x210000, 0x210080),
            (0x210000, 0x210001, 0x210080),
            (0x210000, 0x210000, 0x21003f),
            (0x210000, 0, 0x210080),
            (0x210000, 0x210000, 0x400000),
            (u64::MAX - 63, 0x210000, 0x210080),
        ] {
            assert_eq!(
                property_word(address, begin, end),
                Err(MailboxError::Address)
            );
        }
    }

    #[test]
    fn deadline_wrap_and_frozen_timer_are_bounded() {
        let mut budget = Budget::new(u32::MAX - 10);
        assert!(budget.poll(20).is_ok());
        assert_eq!(budget.poll(999_990), Err(MailboxError::Timeout));
        let mut budget = Budget::new(1);
        for _ in 0..1_000_000 {
            assert!(budget.poll(1).is_ok());
        }
        assert_eq!(budget.poll(1), Err(MailboxError::Timeout));
    }

    #[test]
    fn consumed_and_poisoned_slots_cannot_be_reused() {
        let mut slots = ClockSlots::default();
        assert!(slots.claim(ClockOperation::Enable).is_ok());
        assert_eq!(
            slots.claim(ClockOperation::Enable),
            Err(MailboxError::AlreadyUsed)
        );
        slots.poison();
        assert_eq!(
            slots.claim(ClockOperation::SetRate),
            Err(MailboxError::AlreadyUsed)
        );
    }
}
