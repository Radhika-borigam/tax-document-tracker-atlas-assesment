# The data model, and the decisions behind it

This is the doc where I commit to a shape for the data and explain why each table
looks the way it does. The whole model is bent around one requirement from the
brief: the system derives the list more than once, and the second derivation must
not destroy what the accountant did in between. If you understand that, the
tables explain themselves.

## The one idea everything hangs off

Keep the **system's opinion** and the **human's decisions** in separate columns,
never in the same one.

The system's opinion is "I expect Luis to have two W-2s for 2025." The human's
decision is "I've marked Ana's second W-2 as not needed" or "I added a request
for a 1099 the system didn't know about." If those two kinds of information live
in the same field, then re-running the system has to write over the human's work,
and we lose it. If they live in different fields, re-derivation can refresh the
system's side and physically cannot touch the human's side. That is the whole
trick, and it is why an expected item is not just a row that gets rewritten each
time.

## The tables

### `clients`

One row per engagement — a household plus the tax year we are filing. Fields:
name (`"Rivera household"`), `tax_year` (2025), `filing_status`
(`married_joint` etc.), and a `derivation_version` counter that ticks up every
time we re-derive. The version counter is what lets me say "this expected item
was last confirmed by the system in run 2" and spot items the system has stopped
asking for.

I folded "household" and "the return for a given year" into one `clients` row to
keep things simple. In a bigger system you would separate the household from the
per-year engagement so history is cleaner. I note that as a next step rather than
build it now.

### `people`

The members of the household: name and `role` (`taxpayer`, `spouse`,
`dependent`). W-2 expectations are per person, and government-ID expectations
depend on role, so the people table is a first-class input to derivation, not
decoration.

### `employment_facts`

This is the input to the rules engine — the disclosed facts about who worked
where. Rather than storing "expected W-2 count" (an answer), I store the facts
that *produce* the count, so that re-derivation is just re-running the rules over
updated facts. Per person I store, for a given tax year, how many employers they
had, and whether a mid-year job change happened. Concretely:

- `person_id`
- `tax_year`
- `employer_count` — how many employers paid this person during that year
- `note` — free text like "changed jobs in June", for the human reading it

The Rivera facts become: Ana 2025 → 2 employers; Luis 2025 → in January this
row says 1 employer, and in March it is updated to 2 with a note about the job
change. Re-deriving after that edit is what produces Luis's second W-2 slot. I
model the fact as "employers this year" rather than "jobs last year plus
changes" because that is the thing that actually determines W-2 count, and it
keeps the rule a one-liner: **W-2s expected = employers that year.** The "two
jobs last year → two again" and "one job plus a June change → two" cases from the
brief both reduce to counting employers in the tax year.

### `requirements` — the expected items, the heart of it

One row per expected document *slot*. This is where the system's opinion and the
human's decisions sit side by side but separated.

Identity (the part that must be stable across re-derivations):

- `client_id`
- `kind` — `prior_year_1040`, `government_id`, or `w2`
- `person_id` — null for the household 1040, set for IDs and W-2s
- `doc_tax_year` — 2024 for the prior-year 1040, 2025 for W-2s, null for IDs
- `slot_index` — 1, 2, ... to tell Ana's first W-2 from her second

Those five fields together are the stable key. When the system re-derives, it
computes the same keys and matches them to existing rows, so "Luis's second W-2
for 2025" is recognised as the same slot every time instead of being recreated.

The system's side:

- `source` — `system` or `manual`. `system` rows are owned by the rules engine;
  `manual` rows were added by the accountant and the engine never touches them.
- `last_seen_version` — the derivation run that most recently produced this row.
  If the current version has moved past it, the system no longer expects this
  item, and we can show that without deleting anything.

The human's side (none of these are ever written by re-derivation):

- `waived` — the accountant marked this "not needed". It stops counting as
  outstanding but stays visible.
- `waived_reason`
- `removed` — the accountant said this entry was wrong. Hidden from the working
  list but not physically deleted, so we keep an audit trail and so a later
  re-derivation doesn't silently resurrect it.

Why keep removed/waived rows at all instead of deleting? Because the brief's
scenario is precisely a human and a machine disagreeing over time, and you want
a record of who decided what. Soft flags give you that. Hard deletes throw away
the story.

**How the human and the system resolve conflicts:** the human wins. If the
accountant removed an item and the system re-derives it, the row stays removed —
we do not un-remove it. The system's re-derivation only *adds* genuinely new
slots and *refreshes* the `last_seen_version` of ones that still exist. It never
flips a human flag. That is the safe direction to be wrong in: worst case the
accountant sees an item they have to re-add, which is annoying; the opposite
(the machine overruling a human) is the thing the brief is warning against.

