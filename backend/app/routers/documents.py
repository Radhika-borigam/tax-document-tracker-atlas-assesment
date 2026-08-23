"""Endpoints for documents: upload (with classification + routing), review."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import documents as docsvc
from app.db import get_db
from app.models import Client, Document
from app.schemas import AcceptIn, RejectIn

router = APIRouter(prefix="/api", tags=["documents"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    return client


def _get_document(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


def _doc_view(doc: Document) -> dict:
    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "guessed_kind": doc.guessed_kind.value if doc.guessed_kind else None,
        "guessed_tax_year": doc.guessed_tax_year,
        "guessed_person_name": doc.guessed_person_name,
        "confidence": doc.confidence,
        "readable": doc.readable,
        "status": doc.status.value,
        "review_reason": doc.review_reason.value if doc.review_reason else None,
        "matched_requirement_id": doc.matched_requirement_id,
    }


@router.post("/clients/{client_id}/documents")
async def upload_document(
    client_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """A file arrives. We save it, run the classifier, route on confidence, and
    auto-match only if it is clean and confident."""
    client = _get_client(db, client_id)
    content = await file.read()

    stored_name = f"{uuid.uuid4().hex}_{file.filename}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)
    with open(stored_path, "wb") as fh:
        fh.write(content)

    doc = docsvc.ingest(db, client, file.filename, content)
    doc.stored_path = stored_path
    db.commit()
    db.refresh(doc)
    return _doc_view(doc)


@router.get("/clients/{client_id}/documents")
def list_documents(client_id: int, db: Session = Depends(get_db)):
    client = _get_client(db, client_id)
    return [_doc_view(d) for d in client.documents]


@router.post("/documents/{doc_id}/accept")
def accept(doc_id: int, body: AcceptIn, db: Session = Depends(get_db)):
    doc = _get_document(db, doc_id)
    client = _get_client(db, doc.client_id)
    docsvc.accept_document(
        db, client, doc,
        kind=body.kind, tax_year=body.tax_year, person_id=body.person_id,
        requirement_id=body.requirement_id, note=body.note,
    )
    return _doc_view(doc)


@router.post("/documents/{doc_id}/reject")
def reject(doc_id: int, body: RejectIn, db: Session = Depends(get_db)):
    doc = _get_document(db, doc_id)
    docsvc.reject_document(db, doc, note=body.note)
    return _doc_view(doc)
