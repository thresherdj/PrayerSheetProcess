---
name: ps-remind
description: Draft the monthly prayer-sheet reminder emails — one personal, ministry-tagged email per encourager — as Gmail drafts for Dennis to review and send. Use when Dennis says "draft the reminders", "send the monthly reminder", or "time to ask the team for submissions". Claude drafts; Dennis sends — never send autonomously.
---

# Prayer Sheet Reminders (Skill 2)

The involvement engine. Instead of one broadcast email to the whole team,
draft a separate, personally-addressed, ministry-tagged reminder to each
encourager. The tag makes their reply trivially identifiable at capture
time, and the personal address honors that this is *their* missionary.

**Hard rule: Claude drafts, Dennis sends.** Create Gmail *drafts* only.
Never send. The human send is the right checkpoint for mail to real people.

## Paths

- Store CLI: `python3 /home/dennis/MakerSpace/CodingProjects/MissionaryPrayerSheet/Production/lib/store.py`
- Ministry + encourager data: `<app_dir>/ministries.json`
- Voice profile: `/home/dennis/Claude/3_Dennis/Branding/Brand Context/voice-profile.md`

## Procedure

**1. Load context.** Read `ministries.json` and the voice profile. Get the
month's dates: `store.py schedule` → target month + `submission_deadline`
(the Friday) and `assembly_day`.

**2. Build the recipient list.** One draft per ministry whose `encourager`
is a *team member* (not Dennis himself). Group by encourager: if one person
encourages two ministries, that's still one email naming both. Skip
ministries Dennis covers directly (encourager email in
`self_addresses`) — he doesn't remind himself; he handles ROCK, WILD, and
Life Source on his own.

A team member on the roster with **no** ministry assignment gets **no**
draft — flag them in the report so Dennis can assign or confirm they're
inactive.

**3. Default content — somewhat generic (decided 2026-06-12).** Per-person
address and a ministry tag, but no deep personalization. Anything personal
(acknowledging last month's contribution, a personal note) is Dennis's to
add by hand before sending. Each draft:

- **To:** the encourager's email.
- **Subject:** ministry-tagged so the reply is self-identifying, e.g.
  `Prayer Sheet — Fort Wilderness (submissions due Fri July 3)`.
- **Body:** in Dennis's voice (see profile — first-name salutation, purpose
  in the first sentence, warm but direct, no corporate filler, brief close
  like "In His service, Dennis"). State that it's time to gather this
  month's requests for *their* ministry, give the Friday deadline, and
  thank them. Keep it short. No bullet lists in the body — Dennis doesn't
  use them in personal mail.

**4. Dry run first, every time.** Before creating any Gmail draft, show
Dennis the full text of each draft (To / Subject / Body) in the
conversation and let him approve, tweak, or veto. This is cheap and keeps
his drafts folder clean. Only after he says go, proceed.

**5. Create the drafts.** For each approved draft, call the Gmail
`create_draft` tool with `to`, `subject`, `body` (plain text). Do **not**
set a send path. Report each draft id.

**6. Report.** List who got a draft (and for which ministry), note any
unassigned team members skipped, and remind Dennis the drafts are in his
Gmail awaiting his review and send. Optionally note that once he sends, the
back half of the cycle is open — replies will land in the inbox for
`/ps-capture`.

## Notes

- This replaces the April calendar-invite auto-reminder experiment (which
  confused recipients with meeting invitations). No calendar invites.
- Self-covered ministries (ROCK/Schermers, WILD, Life Source): if Dennis
  asks, you can still draft a reminder to the *external* contact (e.g. the
  Schermers at their address) — but that's on request, not the default set.
