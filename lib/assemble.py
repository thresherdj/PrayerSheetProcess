"""Phase 3: Assemble the dated .md from curated store requests.

Replaces the old convert/prepare guesswork. By assembly time the month's
requests are already distilled (capture) and curated (review), so this is
mechanical: harvest the SELECTED requests, drop them into the template's
@prayer() slots under the right ministry, and write {YYYYMM}_ssPrayerTime.md.
Dennis then tweaks formatting and renders.

Read-only on the store (harvest only) so it is safe to re-run — requests
stay 'selected' until the month is archived.

Slot filling:
- Flexible slot  @prayer() [CONTENT NEEDED]  (molds A/C): expand to one
  @prayer() <text> line per selected request for that ministry.
- Labeled slot   @prayer(Name) [CONTENT NEEDED]  (mold B, Fort Wilderness):
  fill with the request whose `label` matches Name; unmatched names get a
  "No new requests this month" line.
"""

import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lib.prepare import _split_template, _normalize, _token_similarity
else:
    from .prepare import _split_template, _normalize, _token_similarity

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = APP_DIR / "template_ssPrayerTime.md"
MINISTRIES_FILE = APP_DIR / "ministries.json"

NO_NEWS = "No new requests this month — continue to pray for them as they serve."


def _harvest(work_dir, month):
    """Selected requests for the month, grouped by ministry key.

    Reads the store directly from the given work_dir (the GUI's chosen
    folder), independent of the store CLI's config-based path.
    """
    f = Path(work_dir) / "capture" / "requests.json"
    records = json.loads(f.read_text()) if f.exists() else []
    out = {}
    for r in records:
        if r.get("target_month") == month and r.get("status") == "selected":
            out.setdefault(r.get("ministry", "unknown"), []).append(r)
    return out


def _heading_args(heading_line):
    """The descriptive args of a section heading, QR path dropped."""
    m = re.match(r"^@(?:missionary_section|title_section|title)\((.+)\)\s*$",
                 heading_line)
    if not m:
        return heading_line
    args = [a.strip() for a in m.group(1).split(",")]
    args = [a for a in args if "QR_Codes" not in a and not a.lower().endswith(".png")]
    return " ".join(args)


def _match_section_to_ministry(heading_line, ministries):
    """Return the ministry key best matching a section heading, or None."""
    sec_tokens = set(_normalize(_heading_args(heading_line)))
    if not sec_tokens:
        return None
    best, best_score = None, 0.0
    for key, info in ministries.items():
        # No dedup: name/org/template_org reinforcing a distinctive token
        # (e.g. "WILD", whose template heading spells out the acronym) lifts
        # an otherwise single-token match over the threshold.
        targets = (_normalize(info.get("name", "")) +
                   _normalize(info.get("org", "")) +
                   _normalize(info.get("template_org", "")))
        score = sum(max((_token_similarity(t, s) for s in sec_tokens), default=0.0)
                    for t in targets)
        if score > best_score:
            best_score, best = score, key
    # Require a real overlap (≈ two solid token matches) to avoid mis-binding.
    return best if best_score >= 1.5 else None


def _claim_by_label(pool, label):
    """Pop and return the request whose label matches `label`, else None."""
    want = set(_normalize(label))
    for i, r in enumerate(pool):
        have = set(_normalize(r.get("label", "")))
        if have and want and len(want & have) >= max(1, min(len(want), len(have)) / 2):
            return pool.pop(i)
    return None


def _fill_section(section_text, requests, log, heading):
    """Fill the @prayer() slots in one section with its requests."""
    pool = list(requests)
    out = []
    for line in section_text.splitlines(keepends=True):
        m = re.match(r"^@prayer\((.*?)\)\s*(.*?)\s*$", line)
        if not m:
            out.append(line)
            continue
        label = m.group(1).strip()
        if label:
            # Labeled (mold B): route by person.
            req = _claim_by_label(pool, label)
            if req:
                out.append(f"@prayer({label}) {req['summary']}\n")
            else:
                out.append(f"@prayer({label}) {NO_NEWS}\n")
        else:
            # Flexible slot (molds A/C): one bullet per remaining request.
            if pool:
                for req in pool:
                    out.append(f"@prayer() {req['summary']}\n")
                pool = []
            else:
                out.append("@prayer() [CONTENT NEEDED]\n")
                log(f"  No selected requests for {heading} — left [CONTENT NEEDED]")
    text = "".join(out)
    # Any labeled requests that matched no bullet: append before the close.
    if pool:
        extra = "".join(f"@prayer() {r['summary']}\n" for r in pool)
        m = re.search(r"^@end_(?:missionary|title)_section\(\)", text, re.M)
        if m:
            text = text[:m.start()] + extra + text[m.start():]
        else:
            text += extra
        log(f"  {len(pool)} request(s) for {heading} had no matching labeled "
            f"slot — appended as plain bullets")
    return text


def run_assemble(code: str, log, work_dir: Path):
    """Build {code}_ssPrayerTime.md from the month's selected requests."""
    month = f"{code[:4]}-{code[4:]}"
    md_out = Path(work_dir) / f"{code}_ssPrayerTime.md"

    if not TEMPLATE.exists():
        log(f"Template not found: {TEMPLATE.name}")
        return

    log("=== ASSEMBLE DOCUMENT ===")
    log(f"Target month: {month}")

    harvested = _harvest(work_dir, month)
    total = sum(len(v) for v in harvested.values())
    if total == 0:
        log("No selected requests for this month — run /ps-review first.")
        return
    log(f"Harvested {total} selected request(s) across "
        f"{len(harvested)} ministr(y/ies).")

    ministries = json.loads(MINISTRIES_FILE.read_text())["ministries"]
    header, sections, footer, num_pre = _split_template(TEMPLATE.read_text())
    log(f"Template: {len(sections)} section(s).")

    used_keys = set()
    filled = []
    for heading, section_text in sections:
        key = _match_section_to_ministry(heading, ministries)
        reqs = harvested.get(key, []) if key else []
        if key:
            used_keys.add(key)
        if reqs:
            log(f"  {heading[:48]} → {key} ({len(reqs)} request(s))")
        else:
            log(f"  {heading[:48]} → {key or 'NO MATCH'} (0 — placeholder kept)")
        filled.append(_fill_section(section_text, reqs, log, heading))

    # Selected requests whose ministry has no section in the template.
    orphans = {k: v for k, v in harvested.items() if k not in used_keys}
    for k, v in orphans.items():
        log(f"  WARNING: {len(v)} selected request(s) for '{k}' have no "
            f"template section — not placed. Reassign in /ps-review.")

    parts = [header]
    parts.extend(filled[:num_pre])
    if footer:
        parts.append(footer)
    parts.extend(filled[num_pre:])
    md_out.write_text("\n".join(parts))

    log(f"Done: {md_out.name}")
    log(f"Next: open and edit {md_out.name}, then Review / PDF to render.")


def main(argv=None):
    import argparse
    from lib.config import load_config
    p = argparse.ArgumentParser(description="Assemble the dated .md from the store.")
    p.add_argument("code", help="YYYYMM, e.g. 202607")
    p.add_argument("--work-dir", help="override work_dir (default: config)")
    args = p.parse_args(argv)
    work = args.work_dir or load_config()["work_dir"]
    run_assemble(args.code, lambda m: print(m), Path(work))


if __name__ == "__main__":
    main()
