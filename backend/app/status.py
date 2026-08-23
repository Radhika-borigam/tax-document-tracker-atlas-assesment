"""Assemble the screen: the three piles the brief asks for.

  - outstanding: expected, not waived/removed, not yet received
  - received:    an expected slot with an accepted document
  - needs_attention: documents in the review queue, plus system-vs-human oddities

Pure read model. It only reads what the other modules wrote.
"""
from __future__ import annotations

from app.models import (
    Client,
    DocKind,
    Document,
    DocStatus,
    Person,
    Requirement,
)

_KIND_LABEL = {
    DocKind.prior_year_1040: "Prior-year return (1040)",
    DocKind.government_id: "Government ID",
    DocKind.w2: "W-2",
}


def _person_name(client: Client, person_id: int | None) -> str | None:
    if person_id is None:
        return None
    p = next((p for p in client.people if p.id == person_id), None)
    return p.name if p else None


def requirement_label(client: Client, req: Requirement) -> str:
    if req.manual_label:
        base = req.manual_label
    else:
        base = _KIND_LABEL.get(req.kind, req.kind.value)
    who = _person_name(client, req.person_id)
    parts = [base]
    if who:
        parts.append(f"— {who}")
    if req.kind == DocKind.w2:
        parts.append(f"(employer #{req.slot_index})")
    if req.doc_tax_year:
        parts.append(f"[{req.doc_tax_year}]")
    return " ".join(parts)


def _accepted_docs(req: Requirement) -> list[Document]:
    return [d for d in req.documents if d.status == DocStatus.accepted]


def build_status(client: Client) -> dict:
    """Return the full view model for one client's collection screen."""
    outstanding = []
    received = []

    for req in client.requirements:
        if req.removed:
            continue
        accepted = _accepted_docs(req)
        no_longer_expected = (
            req.source.value == "system" and req.last_seen_version < client.derivation_version
        )
        item = {
            "requirement_id": req.id,
            "label": requirement_label(client, req),
            "kind": req.kind.value,
            "person": _person_name(client, req.person_id),
            "doc_tax_year": req.doc_tax_year,
            "slot_index": req.slot_index,
            "source": req.source.value,
            "waived": req.waived,
            "waived_reason": req.waived_reason,
            "no_longer_expected": no_longer_expected,
        }
        if accepted:
            item["documents"] = [
                {"id": d.id, "filename": d.original_filename, "confidence": d.confidence}
                for d in accepted
            ]
            received.append(item)
        elif req.waived:
            # Waived items are shown as resolved-by-decision, not outstanding.
            item["resolution"] = "waived"
            received.append(item)
        else:
            outstanding.append(item)

    needs_attention = []
    for d in client.documents:
        if d.status != DocStatus.needs_review:
            continue
        needs_attention.append(
            {
                "id": d.id,
                "filename": d.original_filename,
                "guessed_kind": d.guessed_kind.value if d.guessed_kind else None,
                "guessed_tax_year": d.guessed_tax_year,
                "guessed_person_name": d.guessed_person_name,
                "confidence": d.confidence,
                "readable": d.readable,
                "review_reason": d.review_reason.value if d.review_reason else None,
            }
        )

    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "tax_year": client.tax_year,
            "filing_status": client.filing_status,
            "derivation_version": client.derivation_version,
        },
        "summary": {
            "outstanding": len(outstanding),
            "received": len([r for r in received if r.get("resolution") != "waived"]),
            "waived": len([r for r in received if r.get("resolution") == "waived"]),
            "needs_attention": len(needs_attention),
        },
        "outstanding": outstanding,
        "received": received,
        "needs_attention": needs_attention,
    }
