"""Capture store: the request store behind a small interface.

This is the contract between capture (Skill 1), review, and assembly.
Records live in {work_dir}/capture/requests.json; processed Gmail message
ids in {work_dir}/capture/seen.json. Everything goes through this module's
CLI so the backend can later be swapped for the Pi website (Phase 6)
without touching the skills.

Record schema (one per approved-or-pending prayer request):
  id            small integer, stable across the store's life
  ministry      key into ministries.json (or "unknown" - review reassigns)
  summary       <=3-sentence distilled request text
  sender        email address the material came from
  sender_name   human name
  subject       source email subject
  message_id    Gmail message id (lets review pull the original)
  received      YYYY-MM-DD the source email arrived
  target_month  YYYY-MM of the sheet this request is for
  status        pending -> selected -> used -> archived
                (or dropped / expired)
  display       public-ok | private  (future hallway display; private is
                never shown on a public screen)
  note          optional flag text, e.g. attachment nudge
  created / updated   ISO timestamps

Target-month rule: a request belongs to the next sheet still open for
assembly. The sheet for month M is assembled the day before M's first
Sunday; past that day, new requests roll to the following month.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lib.config import load_config
else:
    from .config import load_config

APP_DIR = Path(__file__).resolve().parent.parent
MINISTRIES_FILE = APP_DIR / "ministries.json"

STATUSES = ("pending", "selected", "used", "archived", "dropped", "expired")
DISPLAYS = ("public-ok", "private")


# ---------------------------------------------------------------- storage

def capture_dir():
    d = Path(load_config()["work_dir"]) / "capture"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def _atomic_write(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def load_requests():
    return _load_json(capture_dir() / "requests.json", [])


def save_requests(records):
    _atomic_write(capture_dir() / "requests.json", records)


def load_seen():
    return set(_load_json(capture_dir() / "seen.json", []))


def save_seen(seen):
    _atomic_write(capture_dir() / "seen.json", sorted(seen))


def load_ministries():
    return json.loads(MINISTRIES_FILE.read_text())


# ----------------------------------------------------------- month logic

def first_sunday(year, month):
    d = dt.date(year, month, 1)
    return d + dt.timedelta(days=(6 - d.weekday()) % 7)


def default_target_month(today=None):
    """YYYY-MM of the next sheet still open for assembly."""
    today = today or dt.date.today()
    y, m = today.year, today.month
    for _ in range(3):
        assembly_day = first_sunday(y, m) - dt.timedelta(days=1)
        if today <= assembly_day:
            return f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1
    raise RuntimeError("could not compute target month")


# ------------------------------------------------------------- commands

def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def cmd_add(args):
    records = load_requests()
    ministries = load_ministries()["ministries"]
    display = args.display
    if not display:
        display = ministries.get(args.ministry, {}).get("display_default")
        if not display:
            display = "private"  # unknown ministry: safe default
    rec = {
        "id": max((r["id"] for r in records), default=0) + 1,
        "ministry": args.ministry,
        "summary": args.summary,
        "sender": args.sender or "",
        "sender_name": args.sender_name or "",
        "subject": args.subject or "",
        "message_id": args.message_id or "",
        "received": args.received or str(dt.date.today()),
        "target_month": args.target_month or default_target_month(),
        "status": args.status,
        "display": display,
        "note": args.note or "",
        "created": _now(),
        "updated": _now(),
    }
    records.append(rec)
    save_requests(records)
    print(json.dumps(rec, ensure_ascii=False))


def cmd_list(args):
    records = load_requests()
    if args.status:
        records = [r for r in records if r["status"] == args.status]
    if args.month:
        records = [r for r in records if r["target_month"] == args.month]
    if args.ministry:
        records = [r for r in records if r["ministry"] == args.ministry]
    print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_set(args):
    records = load_requests()
    ids = set(args.ids)
    hit = []
    for r in records:
        if r["id"] in ids:
            if args.status:
                r["status"] = args.status
            if args.summary is not None:
                r["summary"] = args.summary
            if args.display:
                r["display"] = args.display
            if args.ministry:
                r["ministry"] = args.ministry
            if args.target_month:
                r["target_month"] = args.target_month
            if args.note is not None:
                r["note"] = args.note
            r["updated"] = _now()
            hit.append(r)
    save_requests(records)
    missing = ids - {r["id"] for r in hit}
    if missing:
        print(f"warning: no record with id {sorted(missing)}", file=sys.stderr)
    print(json.dumps(hit, indent=2, ensure_ascii=False))


def cmd_mark_seen(args):
    seen = load_seen()
    seen.update(args.message_ids)
    save_seen(seen)
    print(f"seen: {len(seen)} message ids")


def cmd_check_seen(args):
    """Print the message ids NOT yet seen, one per line."""
    seen = load_seen()
    for mid in args.message_ids:
        if mid not in seen:
            print(mid)


def cmd_expire(args):
    cutoff = default_target_month()
    records = load_requests()
    expired = []
    for r in records:
        if r["status"] in ("pending", "selected") and r["target_month"] < cutoff:
            r["status"] = "expired"
            r["updated"] = _now()
            expired.append(r["id"])
    save_requests(records)
    print(f"expired: {expired or 'none'} (open target month is {cutoff})")


def cmd_status(args):
    month = args.month or default_target_month()
    ministries = load_ministries()["ministries"]
    dead = ("dropped", "expired")
    records = [r for r in load_requests()
               if r["target_month"] == month and r["status"] not in dead]
    print(f"Target month: {month} "
          f"(assembly day: {first_sunday(*map(int, month.split('-'))) - dt.timedelta(days=1)})")
    empty = []
    for key, info in ministries.items():
        counts = {}
        for r in records:
            if r["ministry"] == key:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
        if counts:
            summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
            print(f"  {info['name']:<28} {summary}")
        else:
            empty.append(f"{info['name']} (encourager: {info['encourager']['name']})")
    unknown = [r for r in records if r["ministry"] not in ministries]
    if unknown:
        print(f"  {'(unassigned)':<28} {len(unknown)} item(s) need a ministry")
    if empty:
        print("Still empty:")
        for e in empty:
            print(f"  - {e}")


def cmd_harvest(args):
    """Selected records for a month, grouped by ministry - assembly contract."""
    month = args.month or default_target_month()
    out = {}
    for r in load_requests():
        if r["target_month"] == month and r["status"] == "selected":
            out.setdefault(r["ministry"], []).append(r)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def main(argv=None):
    p = argparse.ArgumentParser(prog="store", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add a captured request (status pending)")
    a.add_argument("--ministry", required=True)
    a.add_argument("--summary", required=True)
    a.add_argument("--sender")
    a.add_argument("--sender-name", dest="sender_name")
    a.add_argument("--subject")
    a.add_argument("--message-id", dest="message_id")
    a.add_argument("--received", help="YYYY-MM-DD")
    a.add_argument("--target-month", dest="target_month", help="YYYY-MM")
    a.add_argument("--status", default="pending", choices=STATUSES)
    a.add_argument("--display", choices=DISPLAYS)
    a.add_argument("--note")
    a.set_defaults(fn=cmd_add)

    a = sub.add_parser("list", help="list records as JSON")
    a.add_argument("--status", choices=STATUSES)
    a.add_argument("--month")
    a.add_argument("--ministry")
    a.set_defaults(fn=cmd_list)

    a = sub.add_parser("set", help="update records by id")
    a.add_argument("ids", nargs="+", type=int)
    a.add_argument("--status", choices=STATUSES)
    a.add_argument("--summary")
    a.add_argument("--display", choices=DISPLAYS)
    a.add_argument("--ministry")
    a.add_argument("--target-month", dest="target_month")
    a.add_argument("--note")
    a.set_defaults(fn=cmd_set)

    a = sub.add_parser("mark-seen", help="record processed Gmail message ids")
    a.add_argument("message_ids", nargs="+")
    a.set_defaults(fn=cmd_mark_seen)

    a = sub.add_parser("check-seen", help="print which of the given ids are NEW")
    a.add_argument("message_ids", nargs="+")
    a.set_defaults(fn=cmd_check_seen)

    a = sub.add_parser("expire", help="expire pending/selected items from past months")
    a.set_defaults(fn=cmd_expire)

    a = sub.add_parser("status", help="per-ministry overview for the target month")
    a.add_argument("--month")
    a.set_defaults(fn=cmd_status)

    a = sub.add_parser("harvest", help="selected records for a month (assembly JSON)")
    a.add_argument("--month")
    a.set_defaults(fn=cmd_harvest)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
