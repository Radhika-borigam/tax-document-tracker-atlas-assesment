"""Generate a corpus of real PDF files for the Rivera household to test with.

The brief says to gather real files and include the awkward cases. These are
genuine PDFs (real text layers, real bytes), named the way a client would name
them. We generate them rather than ship IRS blanks so that each file carries the
right kind / year / person for the scenario, and so the awkward cases (wrong
year, unknown person, unreadable scan) exist on purpose.

Run: python scripts/generate_sample_docs.py
Output: sample_documents/rivera/
"""
from __future__ import annotations

import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_documents", "rivera")
os.makedirs(OUT, exist_ok=True)


def _form_pdf(path: str, title: str, lines: list[str]) -> None:
    """A plain but real form-like PDF with an extractable text layer."""
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 90, title)
    c.setFont("Helvetica", 11)
    y = height - 130
    for line in lines:
        c.drawString(72, y, line)
        y -= 22
    # a couple of boxes so it looks like a form, not just a memo
    c.rect(72, 120, 460, 260, stroke=1, fill=0)
    c.save()


def _unreadable_scan(path: str) -> None:
    """A PDF that is all graphics and no text layer — i.e. a scan we can't read.
    pypdf.extract_text() returns nothing, so the classifier flags it unreadable."""
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter
    # Draw noise-like lines only; deliberately no drawString calls => no text.
    for i in range(0, int(width), 12):
        c.line(i, 0, i, height)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.rect(120, 300, 360, 180, stroke=0, fill=1)
    c.save()


def main() -> None:
    # --- the documents we actually expect (the happy path) ---
    _form_pdf(
        os.path.join(OUT, "Rivera 1040 2024.pdf"),
        "Form 1040 - U.S. Individual Income Tax Return",
        ["Tax Year 2024", "Taxpayer: Ana Rivera", "Spouse: Luis Rivera",
         "Filing status: Married filing jointly"],
    )
    _form_pdf(
        os.path.join(OUT, "Ana Rivera W-2 2025 Acme Corp.pdf"),
        "Form W-2 - Wage and Tax Statement",
        ["Tax Year 2025", "Employee: Ana Rivera", "Employer: Acme Corp"],
    )
    _form_pdf(
        os.path.join(OUT, "Ana Rivera W-2 2025 Globex.pdf"),
        "Form W-2 - Wage and Tax Statement",
        ["Tax Year 2025", "Employee: Ana Rivera", "Employer: Globex Inc"],
    )
    _form_pdf(
        os.path.join(OUT, "Luis Rivera W-2 2025 Initech.pdf"),
        "Form W-2 - Wage and Tax Statement",
        ["Tax Year 2025", "Employee: Luis Rivera", "Employer: Initech LLC"],
    )
    # Luis's second W-2, the one that only appears after the March disclosure.
    _form_pdf(
        os.path.join(OUT, "Luis Rivera W-2 2025 Umbrella.pdf"),
        "Form W-2 - Wage and Tax Statement",
        ["Tax Year 2025", "Employee: Luis Rivera", "Employer: Umbrella Co (new job June 2025)"],
    )
    _form_pdf(
        os.path.join(OUT, "Ana Rivera drivers license.pdf"),
        "State of Illinois - Driver License",
        ["Name: Ana Rivera", "A government-issued photo ID"],
    )
    _form_pdf(
        os.path.join(OUT, "Luis Rivera passport.pdf"),
        "United States Passport",
        ["Name: Luis Rivera", "A government-issued photo ID"],
    )

    # --- the awkward cases the brief asks for ---

    # 1. Wrong year: a W-2 for 2024 when we want 2025.
    _form_pdf(
        os.path.join(OUT, "Ana Rivera W-2 2024 Acme Corp.pdf"),
        "Form W-2 - Wage and Tax Statement",
        ["Tax Year 2024", "Employee: Ana Rivera", "Employer: Acme Corp"],
    )
    # 2. A person nobody asked about (not on this return).
    _form_pdf(
        os.path.join(OUT, "Carla Cousin W-2 2025 Soylent.pdf"),
        "Form W-2 - Wage and Tax Statement",
        ["Tax Year 2025", "Employee: Carla Cousin", "Employer: Soylent Corp"],
    )
    # 3. A scan that cannot be read at all.
    _unreadable_scan(os.path.join(OUT, "scan_unreadable.pdf"))
    # 4. A low-confidence case: badly named, few signals in the filename.
    _form_pdf(
        os.path.join(OUT, "IMG_20250412.pdf"),
        "Form W-2 - Wage and Tax Statement",
        ["Tax Year 2025", "Employee: someone", "Employer: unclear"],
    )

    files = sorted(os.listdir(OUT))
    print(f"Wrote {len(files)} sample files to {OUT}:")
    for f in files:
        print("  -", f)


if __name__ == "__main__":
    main()
