from django.test import TestCase

from .models import (
    CandidateTestRun,
    DecoderCandidate,
    DiscoveryCase,
    PublishedDecoderVersion,
    ReferenceSource,
)


class DecoderDiscoveryModelTests(TestCase):
    def test_discovery_case_starts_pending_and_keeps_raw_queue_references(self):
        case = DiscoveryCase.objects.create(
            identifier_candidate="9176515720",
            queue_references=[{"queue_id": 12, "transport": "tcp"}],
        )
        self.assertEqual(case.status, DiscoveryCase.Status.PENDING_SEARCH)
        self.assertEqual(case.queue_references[0]["queue_id"], 12)

    def test_candidate_defaults_to_unverified_and_does_not_store_source_inline(self):
        case = DiscoveryCase.objects.create(identifier_candidate="unknown-device")
        candidate = DecoderCandidate.objects.create(
            case=case,
            title="Example decoder",
            source_url="https://example.org/decoder.py",
        )
        self.assertEqual(candidate.compatibility, DecoderCandidate.Compatibility.UNKNOWN)
        self.assertEqual(candidate.status, DecoderCandidate.Status.DISCOVERED)
        self.assertFalse(candidate.artifact_preserved)
        self.assertEqual(candidate.artifact_storage_key, "")

    def test_candidate_test_run_is_not_passed_by_default(self):
        case = DiscoveryCase.objects.create()
        candidate = DecoderCandidate.objects.create(
            case=case,
            title="Example decoder",
            source_url="https://example.org/decoder.py",
        )
        run = CandidateTestRun.objects.create(candidate=candidate)
        self.assertEqual(run.status, CandidateTestRun.Status.PENDING)
        self.assertEqual(run.sample_count, 0)

    def test_published_version_is_inactive_until_explicitly_published(self):
        case = DiscoveryCase.objects.create()
        candidate = DecoderCandidate.objects.create(
            case=case,
            title="Example decoder",
            source_url="https://example.org/decoder.py",
        )
        version = PublishedDecoderVersion.objects.create(
            candidate=candidate,
            protocol="example",
            version=1,
            decoder_path="app/protocols/decoders/example.py",
        )
        self.assertFalse(version.is_active)
        self.assertIsNone(version.approved_at)
