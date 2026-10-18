from __future__ import annotations

import hashlib
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase

from fleet.models import UnknownGPSData

from .models import DiscoveryCase, DiscoverySample
from .sample_analysis import analyze_raw_payload


class RawSampleAnalysisTests(TestCase):
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


class UnknownQueueIntakeTests(TestCase):
    def test_command_imports_queue_rows_idempotently_without_assigning_protocol(self):
        session_id = uuid4()
        row = UnknownGPSData.objects.create(
            session_id=session_id,
            transport="tcp",
            remote_address="192.0.2.10:12345",
            raw_payload=b"\x01\x02SAMPLE-123\x00",
            identifier_candidate="",
            status="pending",
        )

        call_command("ingest_unknown_gps_samples", limit=100)
        call_command("ingest_unknown_gps_samples", limit=100)

        self.assertEqual(DiscoveryCase.objects.filter(queue_session_id=session_id).count(), 1)
        case = DiscoveryCase.objects.get(queue_session_id=session_id)
        self.assertEqual(case.status, DiscoveryCase.Status.PENDING_SEARCH)
        self.assertEqual(case.protocol_hint, "")
        self.assertEqual(case.identifier_candidate, "")
        self.assertEqual(case.raw_sample_count, 1)
        self.assertEqual(DiscoverySample.objects.filter(queue_row=row).count(), 1)
        sample = DiscoverySample.objects.get(queue_row=row)
        self.assertEqual(sample.payload_sha256, hashlib.sha256(bytes(row.raw_payload)).hexdigest())
        self.assertEqual(sample.features["byte_length"], len(bytes(row.raw_payload)))

    def test_dry_run_does_not_create_discovery_records(self):
        row = UnknownGPSData.objects.create(
            session_id=uuid4(),
            transport="tcp",
            remote_address="192.0.2.11:12346",
            raw_payload=b"\x01\x02TEST",
            status="pending",
        )

        call_command("ingest_unknown_gps_samples", limit=100, dry_run=True)

        self.assertFalse(DiscoverySample.objects.filter(queue_row=row).exists())
        self.assertFalse(DiscoveryCase.objects.exists())
