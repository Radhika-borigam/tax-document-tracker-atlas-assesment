"""Pydantic request bodies for the API. Response shapes are plain dicts built by
status.py, which keeps the view model in one place."""
from __future__ import annotations

from pydantic import BaseModel

from app.models import DocKind


class WaiveIn(BaseModel):
    reason: str | None = None


class AcceptIn(BaseModel):
    kind: DocKind | None = None
    tax_year: int | None = None
    person_id: int | None = None
    requirement_id: int | None = None
    note: str | None = None


class RejectIn(BaseModel):
    note: str | None = None


class ManualRequirementIn(BaseModel):
    kind: DocKind
    person_id: int | None = None
    doc_tax_year: int | None = None
    label: str | None = None


class FactUpdateIn(BaseModel):
    person_id: int
    tax_year: int
    employer_count: int
    note: str | None = None


class RederiveIn(BaseModel):
    note: str | None = None
