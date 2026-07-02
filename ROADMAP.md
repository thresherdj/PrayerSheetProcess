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

1. **Inbox read access — ✅ PROVEN (tested live 2026-06-12).** The Gmail MCP in
   Claude Code is connected to the right account (`dd86.coin@gmail.com`).
   Validated against real June traffic:
   - `search_threads` full Gmail query syntax works. **Quirk:** `label:`
     queries need the label *name* (`label:pgcc-missions`), not the ID — ID
     queries silently return empty, despite what the tool doc says.
   - `get_thread` (FULL_CONTENT) returns complete plaintext bodies — all June
     reminder replies (Katie/FW, TenPas/LSI, Schermer/Rock) fully readable.
   - Replies thread onto Dennis's own reminder email, so one search on the
     reminder subject retrieves the whole month's submissions.
   - Org mail converges into this inbox via the protonmail forwards.
   - The `PGCC/Missions` label is consistent but broad (budget, reimbursements,
     events) — filter by known team senders + reminder thread, label secondary.
   - **The one gap: attachments.** `get_thread` lists them (filename/mimeType/
     id) but the MCP has *no download tool*. Kathy's OCC submission is a bare
     "Attached!" + `.docx`; Life Source also sends `.docx`. v1 = detect and
     nudge Dennis to drop the file; fast-follow = local Gmail-API/IMAP fetch by
     message id piped through `convertmd`. (rclone's Google grant is Drive-only
     — no help here.)
2. **Email send + PDF attachment.** `create_draft` confirmed available; no send
   tool → lands as "Claude drafts, Dennis sends," which is also the right human
   checkpoint for mail to the team/office.
3. **Two scheduled triggers** — the daily capture run and the "day before the
   first Sunday" assembly (needs first-Sunday date math). Still unproven:
   whether a scheduled run has access to the Gmail connection. Acceptable
   fallback: Dennis invokes `/capture` manually with morning coffee.
4. **Review/select UX** — the one genuinely new surface; design carefully.
   v1 plan: conversational — skill presents distilled candidates, Dennis
   keeps/drops/edits in the chat, keepers written to JSON. **Decided
   2026-06-12: capture and review are decoupled** — capture runs daily and
   accumulates a pending queue; review is unscheduled, on Dennis's own time,
   at least weekly. **Capture scope narrowed 2026-06-26 to inbox-only**
   (`in:inbox newer_than:35d`, one search instead of three): Dennis keeps
   the inbox to the current cycle's live mail and files the rest, so capture
   sees almost no noise and now also catches submissions from senders not in
   known_senders. The deal: a submission filed/archived *before* a capture
   run won't be seen, so leave submissions in the inbox until capture has
   passed over them.
5. **JSON schema** — the contract between capture and assembly: ministry key,
   ≤3-sentence summary, source/sender, date received, target month, status
   (`pending`/`selected`/`used`/`archived`), and a **`display` flag**
   (`public-ok`/`private`, defaulted per ministry — LSI private, others
   public-ok, overridable at review). The flag is inert in v1 but must exist
   from day one for the future hallway-display idea (see Phase 6).
   Unused-but-valid requests **expire by default** (decided 2026-06-12).

---

## Phased plan

### Phase 0 — Get June out by brute force (current tool) — ✅ DONE 2026-06-06
June 2026 shipped on the existing tool after manual cleanup of the misfiled
input. `202606_ssPrayerTime.zip` is in the archive; the sheet went to the
office (CC the MT) on 2026-06-06. Leftover cleanup: an untracked `June/`
work-folder copy sits in this repo, and the configured `work_dir` still holds
superseded June files — both are duplicates of the archive zip, safe to delete.

### Phase 1 — Foundation: JSON store + Skill 1 (capture) — NEXT UP
Seam #1 is proven (see above); estimate ~3 working sessions. Target: capturing
live before the July reminder replies start (~Sat 2026-06-27 reminder; July
sheet assembles 2026-07-04 for first-Sunday 2026-07-05).

- **Session 1 — schema + working skeleton. ✅ DONE 2026-06-12.** Built:
  `ministries.json` (seven ministries: molds, shapes, display defaults,
  encourager map — the data the Phase 6 site will edit), `lib/store.py`
  (schema + CLI: add/list/set/mark-seen/check-seen/expire/status/harvest;
  store lives in `{work_dir}/capture/`; first-Sunday target-month math;
  per-ministry display defaults, unknown→private), and two skills:
  `.claude/skills/ps-capture` and `.claude/skills/ps-review`. Tuned against
  the live June corpus: all 5 real submissions correctly identified, all 14
  non-submissions correctly excluded (the exact failure mode of the old
  pipeline), and the store is seeded with 5 real pending July items (2 WILD,
  3 Stephanie Heise guest entries, private). Voice profile:
  `~/Claude/3_Dennis/Branding/Brand Context/voice-profile.md`.
