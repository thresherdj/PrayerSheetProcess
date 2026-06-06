# ssPrayerTime — Roadmap

This roadmap supersedes the original modular-refactor spec. It captures the
**goals**, the **target architecture** (a continuous capture-and-curate
redesign agreed June 2026), and a **phased plan** to get there — starting with
getting *this* month's sheet out by brute force on the current tool.

Companion docs: `CLAUDE.md` (architecture/how-to) and the project memory under
`~/.claude/projects/.../memory/` (the goal notes + `refactor-vision`).

---

## The three goals (everything answers to these)

1. **North star — the content.** Enable the PGCC congregation to pray
   *specifically and currently* for the seven supported ministries. Success =
   requests that are **current, concise, accurate, and trustworthy** (Dennis
   reviews every word; the tool never auto-publishes). Everything else is
   scaffolding.
2. **Involvement — the people.** Grow the Mission Team through *meaningful*
   participation and grow missions awareness in the congregation. The humans
   are a **feature, not an inefficiency** — reduce friction *for* the team,
   never engineer them out. The encourager↔missionary relationship is itself
   ministry.
3. **Operating principle — the division of labor.** Full automation isn't
   realistic; the process will always need Dennis's judgment, review, and
   relationship work. So the tool **automates what it can** and, for the rest,
   acts as a **process-keeper**: track state across the monthly cycle and
   **nudge** when something's missing or slipping. Be process-aware, not a row
   of stateless buttons.

The honest tension: efficiency can pull against involvement. A change that
eases the software but sidelines a team member is a *net loss*. Good designs
serve all three.

---

## Where we are today

The current tool works end-to-end but its **front half is brittle**:

- `mtps` GUI, `template_ssPrayerTime.md`, `macros.py`, RapumaMD render, and
  archive are solid and stay.
- **The fragile part:** `lib/convert.py` identifies senders by *substring*
  match against `known_senders.json` (e.g. the key `"don"` matched inside
  `"don't"`), and `lib/prepare.py` then *fuzzy-matches* filenames to template
  sections. In the June run this misfiled a Fort Wilderness email into the
  Dewings section and scattered several "Re: reminder" replies into the wrong
  ministries. This whole identify/match approach is what the redesign replaces.

---

## Target architecture (the redesign)

Shift from end-of-month batch guessing to **continuous capture with human
curation**, so identification happens *at capture, with Dennis in the loop* —
one request at a time — instead of blindly after the fact.

```
Back half of month (continuous):
  Skill 2 (outbound) ── drafts personal, ministry-tagged reminder emails to
                        each encourager  (the involvement engine)
        │
        ▼
  team replies  +  org emails Dennis receives directly (LSI alerts, WILD…)
        │   all land in the inbox
        ▼
  Skill 1 (capture) ── scans inbox ~daily → distills each request to ≤3
                       sentences → nudges Dennis → he REVIEWS & SELECTS →
                       keepers go to a JSON store, tagged for the target month

Day before the first Sunday (assembly):
  small app ── harvest the month's selected requests from JSON → write the
               dated .md → Dennis reviews/tweaks → render with RapumaMD → PDF

Close-out:
  Claude drafts the office email (done + PDF attached), CC the MT  ← closes
  the involvement loop (team sees the finished sheet) → archive
```

Why it's the right shape: the brittle front half **disappears** — by assembly
time the JSON is already clean and sorted, so the build is trivial; every human
checkpoint (select, review the `.md`, render, send) is where judgment adds
value.

### Seams to validate (by risk)

1. **Inbox read access — the keystone, prove first.** Which account
   (submissions appear to land at a Gmail, `dd86.coin@gmail.com`) and how a
   skill reaches it. Gmail tools incl. draft creation are available in the
   Claude environment, but the account must be connected. Fallback: local IMAP.
2. **Email send + PDF attachment.** Drafting is likely; autonomous *send* and
   *attach* are uncertain → probably lands as "Claude drafts, Dennis sends,"
   which is also the right human checkpoint for mail to the team/office.
3. **Two scheduled triggers** — the daily capture run and the "day before the
   first Sunday" assembly (needs first-Sunday date math).
4. **Review/select UX** — the one genuinely new surface; design carefully.
5. **JSON schema** — the contract between capture and assembly: ministry key,
   ≤3-sentence summary, source/sender, date received, target month, status
   (`pending`/`selected`/`used`/`archived`).

---

## Phased plan

### Phase 0 — Get June out by brute force (current tool) — NEXT SESSION
The new system isn't built, so this month uses the existing tool with manual
cleanup of the misfiled input:
- In the work folder's `input/`, **re-sort the misfiled files** to the correct
  ministry (read each one's `From:`/content, ignore the bad labels). Known bad:
  the FW/Kusilek email mislabeled `MidwestIndianMission_DewingDon`; several
  "Re: reminder" replies mislabeled `LivingStonesInternational`; one in
  `RockInternational`.
- **Remove non-submissions** (the bare "Mission Team Prayer Sheet Reminder" /
  "Updates Welcome" emails with no requests) and the dropped **Giles** file.
- Confirm each of the seven has its real material (or is knowingly empty —
  e.g. Roy/Dewings may not have submitted).
- Re-run **Prepare → review → render → archive** (API credits now active).

### Phase 1 — Foundation: JSON store + Skill 1 (capture)
- Prove inbox access (seam #1) before anything else.
- Define the JSON schema (seam #5).
- Build Skill 1: scan → summarize (≤3 sentences) → review/select → write JSON.
- Wrap it in a daily schedule that nudges when there's a batch to review.

### Phase 2 — Skill 2 (outbound tagged reminders)
- Draft per-encourager, ministry-tagged emails (see MT→ministry map in the
  `ministry-structure` memory). Land on "draft, Dennis sends."
- Optionally make the email a relational touchpoint (acknowledge last month's
  contribution → reinforces ownership).

### Phase 3 — Assembly app (JSON → dated .md)
- Harvest the target month's selected requests → dated `.md` using the existing
  template + macros. Each ministry's requests become the `@prayer()` bullets
  (the flexible unlabeled-slot behavior already supports this).

### Phase 4 — Close-out email
- Draft office email (done + PDF attached), CC the MT; then archive.

### Phase 5 — Retire the brittle front half
- Remove/replace `lib/convert.py` substring identification and `lib/prepare.py`
  fuzzy matching once capture-and-curate is proven. Keep render + archive.

---

## What stays regardless

`template_ssPrayerTime.md`, `macros.py` (incl. the two-column section macros
and the labeled-vs-unlabeled `@prayer()` behavior), the RapumaMD render path,
and the archive step all survive the redesign and feed the assembly/close-out
stages. The `mtps` GUI may evolve into the assembly/review front-end rather
than disappear.
