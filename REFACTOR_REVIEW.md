# ssPrayerTime Refactor — Design Review

*Printed for review. Each feature below states what it does and the design
decisions currently baked into it. Mark anything that no longer matches your
thinking — corrections to this document set the direction for the build.*

*Status as of June 12, 2026: vision agreed, inbox access proven, nothing
built yet. Phase 1 (capture skill) is next.*

---

## What the refactor is, in one paragraph

Replace the end-of-month batch — drop emails in a folder, let the tool guess
who sent what and which section it belongs to — with **continuous capture and
human curation**. Requests get identified and filed *as they arrive*, one at
a time, with you confirming each one. By assembly day the month's requests
are already clean, sorted, and approved, so building the sheet becomes
trivial. The brittle guessing code (substring sender matching, fuzzy section
matching — the source of the June misfiles) is retired entirely.

## The three goals everything answers to

1. **The content.** The congregation can pray *specifically and currently*
   for the seven ministries. Requests must be current, concise, accurate,
   and trustworthy — you review every word; the tool never auto-publishes.
2. **The people.** The process grows the Mission Team through meaningful
   participation. The encourager–missionary relationship is itself ministry.
   Reduce friction *for* the team, never engineer them out.
3. **The division of labor.** Full automation isn't realistic. The tool
   automates what it can and acts as **process-keeper** for the rest —
   tracking what's in, what's outstanding, and nudging you when something
   slips. Mechanical tracking moves off your plate; judgment, review, and
   relationships stay yours.

---

## The monthly cycle as the new system runs it

**Back half of the month (continuous):** Around the last Saturday, Skill 2
drafts a personal, ministry-tagged reminder email to each encourager; you
review and send. Replies and the org emails you receive directly (LSI
alerts, WILD updates, forwarded newsletters) all land in the Gmail inbox.
Skill 1 scans the inbox daily, distills each new request to three sentences
or fewer, and holds it in a pending queue. When you sit down to review — on
your own schedule, at least weekly — you keep, drop, or edit each item;
keepers go into the JSON store tagged for the target month.

**Assembly day (day before the first Sunday):** A small app harvests the
month's selected requests from the JSON and writes the dated `.md` using the
existing template and macros. You review and tweak, render with RapumaMD,
and have the PDF.

