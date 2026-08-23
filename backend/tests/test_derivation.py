"""The rules engine produces the list I worked out by hand in docs/01."""
from __future__ import annotations

from app.derivation import expected_slots
from app.models import DocKind, PersonRole


def _slots(client):
    return expected_slots(client, list(client.people), list(client.facts))


def test_january_list_has_six_items(client):
    # 1 prior-year 1040 + 2 government IDs + 2 W-2s (Ana) + 1 W-2 (Luis) = 6.
    slots = _slots(client)
    assert len(slots) == 6


def test_prior_year_1040_is_one_household_item_for_the_year_before(client):
    tens = [s for s in slots(client) if s.kind == DocKind.prior_year_1040]
    assert len(tens) == 1
    assert tens[0].person_id is None  # household-level, not per person
    assert tens[0].doc_tax_year == 2024  # the year before the 2025 engagement


def test_government_id_per_adult_not_for_the_child(client):
    ids = [s for s in slots(client) if s.kind == DocKind.government_id]
    adult_ids = {p.id for p in client.people if p.role in (PersonRole.taxpayer, PersonRole.spouse)}
    child_ids = {p.id for p in client.people if p.role == PersonRole.dependent}
    assert {s.person_id for s in ids} == adult_ids
    assert not (child_ids & {s.person_id for s in ids})
    assert all(s.doc_tax_year is None for s in ids)  # IDs have no tax year


def test_w2_count_matches_employer_count(client):
    ana = next(p for p in client.people if p.name.startswith("Ana"))
    luis = next(p for p in client.people if p.name.startswith("Luis"))
    w2 = [s for s in slots(client) if s.kind == DocKind.w2]
    ana_w2 = [s for s in w2 if s.person_id == ana.id]
    luis_w2 = [s for s in w2 if s.person_id == luis.id]
    assert len(ana_w2) == 2  # two jobs
    assert len(luis_w2) == 1  # one job, as known in January
    assert all(s.doc_tax_year == 2025 for s in w2)
    # slots are indexed 1..n so they have stable identities
    assert {s.slot_index for s in ana_w2} == {1, 2}


def test_child_with_no_fact_has_no_w2(client):
    mateo = next(p for p in client.people if p.name.startswith("Mateo"))
    w2 = [s for s in slots(client) if s.kind == DocKind.w2]
    assert all(s.person_id != mateo.id for s in w2)


# small helper so tests read nicely
def slots(client):
    return _slots(client)
