"""The crown-jewel behaviour: re-derive in March without stomping on two months
of the accountant's decisions.

This is the scenario the brief spends the most words on, so it gets the most
tests. See docs/01 and docs/02.
"""
from __future__ import annotations

from app import derivation
from app.models import DocKind, EmploymentFact, ReqSource, Requirement


def _luis(client):
    return next(p for p in client.people if p.name.startswith("Luis"))


def _ana(client):
    return next(p for p in client.people if p.name.startswith("Ana"))


def _reqs(client, **filters):
    out = []
    for r in client.requirements:
        if all(getattr(r, k) == v for k, v in filters.items()):
            out.append(r)
    return out


def _disclose_luis_job_change(db, client):
    """March: the job change surfaces. Update the fact, then re-derive."""
    fact = next(f for f in client.facts if f.person_id == _luis(client).id)
    fact.employer_count = 2
    fact.note = "Changed jobs in June 2025 (disclosed in March)"
    db.commit()
    return derivation.derive(db, client, note="Job change disclosed")


def test_rederivation_adds_the_new_slot(db, client):
    before = _reqs(client, kind=DocKind.w2, person_id=_luis(client).id)
    assert len(before) == 1  # January: one W-2 for Luis

    run = _disclose_luis_job_change(db, client)

    after = _reqs(client, kind=DocKind.w2, person_id=_luis(client).id)
    assert len(after) == 2  # March: the second W-2 slot now exists
    assert run.added_count == 1  # exactly one new slot was created


def test_rederivation_does_not_duplicate_existing_slots(db, client):
    """Re-running must recognise the same slots, not create copies of them."""
    count_before = len(client.requirements)
    _disclose_luis_job_change(db, client)
    # Only Luis's second W-2 is new; everything else is refreshed in place.
    assert len(client.requirements) == count_before + 1


def test_rederivation_preserves_a_waived_item(db, client):
    # The accountant waived Ana's second W-2 in February.
    ana_w2_2 = _reqs(client, kind=DocKind.w2, person_id=_ana(client).id, slot_index=2)[0]
    derivation.waive_requirement(db, ana_w2_2, "Ana confirmed she left that job before it paid out")

    _disclose_luis_job_change(db, client)

    db.refresh(ana_w2_2)
    assert ana_w2_2.waived is True
    assert ana_w2_2.waived_reason  # the human's note survived re-derivation


def test_rederivation_preserves_a_removed_item(db, client):
    # The accountant removed one of Ana's W-2s as wrong.
    ana_w2_1 = _reqs(client, kind=DocKind.w2, person_id=_ana(client).id, slot_index=1)[0]
    derivation.remove_requirement(db, ana_w2_1)

    _disclose_luis_job_change(db, client)

    db.refresh(ana_w2_1)
    # It stays removed; re-derivation does not resurrect a human's decision.
    assert ana_w2_1.removed is True


def test_rederivation_leaves_manual_additions_alone(db, client):
    # The accountant added a 1099 the system never anticipated.
    manual = derivation.add_manual_requirement(
        db, client, DocKind.w2, _ana(client).id, 2025, label="Freelance 1099 (manual)"
    )
    assert manual.source == ReqSource.manual

    _disclose_luis_job_change(db, client)

    db.refresh(manual)
    assert manual.source == ReqSource.manual
    assert manual.manual_label == "Freelance 1099 (manual)"


def test_version_counter_advances_each_run(db, client):
    v0 = client.derivation_version
    _disclose_luis_job_change(db, client)
    assert client.derivation_version == v0 + 1
    # a run log row was written for the audit trail
    assert any(r.note == "Job change disclosed" for r in client.runs)


def test_dropped_slot_is_kept_but_flagged_not_deleted(db, client):
    """If a fact reverses (employer_count drops), the system stops asking for a
    slot, but we keep the row and let last_seen_version fall behind so the screen
    can show 'no longer expected' rather than silently deleting."""
    # First raise Luis to 2, then drop back to 1.
    _disclose_luis_job_change(db, client)
    luis_w2 = _reqs(client, kind=DocKind.w2, person_id=_luis(client).id)
    assert len(luis_w2) == 2

    fact = next(f for f in client.facts if f.person_id == _luis(client).id)
    fact.employer_count = 1
    db.commit()
    derivation.derive(db, client, note="Correction: back to one job")

    # The second slot still exists as a row, but was not refreshed this run.
    luis_w2 = _reqs(client, kind=DocKind.w2, person_id=_luis(client).id)
    assert len(luis_w2) == 2  # not deleted
    stale = [r for r in luis_w2 if r.last_seen_version < client.derivation_version]
    assert len(stale) == 1  # flagged as no-longer-expected
