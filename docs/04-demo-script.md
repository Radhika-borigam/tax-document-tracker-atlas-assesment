# Demo script (for the video)

A 3–5 minute walkthrough. The goal is to show the screen doing its job and to
talk through the cases I judged worth handling. Roughly what I say and click.

## 0. Setup (before recording)

- Backend running on :8000, frontend on :5173.
- The app is freshly seeded, so Rivera is in its **January** state: 6 items
  outstanding, nothing received, nothing to review.
- Have `sample_documents/rivera/` open in a file picker.

## 1. The problem, in ten seconds (~30s)

"This is the document-collection screen for one client, the Rivera household,
filing jointly for 2025. Three columns: what's still outstanding, what we've
received, and what needs my attention. Right now everything is outstanding
because no documents have arrived."

Point at the outstanding list and read it:
- prior-year 1040 for **2024** (last year's return),
- a government ID for Ana and one for Luis (not Mateo, the child),
- two W-2s for Ana (she had two jobs), one for Luis.

"Nobody typed this list in. It was **derived** from what we know about the
family's jobs — that panel on the right shows the facts it came from."

## 2. Documents arrive — the happy path (~45s)

Upload `Ana Rivera W-2 2025 Acme Corp.pdf`.

"A file arrives. The tool reads it, it's confident it's Ana's 2025 W-2, and it
matches an open slot — so it files itself and moves to Received. No human needed
for the clean, confident case."

Upload `Rivera 1040 2024.pdf` and `Ana Rivera drivers license.pdf` the same way.
"Same story — confident, they fit, they're filed."

## 3. The messy documents — the review pile (~90s)

This is the heart of it. Upload the awkward files one at a time and narrate each.

- `Ana Rivera W-2 2024 Acme Corp.pdf` → **Wrong tax year.** "The tool is sure
  this is a W-2, but it's for 2024 and we're filing 2025. It doesn't get filed —
  it goes to review, flagged wrong year."
- `Carla Cousin W-2 2025 Soylent.pdf` → **Person not on this return.** "Confident
  W-2, but Carla isn't part of this household. Flagged, not filed."
- `scan_unreadable.pdf` → **Couldn't read the scan.** "This one has no readable
  text at all. You can't act on what you can't read, so it waits for a human."
- `IMG_20250412.pdf` → **Low confidence.** "Badly named, few signals. The tool
  isn't sure enough, so — exactly as the brief asks — it doesn't act on the
  guess. It asks me."

Then **review one**. On the wrong-year card, open "Correct & accept", change the
year to 2025, save. "I looked, I corrected the tool's guess, and now it matches
Ana's open slot. Notice the tool's original guess is kept — we don't erase what
it thought." Reject the Carla one: "Not our client — reject."

## 4. The late disclosure — re-derivation (~75s)

This is the part the brief cares about most.

"It's March. Two months in. I've been working this list — say I marked one of
Ana's W-2s as not needed." (Mark it not needed with a reason.)

"Now the client finally mentions Luis changed jobs back in June. So he actually
has **two** employers this year, not one. Watch what happens when we re-derive."

In the facts panel, pick Luis, set employers to 2, add the note, hit Re-derive.

"Two things to notice. One: a **new** slot appeared — Luis's second W-2. Two:
everything else is exactly as I left it. The item I marked not needed is still
marked not needed. The re-derivation added what changed and touched nothing I'd
decided. The derivation history at the bottom shows it: version 2, one added, the
rest refreshed in place."

"If it had just rebuilt the list from scratch, it would have blown away two
months of my work. That's the whole point of keeping the system's opinion and my
decisions in separate places."

## 5. Wrap (~20s)

"So: the list is derived and safely re-derived, confident documents file
themselves, and everything the tool is unsure about — or that's plain wrong —
lands in front of me instead of quietly slipping into the file. The reasoning
behind all of it is in the docs folder. Thanks."
