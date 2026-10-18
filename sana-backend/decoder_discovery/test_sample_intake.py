from __future__ import annotations

import hashlib
import unittest

from .sample_analysis import analyze_raw_payload


class RawSampleAnalysisTests(unittest.TestCase):
    def test_extracts_generic_features_without_protocol_classification(self):
        payload = b"\x7e\x01DEVICE-ABC\x00\x7e"
        result = analyze_raw_payload(payload)

        self.assertEqual(result["byte_length"], len(payload))
        self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(result["prefix_hex"], payload[:32].hex())
        self.assertIn("DEVICE-ABC", result["printable_runs"])
        self.assertNotIn("protocol", result)

    def test_empty_payload_has_stable_features(self):
        result = analyze_raw_payload(b"")
        self.assertEqual(result["byte_length"], 0)
        self.assertEqual(result["entropy_bits_per_byte"], 0.0)
        self.assertEqual(result["sha256"], hashlib.sha256(b"").hexdigest())
