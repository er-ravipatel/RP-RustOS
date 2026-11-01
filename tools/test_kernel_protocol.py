import unittest
from test_kernel import serial_marker


class ProtocolChecks(unittest.TestCase):
    def test_unterminated_or_prefixed_marker_cannot_pass(self):
        self.assertFalse(serial_marker(b'RUSTOS_BOOT_OK', 'RUSTOS_BOOT_OK', []))
        self.assertFalse(serial_marker(b'prefix RUSTOS_BOOT_OK\n', 'RUSTOS_BOOT_OK', []))
        self.assertTrue(serial_marker(b'RUSTOS_BOOT_OK\r\n', 'RUSTOS_BOOT_OK', []))

    def test_expected_marker_does_not_override_fault(self):
        with self.assertRaises(ValueError):
            serial_marker(b'RUSTOS_BOOT_OK\nRUSTOS_EXCEPTION\n', 'RUSTOS_BOOT_OK', ['RUSTOS_EXCEPTION'])

    def test_oversized_or_invalid_stream_cannot_pass(self):
        for raw in (b'x' * 4097, b'x\n' * 524289, b'\xffRUSTOS_BOOT_OK\n'):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                serial_marker(raw, 'RUSTOS_BOOT_OK', [])


if __name__ == '__main__':
    unittest.main()
