# Understanding the problem

Before writing any code I wanted to be sure I actually understood what this
screen is for and where the hard parts are. This document is me thinking it
through. It is long on purpose. The brief said the reasoning matters more than
the amount of code, and I agree with that, because most of the mistakes you can
make here are mistakes of understanding, not of typing.

## What is really being asked

On the surface it looks simple. A tax accountant needs some documents from a
client, and we build a screen that shows which ones have turned up and which
ones are still missing. If that were the whole story you could build it in an
afternoon with a checklist table.

But it is not the whole story. When I read the brief slowly, three separate hard
problems fall out of it, and they are the actual assignment. The checklist is
just the thing you see at the end.

### Hard problem 1: the list is not fixed, it is worked out

Nobody types in "this client needs seven documents." The system has to *derive*
the list from facts about the client. The facts are things like: last year Ana
had two jobs, Luis had one job, this year Luis changed jobs in June. From those
facts you work out that you expect two W-2s from Ana, two from Luis, one
prior-year 1040 for the household, and a government ID for each adult.

So the first real piece of work is a small rules engine. Not a big one, but a
real one. Given the household and what we know about their employment, produce
the set of documents we expect.

### Hard problem 2: the list is worked out more than once, and the second time it must not stomp on the accountant

This is the part the brief spends the most words on, so I think it is the part
they most want to see handled well.

The story is: in January the system derives the list. Then for two months the
accountant lives inside that list. They tick things off, they mark some items as
not needed, they delete an entry that was plainly wrong, they add an item the
system never thought of. Then in March a fact changes. Luis, it turns out,
changed jobs back in June and nobody mentioned it. Now we have to derive the
list *again* so that the second W-2 for Luis appears.

The naive way to re-derive is to throw the old list away and build a fresh one.
That is a disaster here, because it wipes out two months of the accountant's
decisions. The "not needed" flags are gone, the manual additions are gone, the
deletions come back from the dead. So re-derivation cannot be "delete and
rebuild." It has to be a *merge*: bring in what genuinely changed, and leave the
human's decisions alone.

This one line in the brief is the whole reason the data model looks the way it
does. I keep the system's opinion and the human's decisions in separate places,
so that re-running the system can never overwrite a human decision. More on that
in the data model doc, but this is where the idea comes from.

To make that merge possible I need every expected item to have a *stable
identity* that survives re-derivation. "Luis's second W-2 for 2025" has to be
recognisably the same slot in March as it was in January, otherwise I can't tell
the difference between "this is the item that changed" and "this is a brand new
item." Getting that identity right is most of the battle.

### Hard problem 3: the documents that arrive are messy and half of them lie to you

Documents show up over about six weeks, in no order, from different people in the
family. A W-2 arriving for Ana tells you nothing about whether Luis's has
arrived. So matching an incoming file to the right expected slot is its own job.

On top of that, a software tool reads each file and *guesses* what it is: the
kind of document, the tax year, whose it is, and how sure it is. The brief is
blunt that this tool is sometimes badly wrong, and that a low-confidence guess
must not be acted on without a human looking at it. So confidence is not
decoration. It decides whether a document can be filed automatically or has to
go into a review pile.

And then the genuinely junk cases, which the brief explicitly asks me to handle:

- a document for the wrong year (a 2024 W-2 when we want 2025),
- a document for a person nobody asked about (a W-2 for some cousin who is not on
  this return),
- a scan that cannot be read at all.

None of these should quietly slot into the checklist. Each needs to be caught
and shown to the accountant as "look at this," not counted as a received
document.

## So what is the screen actually showing

Once I frame it that way, the screen has three jobs, and they line up exactly
with the three sentences at the end of the brief:

1. **Outstanding** — what we still expect and have not received. This is the
   accountant's to-do list for chasing the client.
2. **Received** — what has turned up and been confirmed against an expected slot.
3. **Needs attention** — everything the system is not confident enough to act on
   by itself: low-confidence guesses, unreadable scans, wrong-year forms,
   documents for unknown people, and anything where the system's opinion and the
   accountant's decision disagree.

The third pile is the interesting one and, I think, the one that shows whether
you understood the brief. It is easy to build one and two. Pile three is where
the "usually right and occasionally badly wrong" tool gets handled like an adult.

## The example, worked out by hand

The brief gives the Rivera household. I worked out the expected list by hand
first, because if my code produces a different list than my own head does, one of
us is wrong and I want to know which.

Rivera household, filing jointly, tax year 2025.
People: Ana (taxpayer), Luis (spouse), Mateo (child).
Last year: Ana had 2 jobs, Luis had 1 job.
This year: Luis changed jobs in June 2025.

What I expect:

- **One prior-year 1040 for the household.** "Last year's completed return"
  means the return they filed last year, which covers tax year 2024. So this is
  a 1040 for **2024**, not 2025. That detail matters: it means a W-2 is a
  wrong-year document if it says 2024, but the 1040 is a wrong-year document if
  it says 2025. Different documents, different correct year.
- **A government ID for Ana, and one for Luis.** I read "needed by everyone" as
  every adult filer, not literally every person, so Mateo the child does not need
  one. A government ID has no tax year. (This is a judgement call; I record it in
  the decisions doc.)
- **Two W-2s for Ana.** She had two jobs last year and nothing says that
  changed, so I expect two again for 2025.
- **Two W-2s for Luis.** He had one job last year, but he changed jobs in June,
  so during 2025 he was paid by two employers, and each employer issues a W-2.
  One job last year becomes two W-2s this year.
- **Nothing for Mateo.** He is a child with no job, so no W-2, and by my reading
  no ID.

That is **seven expected documents**: 1 + 2 (IDs) + 2 (Ana) + 2 (Luis).

Now the January-to-March twist, which is the scenario I most want to demo:
In January nobody knew about Luis's job change, so the system only expected
**one** W-2 for Luis, and the January list had six items. The accountant worked
that list for two months. In March the job change surfaces, the system
re-derives, and Luis's **second** W-2 slot appears — without disturbing anything
the accountant did to the other six items. That transition from six to seven,
with the human's edits intact, is the single behaviour I would point at if
someone asked me "did you actually get it."

## What I am deliberately not building

I want to be honest up front about scope, because five to six hours is not a lot
and spreading thin would hurt the parts that matter.

- **A real document classifier / OCR.** The brief describes the tool that reads
  files and guesses, but building a real one is a machine-learning project on its
  own. I build a stub that produces the same *shape* of output (kind, year,
  person, confidence, readable-or-not) behind a clean interface, so the rest of
  the system is built against a realistic classifier and a real one could be
  dropped in later. The interesting logic — routing on confidence, catching junk,
  matching to slots — is all downstream of the classifier and is fully real.
- **Auth, multiple accountants, permissions.** Out of scope for a single screen.
- **A polished visual design.** I aim for clear and usable, not pretty.

The next docs cover the data model and the decisions, then the architecture, and
then I build it.
