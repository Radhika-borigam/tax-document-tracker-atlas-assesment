"""The stubbed document-reading tool.

The brief describes a tool that reads each file and guesses its kind, tax year,
whose it is, and how confident it is, and that is "usually right and occasionally
badly wrong". This module is that tool, behind one function: `classify`.

The stub reads the filename (a client names a file something like
"Ana Rivera W-2 2025 Acme.pdf") for kind / year / person, and opens the PDF to
decide whether it is readable and to nudge confidence. A real OCR/ML classifier
would replace the body of `classify` and nothing downstream would change.

Determinism note: classification is a pure function of (filename, bytes), so the
tests are deterministic. To simulate the "occasionally badly wrong" case without
randomness, a filename can carry an explicit hint like "conf=0.4" or the token
"unreadable"; this is only a testing affordance and is documented as such.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

from app.models import DocKind


@dataclass
class Guess:
    kind: DocKind | None
    tax_year: int | None
    person_name: str | None
    confidence: float
    readable: bool


# Signals that identify each kind of document from a filename.
_KIND_PATTERNS = [
    (DocKind.w2, re.compile(r"\bw-?2\b", re.I)),
    (DocKind.prior_year_1040, re.compile(r"\b1040\b", re.I)),
    (DocKind.government_id, re.compile(r"\b(id|passport|licen[cs]e|dl)\b", re.I)),
]
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_CONF_OVERRIDE_RE = re.compile(r"conf=([01](?:\.\d+)?)", re.I)


def _pdf_is_readable(file_bytes: bytes) -> tuple[bool, str]:
    """Return (readable, extracted_text). A scan with no text layer counts as
    unreadable, which is exactly the 'scan that cannot be read' case."""
    if not file_bytes:
        return False, ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        return (len(text.strip()) >= 10), text
    except Exception:
        # Corrupt file, not a PDF, or an image-only scan we can't parse.
        return False, ""


def _guess_person(filename: str, known_names: list[str]) -> tuple[str | None, bool]:
    """Match the filename against the household's names. Returns (name, matched)."""
    lower = filename.lower()
    for name in known_names:
        first = name.split()[0].lower()
        if first in lower or name.lower() in lower:
            return name, True
    return None, False


def classify(filename: str, file_bytes: bytes, known_names: list[str] | None = None) -> Guess:
    """Read a file and guess what it is. See module docstring."""
    known_names = known_names or []
    name = filename or ""

    # An explicit "unreadable" marker or an unparseable PDF => cannot be read.
    readable, text = _pdf_is_readable(file_bytes)
    if "unreadable" in name.lower() or "corrupt" in name.lower():
        readable = False

    if not readable:
        # Nothing to go on. Low confidence, flagged for a human.
        return Guess(kind=None, tax_year=None, person_name=None, confidence=0.15, readable=False)

    haystack = f"{name}\n{text}"

    # --- kind --- (filename first, fall back to the document's own text)
    kind: DocKind | None = None
    kind_from_content = False
    for k, pat in _KIND_PATTERNS:
        if pat.search(name):
            kind = k
            break
    if kind is None:
        for k, pat in _KIND_PATTERNS:
            if pat.search(text):
                kind, kind_from_content = k, True
                break

    # --- year --- (filename first, then content)
    years = _YEAR_RE.findall(name) or _YEAR_RE.findall(text)
    tax_year = int(years[0]) if years else None

    # --- person ---
    person_name, person_matched = _guess_person(haystack, known_names)

    # --- confidence ---
    # Start from how many independent signals we found, then apply any explicit
    # override used by the test corpus to simulate a shaky read.
    signals = sum(x is not None for x in (kind, tax_year)) + (1 if person_matched else 0)
    confidence = {0: 0.2, 1: 0.45, 2: 0.75, 3: 0.9}[min(signals, 3)]
    # A kind recovered only from OCR'd content (not the filename) is shakier than
    # one the client named explicitly, so trim confidence a little.
    if kind_from_content:
        confidence -= 0.1
    # Government IDs legitimately have no year, so don't penalise them for it.
    if kind is DocKind.government_id and person_matched:
        confidence = max(confidence, 0.85)

    override = _CONF_OVERRIDE_RE.search(name)
    if override:
        confidence = float(override.group(1))

    return Guess(
        kind=kind,
        tax_year=tax_year,
        person_name=person_name,
        confidence=round(confidence, 2),
        readable=True,
    )