**Close-out:** Claude drafts the email to the church office (sheet attached,
Mission Team CC'd so they see the finished product of their work); you send
it. Archive zips the month and the cycle resets.

---

## Feature 1 — Skill 1: Capture (build first)

**What it does:** Scans the inbox **daily** for prayer-sheet traffic —
reminder-thread replies, known team senders, forwarded org mail. Distills
each request to ≤3 sentences and **holds it in a pending queue**. Review is
a separate, unscheduled act: when you sit down (at least once a week), the
skill presents everything accumulated since last time and you keep/drop/edit
each item. Keepers are written to the JSON store with their ministry,
sender, date, and target month. Tracks which messages it has already
processed so nothing is presented twice.

**Decisions baked in:**
- **Capture and review are decoupled** (decided 2026-06-12): capture runs
  daily and accumulates; review happens on your schedule, unscheduled but at
  least weekly. Nothing reaches the JSON store as `selected` without you.
- Every source goes through the *same* review funnel — a team reply and a
  forwarded WILD newsletter get identical treatment.
- Distillation happens at capture time, not assembly time. You're approving
  near-final prayer-sheet text, not raw newsletter excerpts.
- The review is conversational (in the Claude session), not a separate GUI.
- Attachments (Kathy's monthly OCC `.docx`, Life Source) can't be read
  through the Gmail connection yet. Version 1 *detects* the attachment and
  nudges you to drop the file in manually; a local fetch script is the
  planned fast-follow.
- A request arriving after assembly gets tagged for the *next* month, not
  lost.

**Question for you:** When you edit a distillation, should the skill
remember your phrasing style and adapt, or stay neutral and let you edit
each time?

## Feature 2 — Skill 2: Outbound reminders

**What it does:** Drafts one reminder email *per encourager*, addressed
personally and tagged for their ministry, instead of today's single email to
the whole team. Drafts land in your Gmail drafts folder; you review and send.

**Decisions baked in:**
- Per-person, not broadcast, but **somewhat generic in content** (decided
  2026-06-12): the draft is addressed to the encourager and tagged for their
  ministry, without deep personalization. Anything personal (last month's
  contribution, personal details) is yours to add by hand before sending.
- The ministry-tagged subject line makes the reply trivially identifiable —
  serving accuracy *and* honoring the sender's effort (their submission
  can't be misfiled).
- "Claude drafts, Dennis sends" — confirmed as a hard boundary, not just a
  technical limitation. Mail to real people goes out under your hand.
- This replaces the calendar-invite auto-reminder experiment from April
  (which confused Sarah with meeting invitations).

**Question for you:** The current encourager→ministry map: Katie→Fort
Wilderness, Dave→Living Stones, Kathy→OCC, Roy→Dewings/Midwest Indian
Mission, Sarah→?, and you cover Schermers/ROCK, WILD, and Life Source
directly. Is that current and complete?

## Feature 3 — The JSON store

**What it does:** The single source of truth between capture and assembly.
One record per approved request: ministry key, the ≤3-sentence summary,
source/sender, date received, target month, and status
(`pending` → `selected` → `used` → `archived`).

**Decisions baked in:**
- Plain JSON file(s) on disk — no database, greppable, easy to inspect and
  hand-edit.
- The status lifecycle is what makes the system process-aware: at any moment
  it can answer "which ministries have requests for July, and which are
  still empty?"

**Question for you:** Should unused-but-still-valid requests carry over as
candidates for next month (marked as held over), or expire by default?

## Feature 4 — Assembly app

**What it does:** Day before the first Sunday, harvests the target month's
selected requests and writes the dated `.md` using the existing template,
macros, and RapumaMD render path. You review the `.md`, tweak, render to PDF.

**Decisions baked in:**
- The three structural molds drive the layout, not seven bespoke sections:
  **(A)** person/couple with a few prayer points (Dr. Pat, Schermers;
  Dewings plus a *compressed* nod to sub-ministries — never one bullet per
  sub-ministry), **(B)** org with named missionaries, one sub-point per
  person (Fort Wilderness), **(C)** org prayed for as a body (OCC, WILD,
  Life Source).
- Template, macros, and render path survive as-is; the flexible
  `@prayer()` slot behavior already supports requests-as-bullets.
- The Giles entry stays out of the template; occasional entries get re-added
  by hand when they're active.
- The known QR layout wart (wrapfig right-margin overflow) gets its proper
  fix here — QR placed so text never wraps around it, keeping sections
  breakable.

**Question for you:** Does the `mtps` GUI evolve into this assembly
front-end, or does assembly become a skill/command too and the GUI retires?

## Feature 5 — Process-keeper behaviors

**What it does:** Tracks the monthly arc (reminders sent → submissions
arriving → assembly → render → sent → archived) and which of the seven
ministries are accounted for. Nudges when something is slipping: "no Dewings
input yet — chase Roy?" Nudges are deadline-tied and helpful in tone — a
checklist keeping the month on track, not a nag.

**Decisions baked in:**
- A nudge prompts you to follow up *with a person* — it never bypasses the
  encourager to go straight to the missionary or a newsletter.
- A missing ministry is surfaced *before* the sheet ships, not discovered in
  the printed copy.

**Question for you:** Where do nudges reach you? Inside the Claude session
when you happen to open it is the easy version; anything more (email to
yourself, scheduled run that pings) depends on the scheduling seam, which is
still unproven.

## Feature 6 — Close-out

**What it does:** After render, Claude drafts the office email (done, PDF
attached, MT CC'd); you attach the PDF and send. Archive zips the month into
the permanent record, same as today.

**Decision baked in:** CC'ing the team on the finished sheet is deliberate —
it closes the involvement loop; contributors see their input reached the
congregation.

---

## What stays and what goes

**Stays:** the template, `macros.py`, the RapumaMD render path, the archive
step, the two-folder model, the wordlist.

**Goes (Phase 5, once capture is proven):** `lib/convert.py` substring
sender identification, `lib/prepare.py` fuzzy section matching, the
end-of-month `input/` folder batch, and the per-section Opus distillation
call at assembly time (distillation moves to capture).

**Build order:** Skill 1 + JSON store first (~3 sessions, targeting live
capture before the June 27 reminder), then Skill 2, then assembly, then
close-out, then retire the old front half.

---

*Notes / corrections:*