### `documents` — the files that actually arrive

One row per uploaded file. It has three groups of fields.

The file itself: `original_filename`, `stored_path`, `uploaded_at`.

The classifier's guess (what the reading tool thinks):

- `guessed_kind`, `guessed_tax_year`, `guessed_person_name`
- `confidence` — 0 to 1
- `readable` — false if the scan couldn't be read at all

The human's verdict and the outcome:

- `status` — `needs_review`, `accepted`, or `rejected`
- `review_reason` — why it landed in the review pile (`low_confidence`,
  `unreadable`, `wrong_year`, `unknown_person`, `no_matching_slot`), so the
  accountant knows at a glance what is wrong with it
- `matched_requirement_id` — which expected slot this file fills, once accepted
- the corrected fields the human can set when they fix a bad guess:
  `human_kind`, `human_tax_year`, `human_person_id`

Same idea as requirements: the classifier's guess and the human's verdict are
different columns, so a human correcting a guess never erases what the tool
originally thought. You can always see "the tool said 2024, the accountant
changed it to 2025."

### `derivation_runs`

A small log: one row each time we derive, with the version number, a timestamp,
and a short note ("initial", "job change disclosed"). Not strictly required to
make the screen work, but the brief makes a point of the list being derived more
than once, and having the runs on record makes that visible and testable. It is
cheap and it tells the story.

## The document lifecycle, spelled out

This is the rule set for what happens to a file from arrival to resolution. It is
the second real piece of logic after derivation, and it is where confidence and
the junk cases get handled.

When a file arrives, the classifier produces a guess. Then:

1. **Can't be read** (`readable = false`) → `needs_review`, reason
   `unreadable`. We can't act on what we can't read.
2. **Low confidence** (below a threshold, I use 0.70) → `needs_review`, reason
   `low_confidence`. This is the brief's "a low-confidence guess should not be
   acted on without human review", made literal.
3. **Confident, but the guess is junk for this client:**
   - guessed year is wrong for that kind of document → `needs_review`, reason
     `wrong_year`
   - guessed person isn't on this return → `needs_review`, reason
     `unknown_person`
   - guess is fine but there is no open slot it fits → `needs_review`, reason
     `no_matching_slot` (e.g. a third W-2 for Ana when we only expect two)
4. **Confident and it cleanly fits an open expected slot** → `accepted` and
   linked to that slot. This is the only path that happens without a human, and
   only the cleanest cases take it.

The threshold at 0.70 is a judgement call. Set it too low and the tool's bad
guesses get filed automatically, which is the failure the brief warns about. Set
it too high and the accountant reviews everything and the automation is pointless.
0.70 is a starting point; in a real deployment you would tune it against how
often the tool is actually wrong. It lives in one constant so it is easy to move.

When the accountant reviews a `needs_review` document they can:

- **accept** the guess as-is and match it to a slot,
- **correct** the guess (fix kind / year / person) and then match, or
- **reject** it as junk (wrong client, duplicate, truly unreadable).

A requirement counts as **received** when it has at least one `accepted` document
linked to it. Everything expected, not waived, not removed, and not yet received
is **outstanding**. Everything sitting in `needs_review`, plus any system-vs-human
oddities, is **needs attention**.

## The decisions I made where the brief left it open

The brief says to decide for myself and write it down. Here is the list.

- **"Needed by everyone" = every adult filer, not every person.** The household
  1040 is one document for the household; government IDs are per adult
  (taxpayer + spouse). A dependent child needs neither an ID nor a W-2. If a
  child actually had a job you would add a manual W-2 requirement, which the
  system supports.
- **The prior-year 1040 is for the year before the engagement.** Filing 2025 →
  we want the 2024 return. This is what makes year-checking meaningful.
- **Government IDs have no tax year.** They don't expire per tax year, so
  `doc_tax_year` is null and the year check is skipped for them.
- **W-2 count equals the number of employers in the tax year.** This collapses
  both worked examples ("two jobs again", "one job plus a mid-year change") into
  one rule.
- **Confidence threshold is 0.70**, in one constant.
- **The human always wins over the system** in a conflict, and nothing is ever
  hard-deleted by re-derivation.
- **The classifier is stubbed** behind an interface. It reads the filename (as a
  client would name the file) for kind/year/person and peeks at the PDF to decide
  whether it is readable and to nudge confidence. A real OCR/ML tool implements
  the same interface. See the architecture doc.
