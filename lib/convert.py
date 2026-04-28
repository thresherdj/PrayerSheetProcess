"""Step 2: Input conversion via convertmd + rename."""

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
KNOWN_SENDERS = APP_DIR / "known_senders.json"


# ── Error logging ────────────────────────────────────────────────────────────

def _log_error(filename, message, error_log):
    """Append a timestamped error to input/error.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(error_log, "a") as f:
        f.write(f"[{ts}] {filename}: {message}\n")


# ── 2b: Rename logic ────────────────────────────────────────────────────────

def _load_known_senders():
    """Load the known_senders.json lookup table."""
    if KNOWN_SENDERS.exists():
        return json.loads(KNOWN_SENDERS.read_text())
    return {}


def _match_known_sender(content, known):
    """Check if the file content matches any known sender pattern.

    Scans the full content (lowercased) for each key in known_senders.json.
    Returns (org, sender) tuple or (None, None).
    """
    content_lower = content.lower()
    # Try longest keys first to prefer specific matches over short ones
    for key in sorted(known, key=len, reverse=True):
        if key in content_lower:
            entry = known[key]
            return entry["org"], entry["sender"]
    return None, None


def _identify_via_claude(content, filename, log):
    """Use a Claude API call to extract org and sender from file content.

    Returns (org, sender) tuple or (None, None) on failure.
    """
    import anthropic

    # Send only the first ~2000 words to keep the call cheap
    truncated = " ".join(content.split()[:2000])

    prompt = f"""Analyze this converted newsletter/email and extract two things:

1. **Organization name** — the ministry, mission, church, or organization this communication is from.
2. **Sender name** — the primary person who sent or authored this (first and last name).

Respond with ONLY a JSON object in this exact format, nothing else:
{{"org": "OrganizationName", "sender": "LastFirst"}}

Rules:
- org should be CamelCase with no spaces (e.g., "RockInternational", "FortWilderness", "MidwestIndianMission")
- sender should be LastnameFirstname with no spaces (e.g., "SmithJohn", "DewingDon")
- If the sender is known by a title (Dr., Rev., etc.), omit the title
- If you cannot determine either field with confidence, use null for that field

Filename: {filename}

Content:
{truncated}"""

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Parse the JSON response
        result = json.loads(raw)
        org = result.get("org")
        sender = result.get("sender")
        # Validate: must be alpha-only strings
        if org and not re.match(r'^[A-Za-z]+$', org):
            org = re.sub(r'[^A-Za-z]', '', org) or None
        if sender and not re.match(r'^[A-Za-z]+$', sender):
            sender = re.sub(r'[^A-Za-z]', '', sender) or None
        return org, sender
    except Exception as e:
        log(f"  Claude identification failed: {e}")
        return None, None


# ── Main entry point ─────────────────────────────────────────────────────────

def run_convert(code, log, work_dir: Path):
    """Run the full conversion pipeline: convertmd + rename.

    Returns True if there were errors, False if clean.
    """
    input_dir = work_dir / "input"
    org_dir = input_dir / "Org"
    error_log = input_dir / "error.log"

    had_errors = False

    log("=== CONVERT INPUT FILES ===")

    if not input_dir.exists():
        log("No input/ directory found — aborting.")
        return True

    # Clear error.log for this run
    if error_log.exists():
        error_log.unlink()

    org_dir.mkdir(exist_ok=True)

    # ── 2a: convertmd conversion ─────────────────────────────────────────
    log("Phase 1: Converting files to Markdown...")

    input_files = sorted(
        f for f in input_dir.iterdir()
        if f.is_file() and f.name != "error.log"
    )

    if not input_files:
        log("No input files found in input/ — aborting.")
        return True

    for f in input_files:
        if f.suffix.lower() == ".md":
            log(f"  Already .md: {f.name}")
            continue

        log(f"  Converting: {f.name}")
        result = subprocess.run(
            ["convertmd", str(f)],
            capture_output=True, text=True,
        )
        md_version = f.with_suffix(".md")

        if result.returncode != 0 or not md_version.exists():
            err_detail = result.stderr.strip() or "convertmd returned non-zero"
            log(f"  FAILED: {f.name} — {err_detail}")
            _log_error(f.name, f"convertmd failed: {err_detail}", error_log)
            had_errors = True
        else:
            # Move original to Org/
            dest = org_dir / f.name
            shutil.move(str(f), str(dest))
            log(f"  OK: {md_version.name} (original → Org/)")

    # ── 2b: Rename pass ─────────────────────────────────────────────────
    log("Phase 2: Renaming converted files...")

    known = _load_known_senders()
    if known:
        log(f"  Loaded {len(known)} known sender patterns")
    else:
        log("  Warning: known_senders.json not found — using Claude only")

    md_files = sorted(
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".md" and f.name != "error.log"
    )

    for f in md_files:
        # Skip files already in the expected format (with optional _N suffix)
        if re.match(r'^[A-Za-z]+_[A-Za-z]+_\d{6}(_\d+)?\.md$', f.name):
            log(f"  Already named: {f.name}")
            continue

        try:
            content = f.read_text(errors="replace")
        except Exception as e:
            log(f"  FAILED read: {f.name} — {e}")
            _log_error(f.name, f"Could not read for rename: {e}", error_log)
            had_errors = True
            continue

        # Try known senders first
        org, sender = _match_known_sender(content, known)
        if org and sender:
            log(f"  Identified (known): {f.name} → {org}/{sender}")
        else:
            # Fall back to Claude
            log(f"  Not in known_senders — asking Claude: {f.name}")
            org, sender = _identify_via_claude(content, f.name, log)
            if org and sender:
                log(f"  Identified (Claude): {f.name} → {org}/{sender}")

        if not org:
            log(f"  FAILED rename: {f.name} — could not determine organization")
            _log_error(f.name, "Rename failed: could not determine organization name", error_log)
            had_errors = True
            continue

        if not sender:
            log(f"  FAILED rename: {f.name} — could not determine sender")
            _log_error(f.name, "Rename failed: could not determine sender identity", error_log)
            had_errors = True
            continue

        new_name = f"{org}_{sender}_{code}.md"
        new_path = input_dir / new_name

        # If the name is taken, append _2, _3, etc.
        if new_path.exists() and new_path != f:
            n = 2
            while True:
                new_name = f"{org}_{sender}_{code}_{n}.md"
                new_path = input_dir / new_name
                if not new_path.exists() or new_path == f:
                    break
                n += 1

        f.rename(new_path)
        log(f"  Renamed: {f.name} → {new_name}")

    # ── Summary ──────────────────────────────────────────────────────────
    if had_errors:
        log(f"\nConversion completed with errors — see input/error.log")
    else:
        log("\nConversion completed successfully.")

    return had_errors
