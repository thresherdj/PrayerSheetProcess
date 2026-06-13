---
name: ps-review
description: Present pending captured prayer requests for Dennis to keep, drop, or edit; keepers become "selected" in the store. Use when Dennis says "review requests", "let's review the prayer sheet items", or after a capture run when he wants to triage. This is the human checkpoint — nothing reaches the sheet without it.
---

# Prayer Sheet Review

Dennis's curation pass over what capture collected. Conversational, fast,
and entirely his call — typical session is five minutes.

## Paths

- Store CLI: `python3 /home/dennis/MakerSpace/CodingProjects/MissionaryPrayerSheet/Production/lib/store.py`
- Ministry data: `ministries.json` in the same app dir

## Procedure

**1. Open the books.**

- `store.py expire` — roll stale items out first
- `store.py status` — the month header
- `store.py list --status pending` — the queue

**2. Present.** Show the status header (target month, assembly day, which
ministries are covered and which are still empty, with encourager names —
that line is the nudge). Then the pending items, grouped by ministry,
**numbered by their store id** so Dennis's replies map unambiguously:

```
12. [Fort Wilderness] Katie Kusilek — Jun 27
    Janet Merkel asks continued prayer for her housing situation; she
    remains on a waiting list while staying with a sibling.

13. [OCC] Kathy Winkler — Jun 29   ⚠ attachment — needs the file from Dennis
    [attachment: OCC Prayer 6.2026.docx]
```

Flag inline: attachment nudges, `unknown` ministry (needs reassignment),
`private` display. Keep the presentation compact — no tables, no prose
padding.

**3. Take verdicts.** Dennis replies naturally, e.g. *"keep 12 and 14,
drop 13, edit 15: change X to Y, 16 is private, 17 goes to wild"*. Apply:

- keep → `store.py set <ids> --status selected`
- drop → `store.py set <ids> --status dropped`
- edit → `store.py set <id> --summary "<his wording>" --status selected`
  (an edit implies a keep unless he says otherwise)
- reassign → `store.py set <id> --ministry <key>` (display default does
  NOT re-derive — ask or set `--display` if the new ministry is
  living_stones)
- show source → `get_thread` with the record's `message_id`, show the
  original email text, then re-ask
- attachment records → if Dennis supplies the file or pastes the content,
  distill it now (voice + shape rules from ps-capture) and update the
  record's summary; otherwise leave pending with its nudge note

Items he doesn't rule on stay pending for next time — say so, don't push.

**4. Recap.** Selected counts by ministry, anything left pending, and the
still-empty ministries with their encouragers ("no Dewings yet — worth a
nudge to Roy?"). One short block, then stop.
