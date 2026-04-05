"""Step 5: Spellcheck via aspell + pandoc."""

import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
WORDLIST = BASE / "wordlist.txt"


def md_path(code: str) -> Path:
    return BASE / f"{code}_ssPrayerTime.md"


def run_spellcheck(code: str, log):
    md = md_path(code)
    if not md.exists():
        log(f"File not found: {md.name}")
        return

    log("=== SPELLCHECK ===")

    pandoc = subprocess.run(
        ["pandoc", str(md), "-t", "plain"],
        capture_output=True, text=True
    )
    if pandoc.returncode != 0:
        log(f"pandoc error: {pandoc.stderr.strip()}")
        return

    aspell = subprocess.run(
        [
            "aspell", "list",
            "--lang=en_US",
            f"--personal={WORDLIST.resolve()}",
            "--ignore-case",
        ],
        input=pandoc.stdout,
        capture_output=True, text=True
    )

    flagged = sorted(set(aspell.stdout.splitlines()))
    if flagged:
        log("Possible spelling issues (review before generating PDF):\n")
        for word in flagged:
            log(f"  - {word}")
    else:
        log("No spelling issues found.")
