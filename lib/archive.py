"""Step 7: Archive zip + cleanup."""

import zipfile
from pathlib import Path


def run_archive(code: str, log, work_dir: Path, *, pdf_warning_accepted=False):
    archive_dir = work_dir / "archive"
    input_dir = work_dir / "input"
    md = work_dir / f"{code}_ssPrayerTime.md"
    pdf = work_dir / f"{code}_ssPrayerTime.pdf"
    zip_path = archive_dir / f"{code}_ssPrayerTime.zip"

    log("=== ARCHIVE ===")

    if not md.exists():
        log(f"Cannot archive — missing: {md.name}")
        return

    if not pdf.exists() and not pdf_warning_accepted:
        log(f"Warning: {pdf.name} not found — archive will not include a PDF.")
        log("Proceeding without PDF...")

    input_files = sorted(input_dir.iterdir()) if input_dir.exists() else []

    log("Building zip:")
    log(f"  {md.name}")
    if pdf.exists():
        log(f"  {pdf.name}")
    for f in input_files:
        log(f"  input/{f.name}")

    archive_dir.mkdir(exist_ok=True)
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
    log("Working folder is ready for next month.")
