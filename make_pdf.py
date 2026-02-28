#!/usr/bin/env python3
"""
GUI PDF production tool for ssPrayerTime.

Workflow:
  1. Enter the month and click Prepare Document — Claude reads the template
     and input files and writes the dated .md.
  2. Spellcheck, then Generate PDF.
  3. Archive when the month is done.
"""

import sys
import glob
from pathlib import Path as _Path

# Ensure venv packages are available regardless of which python runs this
_venv_lib = _Path(__file__).resolve().parent / ".venv" / "lib"
for _sp in glob.glob(str(_venv_lib / "python*/site-packages")):
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import email
import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
import zipfile
from pathlib import Path

BASE = Path(__file__).parent
CSS = BASE / "prayer_style.css"
WORDLIST = BASE / "wordlist.txt"
ARCHIVE_DIR = BASE / "archive"
INPUT_DIR = BASE / "input"
TEMPLATE = BASE / "template_ssPrayerTime.md"
ENV_FILE = BASE / ".env"


# ── Environment ───────────────────────────────────────────────────────────────

def load_env():
    """Load KEY=value pairs from .env into os.environ."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


# ── File readers ──────────────────────────────────────────────────────────────

def read_docx(path: Path) -> str:
    import docx
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_eml(path: Path) -> str:
    msg = email.message_from_bytes(path.read_bytes())
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                parts.append(part.get_payload(decode=True).decode(errors="replace"))
    else:
        parts.append(msg.get_payload(decode=True).decode(errors="replace"))
    return "\n".join(parts)


def read_input_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    elif suffix == ".eml":
        return read_eml(path)
    else:
        return path.read_text(errors="replace")


# ── Core logic (runs in worker threads) ───────────────────────────────────────

def md_path(code: str) -> Path:
    return BASE / f"{code}_ssPrayerTime.md"


def pdf_path(code: str) -> Path:
    return BASE / f"{code}_ssPrayerTime.pdf"


def parse_date(raw: str):
    """Return YYYYMM string or None if invalid."""
    parts = raw.strip().split("/")
    if (
        len(parts) == 2
        and len(parts[0]) == 4 and parts[0].isdigit()
        and len(parts[1]) == 2 and parts[1].isdigit()
    ):
        return parts[0] + parts[1]
    return None


def run_prepare(code: str, log):
    import anthropic

    md_out = md_path(code)
    year, month = code[:4], code[4:]
    label = f"{year}/{month}"

    if not TEMPLATE.exists():
        log(f"Template not found: {TEMPLATE.name}")
        return

    log("=== PREPARE DOCUMENT ===")
    log(f"Reading template...")
    template_text = TEMPLATE.read_text()

    input_files = sorted(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else []
    if not input_files:
        log("No input files found in input/  — aborting.")
        return

    # Build input file block
    input_block = ""
    for f in input_files:
        log(f"Reading input: {f.name}")
        try:
            content = read_input_file(f)
        except Exception as e:
            log(f"  Warning: could not read {f.name}: {e}")
            content = "(unreadable)"
        input_block += f"\n\n--- {f.name} ---\n{content}"

    prompt = f"""You are preparing the monthly ssPrayerTime prayer guide for {label}.

Below is the template used every month, followed by this month's input files containing prayer requests and missionary updates.

Using the input content, fill in the template to produce the {label} edition. Follow the template's structure, tone, and formatting exactly. Replace placeholder content with real content from the inputs. Output only the completed Markdown document — no explanation, no commentary.

=== TEMPLATE ===
{template_text}

