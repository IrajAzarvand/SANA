from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from .discovery_engine import analyze_unknown_sessions, find_identifier_candidates


class IdentifierEvidenceTests(unittest.TestCase):
    def test_finds_registered_ascii_identifier_with_numeric_boundaries(self):
        self.assertEqual(
            find_identifier_candidates(b"ID=352016703005868;OK", ["352016703005868", "168"]),
            ["352016703005868"],
        )

    def test_keeps_ambiguous_identifiers_visible(self):
        result = find_identifier_candidates(b"352016703005868/9176515720", [
            "352016703005868", "9176515720",
        ])
        self.assertEqual(result, ["352016703005868", "9176515720"])


class UnknownSessionAnalysisTests(unittest.TestCase):
    def _row(self, row_id, session_id, payload, identifier=""):
        return SimpleNamespace(
            id=row_id,
            session_id=session_id,
            transport="tcp",
            raw_payload=payload,
            identifier_candidate=identifier,
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_groups_rows_and_analyzes_payload_without_mutating_rows(self):
        session = uuid4()
        rows = [
            self._row(1, session, b"ID=352016703005868;"),
            self._row(2, session, b"\x01\x02GPS"),
        ]
        reports = analyze_unknown_sessions(rows, ["352016703005868"])

        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertEqual(report["row_ids"], [1, 2])
        self.assertEqual(report["identifier_match_status"], "unique")
        self.assertEqual(report["registered_identifier_candidates"], ["352016703005868"])
        self.assertEqual(report["features"]["byte_length"], len(b"ID=352016703005868;\x01\x02GPS"))
        self.assertEqual(rows[0].raw_payload, b"ID=352016703005868;")

    def test_ambiguous_or_unmatched_session_is_not_guessed(self):
        session = uuid4()
        rows = [self._row(1, session, b"9176515720 and 352016703005868")]
        report = analyze_unknown_sessions(
            rows, ["9176515720", "352016703005868"]
        )[0]
        self.assertEqual(report["identifier_match_status"], "ambiguous")
        self.assertEqual(len(report["registered_identifier_candidates"]), 2)

    def test_limits_session_bytes_and_marks_truncation(self):
        session = uuid4()
        rows = [
            self._row(1, session, b"1234"),
            self._row(2, session, b"5678"),
        ]
        report = analyze_unknown_sessions(rows, [], max_session_bytes=5)[0]
        self.assertTrue(report["truncated"])
        self.assertEqual(report["features"]["byte_length"], 4)


class JT808HeaderEvidenceTests(unittest.TestCase):
    def test_extracts_terminal_bcd_and_registration_message_as_evidence(self):
        from .discovery_engine import _extract_jt808_header_evidence

        # Frame header: 7E | 0100 | 002D | 019176533355 | 0027 | body | 7E
        payload = bytes.fromhex(
            "7e0100002d01917653335500270022044e373034343456335f4f50454e5f4a54"
            "3830380000000000000000000000000000000000000000000000000000007e"
        )
        evidence = _extract_jt808_header_evidence(payload)
        self.assertGreaterEqual(evidence["jt808_frame_evidence_count"], 1)
        self.assertEqual(evidence["jt808_frame_evidence"][0]["message_id"], "0x0100")
        self.assertEqual(evidence["jt808_frame_evidence"][0]["terminal_id_digits"], "019176533355")
        self.assertIn("19176533355", evidence["jt808_terminal_id_candidates"])

    def test_session_report_exposes_search_clues_without_assigning_protocol(self):
        session = uuid4()
        payload = bytes.fromhex(
            "7e0100002d01917653335500270022044e373034343456335f4f50454e5f4a54"
            "3830380000000000000000000000000000000000000000000000000000007e"
        )
        row = SimpleNamespace(
            id=1, session_id=session, transport="tcp", raw_payload=payload,
            identifier_candidate="", received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        report = analyze_unknown_sessions([row], ["352016703005868"])[0]
        self.assertIn("jt808_like_framing", report["protocol_hints"])
        self.assertIn("open_jt808_marker", report["protocol_hints"])
        self.assertTrue(report["decoder_research_queries"])
        self.assertFalse(report["exact_header_identifier_matches"])
