# Architecture and how the pieces fit

Short doc. The two previous ones did the thinking; this one says how the code is
laid out and why, and how to run it.

## Stack, and why

- **FastAPI + SQLAlchemy + SQLite.** FastAPI because it gives clean typed
  endpoints and Pydantic schemas for free, and because the brief says any Python
  web framework. SQLite because it needs no setup — a reviewer clones the repo
  and runs it, no database server to install. The ORM keeps the data layer
  swappable to Postgres later with almost no change.
- **React (Vite) front end.** A small single-page app that talks to the API. The
  brief allows server-rendered pages, and honestly for this size that would have
  been less setup, but a React front end shows the three-pile screen more
  interactively and was the requested approach. I kept it deliberately small:
  a few components, plain fetch calls, no state library.
- **pytest** for the tests, run straight against the service layer with no
  browser and no running server — the brief asks for exactly that.

## The important boundary: logic is separate from the web

The rules — deriving the list, re-deriving it, routing documents on confidence,
matching them to slots — live in plain Python modules that know nothing about
HTTP. The FastAPI routers are a thin skin on top. This matters for two reasons:
the brief explicitly wants the logic testable without a browser, and keeping the
rules out of the request handlers is just where the value of the project is, so
it should be the part that is easiest to read and test.

```
backend/app/
  db.py            SQLAlchemy engine + session, SQLite file
  models.py        the tables from doc 02
  schemas.py       Pydantic request/response shapes
  classifier.py    the stubbed document-reading tool, behind one function
  derivation.py    the rules engine: build and re-derive the expected list
  documents.py     upload + confidence routing + matching to slots + review
  status.py        assembles the three-pile view for the screen
  seed.py          creates the Rivera household in its "January" state
  routers/         thin FastAPI endpoints calling the modules above
  main.py          app wiring, CORS, static serving
backend/tests/     pytest, straight against the modules above
```

`derivation.py`, `documents.py`, and `status.py` are the three files worth
reading. Everything else is plumbing.

## The classifier boundary

`classifier.py` exposes one function, `classify(filename, file_bytes) ->
Guess`. The `Guess` is exactly what the brief describes: kind, tax year, person
name, a confidence between 0 and 1, and whether the file was readable. The stub
works out kind/year/person from the filename (a client names the file something
like `Ana Rivera W-2 2025 Acme.pdf`) and opens the PDF to check it is readable
and has text, which sets `readable` and nudges confidence up or down. Files it
can't parse, or that are clearly named as bad scans, come back unreadable with
low confidence.

A real system replaces the body of that one function with an OCR/ML call and
everything downstream is unchanged. The point of isolating it is that the
interesting behaviour — what we do with a low-confidence or junk guess — does not
depend on how the guess was made.

## Re-derivation flow (the part I most care about)

1. Something changes — the accountant updates an employment fact (Luis now has 2
   employers for 2025).
2. `derivation.derive(client)` runs. It bumps `client.derivation_version`, writes
   a `derivation_runs` row, computes the set of expected slot-keys from the facts
   and people, and for each key either refreshes the existing `system` requirement
   (updating `last_seen_version`) or creates a new one. It never reads or writes
   the human flags (`waived`, `removed`) and never touches `manual` rows.
3. The screen re-reads and the new slot appears, everything else exactly as the
   accountant left it.

## How to run it

Full steps are in the top-level README. In short: create a Python venv, install
`backend/requirements.txt`, run the seed, start uvicorn; then `npm install` and
`npm run dev` in `frontend`. The API defaults to SQLite in a local file so there
is nothing else to stand up.
