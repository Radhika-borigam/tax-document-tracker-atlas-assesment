"""Run the real classifier + routing over the actual sample PDF files.

Unlike test_documents.py (which injects guesses to exercise each branch), this
test uses no injection: it reads the real bytes off disk and lets the stub
classifier read them, so it proves the end-to-end pipeline works on real files —
including the three awkward cases the brief asks for.
"""
from __future__ import annotations

import os

import pytest

from app import documents as docsvc
from app.models import DocStatus, ReviewReason

SAMPLES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "sample_documents",
    "rivera",
)

pytestmark = pytest.mark.skipif(
    not os.path.isdir(SAMPLES) or not os.listdir(SAMPLES),
    reason="sample docs not generated; run scripts/generate_sample_docs.py",
)


def _ingest(db, client, filename):
    with open(os.path.join(SAMPLES, filename), "rb") as fh:
        return docsvc.ingest(db, client, filename, fh.read())


def test_good_w2_is_accepted(db, client):
    doc = _ingest(db, client, "Ana Rivera W-2 2025 Acme Corp.pdf")
    assert doc.status == DocStatus.accepted
    assert doc.matched_requirement_id is not None


def test_prior_year_1040_is_accepted(db, client):
    doc = _ingest(db, client, "Rivera 1040 2024.pdf")
    assert doc.status == DocStatus.accepted


def test_government_id_is_accepted(db, client):
    doc = _ingest(db, client, "Ana Rivera drivers license.pdf")
    assert doc.status == DocStatus.accepted


def test_wrong_year_file_is_flagged(db, client):
    doc = _ingest(db, client, "Ana Rivera W-2 2024 Acme Corp.pdf")
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason == ReviewReason.wrong_year


def test_unknown_person_file_is_flagged(db, client):
    doc = _ingest(db, client, "Carla Cousin W-2 2025 Soylent.pdf")
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason == ReviewReason.unknown_person


def test_unreadable_scan_is_flagged(db, client):
    doc = _ingest(db, client, "scan_unreadable.pdf")
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason == ReviewReason.unreadable
    assert doc.readable is False


def test_badly_named_file_is_low_confidence(db, client):
    # No usable person in the filename; the content mentions W-2/2025 but the
    # person is "someone", so the classifier stays unsure and asks for review.
    doc = _ingest(db, client, "IMG_20250412.pdf")
    assert doc.status == DocStatus.needs_review
    assert doc.review_reason in (ReviewReason.low_confidence, ReviewReason.unknown_person)
