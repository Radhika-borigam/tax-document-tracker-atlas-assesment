"""What happens to a file from arrival to resolution.

This is the second real piece of logic after derivation. It implements the
document lifecycle from docs/02: run the classifier, route on confidence, catch
the junk cases, auto-match only the cleanest documents, and let a human review
the rest.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.classifier import Guess, classify
from app.models import (
    Client,
    DocKind,
    Document,
    DocStatus,
    Person,
    Requirement,
    ReqSource,
    ReviewReason,
)

# A guess below this is never acted on automatically. See docs/02 for why 0.70.
CONFIDENCE_THRESHOLD = 0.70


def _known_names(client: Client) -> list[str]:
    return [p.name for p in client.people]


def _person_by_name(client: Client, name: str | None) -> Person | None:
    if not name:
        return None
    lower = name.lower()
    for p in client.people:
        if p.name.lower() == lower or p.name.split()[0].lower() == lower.split()[0]:
            return p
    return None


def open_requirements(client: Client) -> list[Requirement]:
    """Slots that are still expected and not yet satisfied."""
    result = []
    for r in client.requirements:
        if r.removed or r.waived:
            continue
        if any(d.status == DocStatus.accepted for d in r.documents):
            continue
        result.append(r)
    return result


def _find_matching_slot(client: Client, kind: DocKind, tax_year: int | None, person: Person | None) -> Requirement | None:
    """Find an open expected slot this document would fill. Lowest slot first."""
    candidates = []
    for r in open_requirements(client):
        if r.kind != kind:
            continue
        # W-2s and IDs are per person; the 1040 is household-level (person is None).
        if r.person_id is not None and (person is None or r.person_id != person.id):
            continue
        if r.doc_tax_year is not None and r.doc_tax_year != tax_year:
            continue
        candidates.append(r)
    candidates.sort(key=lambda r: r.slot_index)
    return candidates[0] if candidates else None


def _expected_year_for_kind(client: Client, kind: DocKind | None) -> int | None:
    """The correct tax year a given kind should carry, or None if year is N/A."""
    if kind is DocKind.w2:
        return client.tax_year
    if kind is DocKind.prior_year_1040:
        return client.tax_year - 1
    return None  # government_id has no year


def ingest(db: Session, client: Client, filename: str, file_bytes: bytes, guess: Guess | None = None) -> Document:
    """Take in one arriving file: classify it, route it, auto-match if clean.

    `guess` can be passed in to bypass the stub classifier (used by tests); by
    default we run the classifier on the bytes.
    """
    if guess is None:
        guess = classify(filename, file_bytes, _known_names(client))

    doc = Document(
        client_id=client.id,
        original_filename=filename,
        guessed_kind=guess.kind,
        guessed_tax_year=guess.tax_year,
        guessed_person_name=guess.person_name,
        confidence=guess.confidence,
        readable=guess.readable,
    )

    reason = _route(client, doc, guess)
    if reason is None:
        # Clean and confident: auto-match to a slot.
        person = _person_by_name(client, guess.person_name)
        slot = _find_matching_slot(client, guess.kind, guess.tax_year, person)
        doc.status = DocStatus.accepted
        doc.matched_requirement_id = slot.id if slot else None
    else:
        doc.status = DocStatus.needs_review
        doc.review_reason = reason

    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _route(client: Client, doc: Document, guess: Guess) -> ReviewReason | None:
    """Decide whether a freshly classified doc needs human review.

    Returns the reason it needs review, or None if it is clean enough to accept
    automatically. Order matters: we report the most fundamental problem first.
    """
    # 1. Can't read it -> can't act on it.
    if not guess.readable:
        return ReviewReason.unreadable

    # 2. Too unsure -> a human must look (the brief's core rule).
    if guess.confidence < CONFIDENCE_THRESHOLD or guess.kind is None:
        return ReviewReason.low_confidence

    # 3. Confident, but is the guess actually usable for this client?
    person = _person_by_name(client, guess.person_name)
    # A document tied to a person (W-2, ID) must name someone on this return.
    if guess.kind in (DocKind.w2, DocKind.government_id) and person is None:
        return ReviewReason.unknown_person

    expected_year = _expected_year_for_kind(client, guess.kind)
    if expected_year is not None and guess.tax_year != expected_year:
        return ReviewReason.wrong_year

    # 4. Guess is fine, but is there actually an open slot for it?
    if _find_matching_slot(client, guess.kind, guess.tax_year, person) is None:
        return ReviewReason.no_matching_slot

    return None


# --- review actions (the human's side) -------------------------------------


def accept_document(
    db: Session,
    client: Client,
    doc: Document,
    *,
    kind: DocKind | None = None,
    tax_year: int | None = None,
    person_id: int | None = None,
    requirement_id: int | None = None,
    note: str | None = None,
) -> Document:
    """The accountant accepts a reviewed document, optionally correcting the guess
    and/or picking which slot it fills."""
    if kind is not None:
        doc.human_kind = kind
    if tax_year is not None:
        doc.human_tax_year = tax_year
    if person_id is not None:
        doc.human_person_id = person_id
    if note is not None:
        doc.review_note = note

    # Resolve the slot: explicit choice wins, else best match on effective values.
    if requirement_id is not None:
        doc.matched_requirement_id = requirement_id
    else:
        person = None
        if doc.human_person_id is not None:
            person = next((p for p in client.people if p.id == doc.human_person_id), None)
        else:
            person = _person_by_name(client, doc.guessed_person_name)
        slot = _find_matching_slot(client, doc.effective_kind, doc.effective_tax_year, person)
        doc.matched_requirement_id = slot.id if slot else None

    doc.status = DocStatus.accepted
    doc.review_reason = None
    db.commit()
    db.refresh(doc)
    return doc


def reject_document(db: Session, doc: Document, note: str | None = None) -> Document:
    """The accountant rejects a document as junk (wrong client, duplicate, etc.)."""
    doc.status = DocStatus.rejected
    doc.matched_requirement_id = None
    if note is not None:
        doc.review_note = note
    db.commit()
    db.refresh(doc)
    return doc
