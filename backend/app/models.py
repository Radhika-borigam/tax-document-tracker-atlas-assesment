"""The tables. See docs/02-domain-model-and-decisions.md for the reasoning.

The one idea to keep in mind while reading this: on every model that both the
system and a human write to (Requirement, Document), the system's opinion and
the human's decision live in *different* columns, so re-running the system can
never overwrite a human decision.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- enums -----------------------------------------------------------------


class PersonRole(str, enum.Enum):
    taxpayer = "taxpayer"
    spouse = "spouse"
    dependent = "dependent"


class DocKind(str, enum.Enum):
    prior_year_1040 = "prior_year_1040"
    government_id = "government_id"
    w2 = "w2"


class ReqSource(str, enum.Enum):
    system = "system"  # produced by the rules engine
    manual = "manual"  # added by the accountant; the engine never touches it


class DocStatus(str, enum.Enum):
    needs_review = "needs_review"
    accepted = "accepted"
    rejected = "rejected"


class ReviewReason(str, enum.Enum):
    low_confidence = "low_confidence"
    unreadable = "unreadable"
    wrong_year = "wrong_year"
    unknown_person = "unknown_person"
    no_matching_slot = "no_matching_slot"


# --- tables ----------------------------------------------------------------


class Client(Base):
    """One engagement: a household filing for one tax year."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    tax_year: Mapped[int] = mapped_column(Integer)
    filing_status: Mapped[str] = mapped_column(String(50), default="married_joint")
    # Ticks up on every re-derivation; lets us tell which items the system still asks for.
    derivation_version: Mapped[int] = mapped_column(Integer, default=0)

    people: Mapped[list["Person"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    facts: Mapped[list["EmploymentFact"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    runs: Mapped[list["DerivationRun"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[PersonRole] = mapped_column(Enum(PersonRole))

    client: Mapped["Client"] = relationship(back_populates="people")


class EmploymentFact(Base):
    """The disclosed facts that drive W-2 derivation.

    We store *employers this year* (the thing that determines the W-2 count),
    not a pre-computed count of documents, so re-derivation is just re-running
    the rule over an updated fact.
    """

    __tablename__ = "employment_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"))
    tax_year: Mapped[int] = mapped_column(Integer)
    employer_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    client: Mapped["Client"] = relationship(back_populates="facts")


class Requirement(Base):
    """An expected document slot.

    The five identity columns (kind, person, doc_tax_year, slot_index, client)
    form the stable key that lets re-derivation recognise the same slot across
    runs. `source`/`last_seen_version` are the system's side; `waived`/`removed`
    are the human's side and are never written by re-derivation.
    """

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))

    # --- stable identity ---
    kind: Mapped[DocKind] = mapped_column(Enum(DocKind))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    doc_tax_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slot_index: Mapped[int] = mapped_column(Integer, default=1)

    # --- the system's side ---
    source: Mapped[ReqSource] = mapped_column(Enum(ReqSource), default=ReqSource.system)
    last_seen_version: Mapped[int] = mapped_column(Integer, default=0)

    # --- the human's side (never touched by re-derivation) ---
    waived: Mapped[bool] = mapped_column(Boolean, default=False)
    waived_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_label: Mapped[str | None] = mapped_column(String(200), nullable=True)  # for manual rows

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    client: Mapped["Client"] = relationship(back_populates="requirements")
    person: Mapped["Person | None"] = relationship()
    documents: Mapped[list["Document"]] = relationship(back_populates="matched_requirement")

    def identity(self) -> tuple:
        """The stable key used to match against a freshly derived slot."""
        return (self.kind, self.person_id, self.doc_tax_year, self.slot_index)


class Document(Base):
    """A file that actually arrived.

    Three groups: the file, the classifier's guess, and the human's verdict.
    The guess columns and the human-correction columns are separate so a human
    fixing a bad guess never erases what the tool originally thought.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))

    # --- the file ---
    original_filename: Mapped[str] = mapped_column(String(400))
    stored_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # --- the classifier's guess ---
    guessed_kind: Mapped[DocKind | None] = mapped_column(Enum(DocKind), nullable=True)
    guessed_tax_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guessed_person_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    readable: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- the human's verdict / outcome ---
    status: Mapped[DocStatus] = mapped_column(Enum(DocStatus), default=DocStatus.needs_review)
    review_reason: Mapped[ReviewReason | None] = mapped_column(Enum(ReviewReason), nullable=True)
    matched_requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)

    # human corrections to the guess (set during review)
    human_kind: Mapped[DocKind | None] = mapped_column(Enum(DocKind), nullable=True)
    human_tax_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    human_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="documents")
    matched_requirement: Mapped["Requirement | None"] = relationship(back_populates="documents")

    # convenience: the effective (human-corrected, else guessed) values
    @property
    def effective_kind(self) -> DocKind | None:
        return self.human_kind or self.guessed_kind

    @property
    def effective_tax_year(self) -> int | None:
        return self.human_tax_year if self.human_tax_year is not None else self.guessed_tax_year


class DerivationRun(Base):
    """A log row per derivation, so 'the list is derived more than once' is visible."""

    __tablename__ = "derivation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    refreshed_count: Mapped[int] = mapped_column(Integer, default=0)

    client: Mapped["Client"] = relationship(back_populates="runs")
