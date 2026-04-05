"""Step 7: Archive zip + cleanup."""

import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = BASE / "archive"
INPUT_DIR = BASE / "input"


def md_path(code: str) -> Path:
    return BASE / f"{code}_ssPrayerTime.md"


def pdf_path(code: str) -> Path:
    return BASE / f"{code}_ssPrayerTime.pdf"


def run_archive(code: str, log, *, pdf_warning_accepted=False):
    md = md_path(code)
    pdf = pdf_path(code)
    zip_path = ARCHIVE_DIR / f"{code}_ssPrayerTime.zip"

    log("=== ARCHIVE ===")

    if not md.exists():
        log(f"Cannot archive — missing: {md.name}")
        return

    if not pdf.exists() and not pdf_warning_accepted:
        log(f"Warning: {pdf.name} not found — archive will not include a PDF.")
        log("Proceeding without PDF...")

    input_files = sorted(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else []

    log("Building zip:")
    log(f"  {md.name}")
    if pdf.exists():
        log(f"  {pdf.name}")
    for f in input_files:
        log(f"  input/{f.name}")

    ARCHIVE_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(md, md.name)
        if pdf.exists():
            zf.write(pdf, pdf.name)
        for f in input_files:
            zf.write(f, f"input/{f.name}")

    md.unlink()
    if pdf.exists():
        pdf.unlink()
    for f in input_files:
        f.unlink()

    log(f"Archived: {zip_path.name}")
    log("Production folder is ready for next month.")
