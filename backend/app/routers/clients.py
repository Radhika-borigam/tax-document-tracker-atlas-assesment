"""Endpoints for the client screen: status, facts, re-derivation, requirements."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import derivation, status
from app.db import get_db
from app.models import Client, EmploymentFact, Requirement
from app.schemas import (
    FactUpdateIn,
    ManualRequirementIn,
    RederiveIn,
    WaiveIn,
)

router = APIRouter(prefix="/api", tags=["clients"])


def _get_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    return client


def _get_requirement(db: Session, req_id: int) -> Requirement:
    req = db.get(Requirement, req_id)
    if not req:
        raise HTTPException(404, "Requirement not found")
    return req


@router.get("/clients")
def list_clients(db: Session = Depends(get_db)):
    return [
        {"id": c.id, "name": c.name, "tax_year": c.tax_year, "filing_status": c.filing_status}
        for c in db.query(Client).all()
    ]


@router.get("/clients/{client_id}/status")
def client_status(client_id: int, db: Session = Depends(get_db)):
    return status.build_status(_get_client(db, client_id))


@router.get("/clients/{client_id}/people")
def client_people(client_id: int, db: Session = Depends(get_db)):
    client = _get_client(db, client_id)
    return [{"id": p.id, "name": p.name, "role": p.role.value} for p in client.people]


@router.get("/clients/{client_id}/facts")
def client_facts(client_id: int, db: Session = Depends(get_db)):
    client = _get_client(db, client_id)
    return [
        {
            "id": f.id,
            "person_id": f.person_id,
            "tax_year": f.tax_year,
            "employer_count": f.employer_count,
            "note": f.note,
        }
        for f in client.facts
    ]


@router.get("/clients/{client_id}/runs")
def client_runs(client_id: int, db: Session = Depends(get_db)):
    client = _get_client(db, client_id)
    return [
        {
            "version": r.version,
            "note": r.note,
            "added": r.added_count,
            "refreshed": r.refreshed_count,
            "created_at": r.created_at.isoformat(),
        }
        for r in sorted(client.runs, key=lambda r: r.version)
    ]


@router.put("/clients/{client_id}/facts")
def update_fact(client_id: int, body: FactUpdateIn, db: Session = Depends(get_db)):
    """Disclose or correct an employment fact. This is what changes in March when
    Luis's job change surfaces. It does NOT re-derive on its own — the caller
    triggers re-derivation explicitly, so the two steps are visible."""
    client = _get_client(db, client_id)
    fact = next(
        (f for f in client.facts if f.person_id == body.person_id and f.tax_year == body.tax_year),
        None,
    )
    if fact:
        fact.employer_count = body.employer_count
        fact.note = body.note
    else:
        fact = EmploymentFact(
            client_id=client.id,
            person_id=body.person_id,
            tax_year=body.tax_year,
            employer_count=body.employer_count,
            note=body.note,
        )
        db.add(fact)
    db.commit()
    return {"ok": True}


@router.post("/clients/{client_id}/rederive")
def rederive(client_id: int, body: RederiveIn, db: Session = Depends(get_db)):
    """Re-run derivation, merging into the existing list without touching human
    decisions. Returns what changed."""
    client = _get_client(db, client_id)
    run = derivation.derive(db, client, note=body.note or "Manual re-derivation")
    return {"version": run.version, "added": run.added_count, "refreshed": run.refreshed_count}


@router.post("/clients/{client_id}/requirements")
def add_requirement(client_id: int, body: ManualRequirementIn, db: Session = Depends(get_db)):
    client = _get_client(db, client_id)
    req = derivation.add_manual_requirement(
        db, client, body.kind, body.person_id, body.doc_tax_year, body.label
    )
    return {"id": req.id}


@router.post("/requirements/{req_id}/waive")
def waive(req_id: int, body: WaiveIn, db: Session = Depends(get_db)):
    req = _get_requirement(db, req_id)
    derivation.waive_requirement(db, req, body.reason)
    return {"ok": True}


@router.post("/requirements/{req_id}/unwaive")
def unwaive(req_id: int, db: Session = Depends(get_db)):
    req = _get_requirement(db, req_id)
    derivation.unwaive_requirement(db, req)
    return {"ok": True}


@router.post("/requirements/{req_id}/remove")
def remove(req_id: int, db: Session = Depends(get_db)):
    req = _get_requirement(db, req_id)
    derivation.remove_requirement(db, req)
    return {"ok": True}
