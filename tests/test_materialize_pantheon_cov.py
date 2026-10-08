"""Offline integrity tests for frozen Pantheon+ covariance materialization."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts import materialize_pantheon_cov as cov


class FrozenCovarianceMaterializerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "tiny.cov"
        self.payload = b"2\n1.0\n0.0\n0.0\n1.0\n"
        self.file.write_bytes(self.payload)

    def verify(self, **changes):
        params = {"digest": hashlib.sha256(self.payload).hexdigest(),
                  "size": len(self.payload), "dimension": 2}
        params.update(changes)
        return cov.verify_covariance(self.file, **params)

    def test_exact_frozen_bytes_and_square_shape(self):
        result = self.verify()
        self.assertEqual(result["status"], "INPUT_BYTES_VERIFIED_ONLY")
        self.assertEqual(result["dimension"], 2)

    def test_wrong_sha_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "COVARIANCE_SHA256_MISMATCH"):
            self.verify(digest="0" * 64)

    def test_wrong_size_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "COVARIANCE_SIZE_MISMATCH"):
            self.verify(size=len(self.payload) + 1)

    def test_shape_mismatch_fails_closed(self):
        self.file.write_bytes(b"2\n1.0\n0.0\n1.0\n")
        actual = self.file.read_bytes()
        with self.assertRaisesRegex(ValueError, "COVARIANCE_SHAPE_MISMATCH"):
            cov.verify_covariance(self.file, digest=hashlib.sha256(actual).hexdigest(),
                                  size=len(actual), dimension=2)


if __name__ == "__main__":
    unittest.main()
