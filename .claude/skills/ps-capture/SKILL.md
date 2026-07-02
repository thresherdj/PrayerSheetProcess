---
name: ps-capture
description: Scan the Gmail inbox for new prayer-sheet submissions, distill each request to ≤3 sentences in Dennis's voice, and hold them in the capture store as pending. Use when Dennis says "run capture", "check for new prayer requests", or a scheduled capture run fires. Capture never selects — review (/ps-review) is a separate human act.
---

# Prayer Sheet Capture (Skill 1)

Scan → distill → hold for review. Nothing you capture is final: every record
lands as `pending` and waits for Dennis in `/ps-review`.

## Paths

- App dir: `/home/dennis/MakerSpace/CodingProjects/MissionaryPrayerSheet/Production`
- Store CLI: `python3 <app_dir>/lib/store.py` (subcommands: add, list, set,
  mark-seen, check-seen, expire, status, harvest)
- Ministry data: `<app_dir>/ministries.json` — keys, molds, shapes,
  encourager map, sender addresses
- Voice profile: `/home/dennis/Claude/3_Dennis/Branding/Brand Context/voice-profile.md`
  (path contains a space — quote it)

## Procedure

**1. Load context.** Read `ministries.json` and the voice profile.

**2. Find candidate mail.** Scan the **inbox only** — Dennis keeps the inbox
to the current cycle's live mail and files everything else, so a single
search catches every submission with almost no noise (decided 2026-06-26):

- `in:inbox newer_than:35d`

Collect unique messages with their message id, sender, date, subject.
**Skip messages Dennis himself sent** (sender in `self_addresses`, or
labelIds containing SENT) — his forwards arrive from the
`forward_addresses` instead and ARE candidates. Because the scan is
inbox-only, a submission archived or filed *before* a capture run won't be
seen — that's the deal: leave submissions in the inbox until capture has
passed over them.

**3. Dedup.** `store.py check-seen <id> <id> ...` prints only the ids not
yet processed. If nothing is new, report that and stop.

**4. Fetch and classify each new message** (`get_thread`, FULL_CONTENT —
fetch each thread once even if several of its messages are new):

- **Submission with request content in the body** → distill (step 5).
- **Attachment submission** (trivial body like "Attached!", plus a
  .docx/.pdf attachment) → the MCP cannot download attachments. Add one
  record with `--summary "[attachment: <filename>]"` and
  `--note "attachment — ask Dennis to supply the file"`.
- **Non-submission** (thank-yous, scheduling chatter, calendar acceptances,
  PGCC business unrelated to prayer requests) → no record; still mark seen.
- **Ministry unclear** → still capture, with `--ministry unknown`; review
  reassigns. Never guess between two plausible ministries — `unknown` is
  the honest answer and costs Dennis one word at review.

**5. Distill.** Per distinct request found, write ≤3 sentences (usually
1–2) in Dennis's voice, following the ministry's `shape` from
`ministries.json` (mold A: couple/person focus, compress sub-ministries;
mold B: one entry per named person; mold C: org as a body). Rules:

- Stay strictly inside what the source says — never embellish, never add
  detail, never resolve ambiguity by inventing. Accuracy beats polish.
- Keep names and pseudonyms exactly as written (LSI uses protective
  pseudonyms deliberately).
- One store record per distinct request, at most 4 per ministry per email.
- Sensitive content (persecution, legal trouble, people in hiding, medical
  detail) → pass `--display private` even if the ministry default is
  public-ok. When in doubt, private.

**6. Store.** For each request:

```
store.py add --ministry <key> --summary "<text>" \
  --sender <email> --sender-name "<name>" --subject "<subject>" \
  --message-id <gmail id> --received <YYYY-MM-DD> [--display private] [--note "..."]
```

Let the store compute `target_month` (it knows the first-Sunday/assembly
rule). Override with `--target-month` only if the sender explicitly says
the request is for a different month.

**7. Mark seen.** `store.py mark-seen <every id processed this run>` —
including non-submissions, so they are never re-triaged.

**8. Report.** End with: how many new requests captured, by ministry;
attachment nudges and unknowns flagged; then `store.py status` output so
Dennis sees what the target month still lacks. Remind him pending items
wait in `/ps-review`.