=== INPUT FILES ==={input_block}
"""

    log("Sending to Claude...")
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    result = message.content[0].text
    md_out.write_text(result)
    log(f"Done: {md_out.name}")
    log("Review the document, then run Spellcheck and Generate PDF.")


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


def run_generate_pdf(code: str, log):
    from weasyprint import HTML, CSS as WeasyCSS

    md = md_path(code)
    pdf = pdf_path(code)
    html = Path(f"/tmp/{code}_prayer_preview.html")

    if not md.exists():
        log(f"File not found: {md.name}")
        return

    log("=== BUILDING PDF ===")

    r = subprocess.run(
        [
            "pandoc", str(md),
            "--standalone",
            "--embed-resources",
            "--css", str(CSS.resolve()),
            "--metadata", "title=",
            "-o", str(html),
        ],
        capture_output=True, text=True,
        cwd=str(BASE)
    )
    if r.returncode != 0:
        log(f"pandoc error: {r.stderr.strip()}")
        return

    log("Converting to PDF via WeasyPrint...")
    try:
        HTML(filename=str(html)).write_pdf(
            str(pdf),
            stylesheets=[WeasyCSS(filename=str(CSS.resolve()))]
        )
        log(f"Done: {pdf.name}")
        subprocess.Popen(["xdg-open", str(pdf)])
    except Exception as e:
        log(f"PDF generation failed: {e}")


def run_archive(code: str, log):
    md = md_path(code)
    pdf = pdf_path(code)
    zip_path = ARCHIVE_DIR / f"{code}_ssPrayerTime.zip"

    log("=== ARCHIVE ===")

    missing = [f.name for f in [md, pdf] if not f.exists()]
    if missing:
        log(f"Cannot archive — missing: {', '.join(missing)}")
        return

    input_files = sorted(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else []

    log("Building zip:")
    log(f"  {md.name}")
    log(f"  {pdf.name}")
    for f in input_files:
        log(f"  input/{f.name}")

    ARCHIVE_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(md, md.name)
        zf.write(pdf, pdf.name)
        for f in input_files:
            zf.write(f, f"input/{f.name}")

    md.unlink()
    pdf.unlink()
    for f in input_files:
        f.unlink()

    log(f"Archived: {zip_path.name}")
    log("Production folder is ready for next month.")


# ── GUI ───────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ssPrayerTime PDF Production")
        self.resizable(False, False)
        self._msg_queue = queue.Queue()
        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ── Header ────────────────────────────────────────────────────────────
        tk.Label(self, text="ssPrayerTime PDF Production",
                 font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(14, 4))

        # ── Month entry ───────────────────────────────────────────────────────
        tk.Label(self, text="Month (YYYY/MM):").grid(
            row=1, column=0, sticky="e", **pad)
        self._month_var = tk.StringVar(value=datetime.now().strftime("%Y/%m"))
        tk.Entry(self, textvariable=self._month_var, width=12,
                 font=("Courier", 12)).grid(
            row=1, column=1, sticky="w", **pad)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=8)

        tk.Button(btn_frame, text="Prepare Document", width=16,
                  bg="#4a90d9", fg="white", font=("Helvetica", 10, "bold"),
                  command=self._do_prepare).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Spellcheck", width=12,
                  command=self._do_spellcheck).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Generate PDF", width=12,
                  command=self._do_generate_pdf).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Archive", width=12,
                  command=self._do_archive).pack(side="left", padx=6)

        # ── Output area ───────────────────────────────────────────────────────
        tk.Label(self, text="Output:", anchor="w").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=12)
        self._output = scrolledtext.ScrolledText(
            self, width=70, height=16, state="disabled",
            font=("Courier", 10), wrap="word"
        )
        self._output.grid(row=4, column=0, columnspan=2, padx=12, pady=(0, 12))

        # ── Clear button ──────────────────────────────────────────────────────
        tk.Button(self, text="Clear output",
                  command=self._clear_output).grid(
            row=5, column=0, columnspan=2, pady=(0, 12))

    # ── Output helpers ────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self._msg_queue.put(msg)

    def _poll_queue(self):
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                self._output.configure(state="normal")
                self._output.insert("end", msg + "\n")
                self._output.see("end")
                self._output.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _clear_output(self):
        self._output.configure(state="normal")
        self._output.delete("1.0", "end")
        self._output.configure(state="disabled")

    # ── Date validation ───────────────────────────────────────────────────────

    def _get_code(self):
        code = parse_date(self._month_var.get())
        if not code:
            messagebox.showerror("Invalid date",
                                 "Enter month as YYYY/MM (e.g. 2026/03)")
        return code

    # ── Button handlers ───────────────────────────────────────────────────────

    def _do_prepare(self):
        code = self._get_code()
        if code:
            threading.Thread(
                target=run_prepare, args=(code, self._log), daemon=True
            ).start()

    def _do_spellcheck(self):
        code = self._get_code()
        if code:
            threading.Thread(
                target=run_spellcheck, args=(code, self._log), daemon=True
            ).start()

    def _do_generate_pdf(self):
        code = self._get_code()
        if code:
            threading.Thread(
                target=run_generate_pdf, args=(code, self._log), daemon=True
            ).start()

    def _do_archive(self):
        code = self._get_code()
        if not code:
            return

        md = md_path(code)
        pdf = pdf_path(code)
        input_files = sorted(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else []

        lines = ["The following will be zipped and removed:\n"]
        for f in [md, pdf]:
            lines.append(f"  \u2022 {f.name}")
        for f in input_files:
            lines.append(f"  \u2022 input/{f.name}")
        lines.append(f"\nZip: archive/{code}_ssPrayerTime.zip")
        lines.append("\nProceed?")

        if messagebox.askyesno("Confirm Archive", "\n".join(lines)):
            threading.Thread(
                target=run_archive, args=(code, self._log), daemon=True
            ).start()
        else:
            self._log("Archive cancelled.")


if __name__ == "__main__":
    load_env()
    App().mainloop()
