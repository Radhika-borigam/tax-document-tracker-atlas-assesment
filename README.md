# Document Collection

A screen that shows a tax accountant where a client stands on the documents
needed to file their return: what has arrived, what is still missing, and what
needs a human to look at it.

Built for take-home assignment A. The short version of what it does:

- It **derives** the list of expected documents from facts about the household,
  and **re-derives** it when the client discloses something late — without
  wiping out the edits the accountant made in the meantime. This is the hard
  part of the brief and the part I put the most care into.
- It takes in documents as they arrive, runs each through a **classifier** that
  guesses what the file is and how sure it is, and **only auto-files the clean,
  confident ones**. Everything shaky — low confidence, unreadable scans, wrong
  year, unknown people, no matching slot — goes to a **review pile** for the
  accountant.

> **Read the thinking first.** The `docs/` folder is where I worked the problem
> out before writing code, and it is the most important part of this submission.
> Start with [`docs/01-understanding-the-problem.md`](docs/01-understanding-the-problem.md).

## The docs

| File | What's in it |
|---|---|
| [`docs/01-understanding-the-problem.md`](docs/01-understanding-the-problem.md) | What is actually being asked, the three hard problems hiding in the brief, and the Rivera example worked out by hand. |
| [`docs/02-domain-model-and-decisions.md`](docs/02-domain-model-and-decisions.md) | The tables, the one idea they hang off (keep the system's opinion and the human's decisions in separate columns), and every judgement call I made. |
| [`docs/03-architecture.md`](docs/03-architecture.md) | Stack, how the code is laid out, and the classifier boundary. |
| [`docs/04-demo-script.md`](docs/04-demo-script.md) | The walkthrough I follow in the video. |

## How to run it

You need Python 3.11+ and Node 18+. SQLite is the database, so there is nothing
else to install or stand up.

### Backend (the API)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On first start it creates the SQLite database and **seeds the Rivera household in
its "January" state** (before Luis's job change is known), so the app is useful
immediately. API docs are at http://localhost:8000/docs.

There is also a shortcut: `./scripts/run_backend.sh` (creates the venv and
installs deps for you).

### Frontend (the screen)

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173. The dev server proxies `/api` to the backend,
so both run happily side by side. Shortcut: `./scripts/run_frontend.sh`.

If you would rather run everything from one process, build the frontend
(`cd frontend && npm run build`) and the backend will serve it at
http://localhost:8000.

### The sample documents

Real PDF files for the Rivera household are in `sample_documents/rivera/`,
including the three awkward cases the brief asks for (a wrong-year form, a form
for someone not on the return, and an unreadable scan). Regenerate them any time
with:

```bash
backend/.venv/bin/python scripts/generate_sample_docs.py
```

Upload these through the screen to see the classifier and the review pile work on
real files.

## The tests

The logic that matters is tested without a browser or a running server, straight
against the service functions:

```bash
cd backend
source .venv/bin/activate
pytest
```

What they cover:

- **`test_derivation.py`** — the rules engine produces exactly the list I worked
  out by hand: one prior-year 1040 for 2024, an ID per adult (not the child),
  and one W-2 per employer.
- **`test_rederivation.py`** — the crown jewel. Re-deriving after a late
  disclosure adds the new slot, does not duplicate the others, and leaves waived
  items, removed items and manual additions exactly as the accountant left them.
- **`test_documents.py`** — the document lifecycle: every confidence-routing and
  junk-catching branch, plus review, correction and rejection.
- **`test_real_files.py`** — runs the real classifier over the actual sample
  PDFs, end to end, including the three awkward cases.

## What I decided (where the brief left it open)

These are covered in full in `docs/02`, but the headlines:

- **"Needed by everyone" means every adult filer**, not literally every person.
  The 1040 is one household document; government IDs are per adult; a dependent
  child needs neither an ID nor a W-2.
- **The prior-year 1040 is for the year before the engagement** (filing 2025 →
  we want the 2024 return). That is what makes the wrong-year check meaningful.
- **A W-2 is expected per employer in the tax year.** Both worked examples in the
  brief ("two jobs again", "one job plus a mid-year change") reduce to counting
  employers.
- **Confidence threshold is 0.70.** Below it, nothing is auto-filed.
- **In any conflict, the human wins over the system,** and re-derivation never
  hard-deletes anything.
- **The classifier is a stub behind one function.** It reads the filename and
  peeks at the PDF's text. A real OCR/ML model implements the same interface and
  nothing downstream changes.

## What I left out, and what I'd do next

Left out on purpose, to spend the time on the parts that matter:

- A real OCR/ML classifier (stubbed behind a clean interface instead).
- Auth, multiple accountants, and permissions.
- Multiple clients in the UI (the data model and API support many; the screen
  shows the first one).
- Fancy visual design.

What I'd do next, roughly in order:

1. **Surface system-vs-human conflicts explicitly** — e.g. "you removed this, but
   the system now expects it again" as its own attention item, rather than just
   respecting the human silently.
2. **Split "household" from "per-year engagement"** so a client's history across
   tax years is clean.
3. **A proper audit log** of every human action, not just the derivation runs.
4. **Duplicate detection** — the same W-2 arriving twice from two family members.
5. **Tune the confidence threshold** against real classifier error rates, and
   make it per-document-kind.

## Project layout

```
docs/                 the reasoning (read this first)
backend/
  app/
    derivation.py     the rules engine: build & re-derive the list  ← core
    documents.py      classify → route on confidence → match to slots  ← core
    status.py         assemble the three-pile view
    classifier.py     the stubbed document-reading tool
    models.py         the tables
    routers/          thin FastAPI endpoints
    seed.py           the Rivera household in its January state
  tests/              pytest, run without a browser
frontend/             React (Vite) single-page screen
sample_documents/     real PDFs, including the awkward cases
scripts/              run + sample-generation helpers
```
