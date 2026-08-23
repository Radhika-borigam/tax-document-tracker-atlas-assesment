"""The rules engine: build the expected-document list, and re-build it safely.

This is the most important file in the project. Everything in
docs/01 and docs/02 about "derive more than once without stomping the human"
is implemented here.

Two rules produce the list:

  1. Every client needs one prior-year 1040 (for tax_year - 1) and one
     government ID per adult filer (taxpayer, spouse).
  2. Each person needs one W-2 per employer they had in the tax year, taken
     straight from the disclosed employment facts.

Re-derivation is a MERGE, never a rebuild:
  - a freshly derived slot that already exists -> refresh its last_seen_version
  - a freshly derived slot that is new         -> create it
  - a system slot no longer derived            -> leave it, just don't refresh it
                                                  (its last_seen_version falls
                                                  behind, so we can flag it)
  - the human's columns (waived / removed) and any `manual` row -> never touched
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import (
    Client,
    DerivationRun,
    DocKind,
    EmploymentFact,
    Person,
    PersonRole,
    ReqSource,
    Requirement,
)

ADULT_ROLES = {PersonRole.taxpayer, PersonRole.spouse}


@dataclass(frozen=True)
class SlotKey:
    """The logical identity of one expected document, independent of any DB row."""

    kind: DocKind
    person_id: int | None
    doc_tax_year: int | None
    slot_index: int


def expected_slots(client: Client, people: list[Person], facts: list[EmploymentFact]) -> list[SlotKey]:
    """Pure function: given the client's facts, what documents do we expect?

    No database writes here on purpose — this is the part that is trivial to unit
    test, and it is where the tax rules live.
    """
    slots: list[SlotKey] = []

    # Rule 1a: one prior-year 1040 for the household (year before the engagement).
    slots.append(SlotKey(DocKind.prior_year_1040, None, client.tax_year - 1, 1))

    # Rule 1b: a government ID per adult filer. IDs have no tax year.
    for p in people:
        if p.role in ADULT_ROLES:
            slots.append(SlotKey(DocKind.government_id, p.id, None, 1))

    # Rule 2: one W-2 per employer in the tax year, per person.
    facts_by_person = {f.person_id: f for f in facts if f.tax_year == client.tax_year}
    for p in people:
        fact = facts_by_person.get(p.id)
        if not fact:
            continue
        for i in range(1, fact.employer_count + 1):
            slots.append(SlotKey(DocKind.w2, p.id, client.tax_year, i))

    return slots


def derive(db: Session, client: Client, note: str | None = None) -> DerivationRun:
    """Run (or re-run) derivation for a client, merging into existing rows.

    Returns the DerivationRun log entry describing what changed.
    """
    people = list(client.people)
    facts = list(client.facts)
    slots = expected_slots(client, people, facts)

    client.derivation_version += 1
    version = client.derivation_version

    # Index existing system requirements by their stable identity.
    existing: dict[tuple, Requirement] = {
        r.identity(): r
        for r in client.requirements
        if r.source == ReqSource.system
    }

    added = 0
    refreshed = 0
    for slot in slots:
        key = (slot.kind, slot.person_id, slot.doc_tax_year, slot.slot_index)
        row = existing.get(key)
        if row is not None:
            # Slot already known: refresh only the system's side. The human's
            # columns (waived/removed) are deliberately left exactly as they are.
            row.last_seen_version = version
            refreshed += 1
        else:
            db.add(
                Requirement(
                    client_id=client.id,
                    kind=slot.kind,
                    person_id=slot.person_id,
                    doc_tax_year=slot.doc_tax_year,
                    slot_index=slot.slot_index,
                    source=ReqSource.system,
                    last_seen_version=version,
                )
            )
            added += 1

    run = DerivationRun(
        client_id=client.id,
        version=version,
        note=note,
        added_count=added,
        refreshed_count=refreshed,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def waive_requirement(db: Session, req: Requirement, reason: str | None) -> Requirement:
    """The accountant marks an item 'not needed'. It stops being outstanding but
    stays visible. A human decision — re-derivation will not undo it."""
    req.waived = True
    req.waived_reason = reason
    db.commit()
    db.refresh(req)
    return req


def unwaive_requirement(db: Session, req: Requirement) -> Requirement:
    req.waived = False
    req.waived_reason = None
    db.commit()
    db.refresh(req)
    return req


def remove_requirement(db: Session, req: Requirement) -> Requirement:
    """The accountant removes an entry that was wrong. Soft-flagged, not deleted,
    so we keep the audit trail and re-derivation will not resurrect it."""
    req.removed = True
    db.commit()
    db.refresh(req)
    return req


def add_manual_requirement(
    db: Session,
    client: Client,
    kind: DocKind,
    person_id: int | None,
    doc_tax_year: int | None,
    label: str | None,
) -> Requirement:
    """The accountant adds an item the system did not anticipate.

    Manual rows use a slot_index above the system's range so they never collide
    with a derived slot, and `source=manual` keeps re-derivation away from them.
    """
    same_kind = [
        r for r in client.requirements
        if r.kind == kind and r.person_id == person_id and r.doc_tax_year == doc_tax_year
    ]
    next_index = max((r.slot_index for r in same_kind), default=0) + 1
    req = Requirement(
        client_id=client.id,
        kind=kind,
        person_id=person_id,
        doc_tax_year=doc_tax_year,
        slot_index=next_index,
        source=ReqSource.manual,
        last_seen_version=client.derivation_version,
        manual_label=label,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req
