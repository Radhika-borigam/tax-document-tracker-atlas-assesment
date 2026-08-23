"""The document lifecycle: confidence routing, the junk cases, matching, review.

These use the `guess` injection on ingest() so we can exercise every routing
branch deterministically without needing real files for each case. There is a
separate test that runs the real classifier over the actual sample PDFs.
"""
from __future__ import annotations

from app import documents as docsvc
from app.classifier import Guess
from app.models import DocKind, DocStatus, ReviewReason
from app.status import build_status


def _ana(client):
    return next(p for p in client.people if p.name.startswith("Ana"))


def g(kind=DocKind.w2, year=2025, person="Ana Rivera", conf=0.9, readable=True):
    return Guess(kind=kind, tax_year=year, person_name=person, confidence=conf, readable=readable)


def test_clean_confident_w2_is_accepted_and_matched(db, client):
    doc = docsvc.ingest(db, client, "Ana W-2 2025.pdf", b"", guess=g())
    assert doc.status == DocStatus.accepted
    assert doc.matched_requirement_id is not None


def test_low_confidence_goes_to_review(db, client):
    doc = docsvc.ingest(db, client, "blurry.pdf", b"", guess=g(conf=0.4))
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason == ReviewReason.low_confidence


def test_unreadable_scan_goes_to_review(db, client):
    doc = docsvc.ingest(db, client, "scan.pdf", b"", guess=g(readable=False, conf=0.15, kind=None, person=None, year=None))
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason == ReviewReason.unreadable


def test_wrong_year_is_caught(db, client):
    # A confident W-2, but for 2024 when we want 2025.
    doc = docsvc.ingest(db, client, "Ana W-2 2024.pdf", b"", guess=g(year=2024))
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason == ReviewReason.wrong_year


def test_unknown_person_is_caught(db, client):
    # A confident W-2 for someone not on the return.
    doc = docsvc.ingest(db, client, "Cousin W-2 2025.pdf", b"", guess=g(person="Carla Cousin"))
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason == ReviewReason.unknown_person


def test_extra_w2_with_no_open_slot_is_caught(db, client):
    # Fill both of Ana's W-2 slots, then a third confident W-2 has nowhere to go.
    docsvc.ingest(db, client, "Ana W-2 2025 a.pdf", b"", guess=g())
    docsvc.ingest(db, client, "Ana W-2 2025 b.pdf", b"", guess=g())
    third = docsvc.ingest(db, client, "Ana W-2 2025 c.pdf", b"", guess=g())
    assert third.status == DocStatus.needs_review
    assert third.review_reason == ReviewReason.no_matching_slot


def test_prior_year_1040_matches_on_the_prior_year(db, client):
    doc = docsvc.ingest(db, client, "Rivera 1040 2024.pdf", b"", guess=g(kind=DocKind.prior_year_1040, year=2024, person=None))
    assert doc.status == DocStatus.accepted
    assert doc.matched_requirement_id is not None


def test_received_count_reflects_accepted_documents(db, client):
    before = build_status(client)["summary"]["received"]
    docsvc.ingest(db, client, "Ana W-2 2025.pdf", b"", guess=g())
    after = build_status(client)["summary"]["received"]
    assert after == before + 1


def test_two_w2s_for_same_person_fill_different_slots(db, client):
    d1 = docsvc.ingest(db, client, "Ana W-2 2025 job1.pdf", b"", guess=g())
    d2 = docsvc.ingest(db, client, "Ana W-2 2025 job2.pdf", b"", guess=g())
    assert d1.matched_requirement_id != d2.matched_requirement_id


def test_review_accept_with_correction_then_matches(db, client):
    # Tool guessed the wrong year; accountant corrects it and it matches.
    doc = docsvc.ingest(db, client, "Ana W-2 2024.pdf", b"", guess=g(year=2024))
    assert doc.status == DocStatus.needs_review
    docsvc.accept_document(db, client, doc, tax_year=2025, note="Client re-sent the 2025 copy")
    assert doc.status == DocStatus.accepted
    assert doc.matched_requirement_id is not None
    assert doc.guessed_tax_year == 2024  # original guess preserved
    assert doc.human_tax_year == 2025  # correction recorded separately


def test_reject_removes_from_review_and_matches_nothing(db, client):
    doc = docsvc.ingest(db, client, "Cousin W-2 2025.pdf", b"", guess=g(person="Carla Cousin"))
    docsvc.reject_document(db, doc, note="Not a member of this household")
    assert doc.status == DocStatus.rejected
    assert doc.matched_requirement_id is None
    assert doc not in [d for d in client.documents if d.status == DocStatus.needs_review]