- **Session 2 — state + edge cases.** Much landed early in Session 1
  (seen-IDs dedup, attachment detect-and-nudge, non-submission skipping,
  next-month tagging are all in the store/skills). **2026-06-26: ran
  `/ps-capture` and `/ps-review` end-to-end live** — queue was empty (July
  reminders had just gone out), but the flow validated: status header +
  empty-queue handling work, and capture correctly classified five inbox
  non-submissions (bulletin-board, elder-board, a study forward) as noise
  and marked them seen, the exact failure mode the old pipeline got wrong.
  Capture also switched to inbox-only this session (see seam #1). Remaining:
  exercise `/ps-review` against *real* pending items once July replies land,
  harden anything that exposes, and decide handling for org mail that only
  reaches protonmail (Dennis must forward it to dd86.coin for capture to see
  it — e.g. LSI Prayer Alerts and Life Source lists were hand-exported .emls
  in June).
- **Session 3 — the trigger (time-boxed).** Try the daily scheduled run
  (seam #3, the only unproven piece). If a scheduled agent can't reach the
  Gmail connection, accept manual `/capture` as v1 without grief.

### Phase 2 — Skill 2 (outbound tagged reminders) — ✅ DONE 2026-06-12
Built `.claude/skills/ps-remind`: one personal, ministry-tagged Gmail draft
per encourager; dry-run-then-create; Claude drafts, Dennis sends. Content is
**somewhat generic** (per-person + ministry tag, no deep personalization;
personal touches are Dennis's to add). Resolved the encourager map:
**Sarah Rose → Life Source** (not officially MT, but on the sheet). Added
`store.py schedule` (target month + assembly day + submission deadline).
**Ran for real 2026-06-26 for the July cycle:** five per-encourager drafts
created (Roy/Dewing, David/Living Stones, Katie/Fort Wilderness,
Kathy/OCC, Sarah/Life Source), subject-tagged with the Fri July 3
submission deadline; Dennis reviewed and sent them. ROCK and WILD are
Dennis-covered, so no drafts there. Subject line evolved from the old
single "Mission Team Prayer Sheet Reminder" to per-ministry tags
("Prayer Sheet — <ministry> …") so replies are self-identifying at capture.

### Phase 3 — Assembly app (JSON → dated .md) — ✅ DONE 2026-06-12
Built `lib/assemble.py` (`run_assemble(code, log, work_dir)`, also a CLI):
harvest the month's SELECTED requests → match each template section to a
ministry → fill `@prayer()` slots → reassemble (footer-aware) → write the
dated `.md`. Read-only on the store, so re-runnable. Slot filling handles
all three molds: flexible `@prayer()` slots (A/C) expand one bullet per
request; labeled slots (B, Fort Wilderness) route by a new optional store
`label` field, with "No new requests this month" for unmatched names.
Section→ministry matching reuses `prepare._normalize`; WILD needed
un-deduped target tokens to clear the threshold (template spells out the
acronym). Wired into the GUI as the new primary **1. Assemble** button;
Convert/Prepare demoted to a "Legacy" row (retire in Phase 5). Verified:
real WILD data + synthetic mold-B data assemble and render to PDF.

### Phase 4 — Close-out email
- Draft office email (done + PDF attached), CC the MT; then archive.

### Phase 5 — Retire the brittle front half
- Remove/replace `lib/convert.py` substring identification and `lib/prepare.py`
  fuzzy matching once capture-and-curate is proven. Keep render + archive.

### Phase 6 — Website on the Pi 5 (deferred 2026-06-12 to keep July on track)
Dennis runs a Pi 5 with another web app already; the prayer-request store and
review surface eventually move there:
- Capture pushes distilled requests to the site; the site notifies Dennis;
  review happens in the browser (the conversational review flow re-skinned as
  a page — same header/status, numbered items become cards with
  keep/drop/edit). Better fit for "unscheduled, at least weekly" review.
- Encourager→ministry map editable in the site UI.
- Internal storage format is the site's choice (SQLite natural); exports to
  JSON when pulled by a skill/app — the assembly contract doesn't change.
- **Private network only** — LAN/Tailscale between Dennis's Pi and a future
  church Pi; no open ports, no public exposure. Prayer requests can be
  sensitive (LSI names people in hiding).
- **Far future:** a church Pi *pulls* current requests over the private link
  and displays them on a hallway screen for congregational awareness — only
  records flagged `display: public-ok`. Pull-only direction (church Pi
  reaches out; nothing pushes to it).

To keep this swap cheap, Phase 1 hides the store behind a small interface and
designs the schema website-ready (display flag, map as data).

---

## Known layout issue — QR float and right-margin overflow

The section macros (`missionary_section` / `title_section`) float the QR
top-right via `wrapfig` so body text flows around it and sections can break
across pages (this is what got the June sheet from 5 → 4 pages). The cost:
`wrapfig` mis-measures the occasional line where bulleted text meets the
float, setting it *wider than the text block* so it pokes into the right
margin. This is **not** fixable by justification settings — confirmed that
`\emergencystretch`, `\sloppy`, and an explicit `wrapfigure[N]` line count all
fail, because the line's target width itself is wrong, not the spacing. For
June 2026 the two offending lines were cleared by lightly tightening the
bullets (also serves "concise").

**Proper fix (assembly/layout work in the refactor, not a quick patch):** lay
sections out so body text never wraps around the QR — e.g. QR in a top band
beside the heading/description with the bullets full-width below, or QR in the
right margin. Either keeps sections breakable (no 5-page whitespace) *and*
removes the overflow. Until then, tightening a bullet is the workaround.

---

## What stays regardless

`template_ssPrayerTime.md`, `macros.py` (the floated-QR breakable section
macros and the labeled-vs-unlabeled `@prayer()` behavior), the RapumaMD render
path, and the archive step all survive the redesign and feed the
assembly/close-out stages. The `mtps` GUI may evolve into the assembly/review
front-end rather than disappear.
