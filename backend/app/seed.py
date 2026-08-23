"""Seed the Rivera household in its 'January' state.

The demo scenario from the brief:
  - Rivera household, filing jointly, tax year 2025
  - Ana (taxpayer, 2 jobs), Luis (spouse, 1 job in January), Mateo (child)

We seed the state as it was known in JANUARY, i.e. before anyone disclosed
Luis's job change. So Luis starts with employer_count = 1. The demo then
discloses the change (bumping Luis to 2 and re-deriving), which is the whole
point of the exercise. See docs/01.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import derivation
from app.db import SessionLocal, init_db
from app.models import Client, EmploymentFact, Person, PersonRole


def seed(db: Session) -> Client:
    # Start clean so the seed is repeatable.
    for c in db.query(Client).all():
        db.delete(c)
    db.commit()

    client = Client(name="Rivera household", tax_year=2025, filing_status="married_joint")
    db.add(client)
    db.commit()
    db.refresh(client)

    ana = Person(client_id=client.id, name="Ana Rivera", role=PersonRole.taxpayer)
    luis = Person(client_id=client.id, name="Luis Rivera", role=PersonRole.spouse)
    mateo = Person(client_id=client.id, name="Mateo Rivera", role=PersonRole.dependent)
    db.add_all([ana, luis, mateo])
    db.commit()
    db.refresh(ana)
    db.refresh(luis)

    # January facts: Ana 2 employers, Luis 1 employer. Mateo none.
    db.add_all(
        [
            EmploymentFact(client_id=client.id, person_id=ana.id, tax_year=2025, employer_count=2,
                           note="Two jobs, same as last year"),
            EmploymentFact(client_id=client.id, person_id=luis.id, tax_year=2025, employer_count=1,
                           note="One job (as known in January)"),
        ]
    )
    db.commit()

    derivation.derive(db, client, note="Initial derivation (January)")
    db.refresh(client)
    return client


if __name__ == "__main__":
    init_db()
    with SessionLocal() as db:
        c = seed(db)
        print(f"Seeded client {c.id}: {c.name}, tax year {c.tax_year}")
        print(f"Derivation version: {c.derivation_version}")
        print(f"Requirements: {len(c.requirements)} (expected 6 in January state)")
