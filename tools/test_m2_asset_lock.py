"""Local byte-review failures, using temporary files rather than real cache edits."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from check_m2_asset_lock import check_file


class LocalBytes(unittest.TestCase):
    def test_exact_file_then_changed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root/'asset.bin'; p.write_bytes(b'good')
            record = dict(path='asset.bin', size_bytes=4, sha256=hashlib.sha256(b'good').hexdigest())
            check_file(root, record)
            p.write_bytes(b'evil')
            with self.assertRaises(ValueError): check_file(root, record)

    def test_length_mismatch_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'asset.bin').write_bytes(b'good')
            with self.assertRaises(ValueError): check_file(root, dict(path='asset.bin', size_bytes=3, sha256=hashlib.sha256(b'good').hexdigest()))
            with self.assertRaises(ValueError): check_file(root, dict(path='../asset.bin', size_bytes=4, sha256='a'*64))


if __name__ == '__main__':
    unittest.main()
