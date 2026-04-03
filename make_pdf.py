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


def _convert_inputs(log):
    """Phase 1: Convert input files to .md using system convertmd command."""
    input_files = sorted(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else []
    if not input_files:
        log("No input files found in input/  — aborting.")
        return None

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
            log(f"  Warning: convertmd failed for {f.name}, using fallback reader")
        else:
            log(f"  OK: {md_version.name}")

    # Read all .md versions (or fall back to raw reader)
    source_parts = []
    for f in input_files:
        md_version = f.with_suffix(".md")
        if md_version.exists() and md_version.suffix == ".md":
            read_path = md_version
        elif f.suffix.lower() == ".md":
            read_path = f
        else:
            # fallback
            log(f"  Fallback read: {f.name}")
            try:
                content = read_input_file(f)
            except Exception as e:
                log(f"  Warning: could not read {f.name}: {e}")
                content = "(unreadable)"
            source_parts.append(f"--- {f.name} ---\n{content}")
            continue
        source_parts.append(f"--- {read_path.name} ---\n{read_path.read_text()}")

    return "\n\n".join(source_parts)


def _split_template(template_text):
    """Phase 2: Split template into header, missionary sections, and footer.

    Returns (header, sections, footer) where sections is a list of
    (heading_line, section_text) tuples. Trailing HTML divs and page-break
    markers are attached to the preceding section.
    """
    import re

    lines = template_text.splitlines(keepends=True)

    # Find all ## heading positions
    heading_indices = [i for i, line in enumerate(lines) if re.match(r"^## ", line)]

    if not heading_indices:
        # No sections found — return everything as header
        return template_text, [], ""

    # Header: everything before the first ## heading
    header = "".join(lines[:heading_indices[0]])

    # Detect footer: the closing scripture quote block.
    # Footer starts at the paragraph beginning with "Jesus reminds us"
    footer_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Jesus reminds us"):
            footer_start = i
            break

    # Find sections that come AFTER the footer (like Life Source on page 3)
    post_footer_heading_indices = []
    pre_footer_heading_indices = []
    if footer_start is not None:
        for idx in heading_indices:
            if idx > footer_start:
                post_footer_heading_indices.append(idx)
            else:
                pre_footer_heading_indices.append(idx)
    else:
        pre_footer_heading_indices = heading_indices

    # Build sections list — includes all headings (pre and post footer)
    sections = []

    all_headings = heading_indices  # process all in order
    for pos, h_idx in enumerate(all_headings):
        heading_line = lines[h_idx].strip()
        if pos + 1 < len(all_headings):
            next_h = all_headings[pos + 1]
        else:
            next_h = len(lines)

        # Section text from heading to next heading (or end)
        section_lines = lines[h_idx:next_h]
        section_text = "".join(section_lines)

        # Check if this section contains the footer quote — if so, split it
        if footer_start is not None and h_idx < footer_start < next_h:
            # Section ends at footer_start, footer is separate
            section_text = "".join(lines[h_idx:footer_start])

        sections.append((heading_line, section_text))

    # Extract footer block
    if footer_start is not None:
        # Footer runs from footer_start to the next ## heading after it,
        # or to end of file if no post-footer sections
        if post_footer_heading_indices:
            footer_end = post_footer_heading_indices[0]
        else:
            footer_end = len(lines)
        footer = "".join(lines[footer_start:footer_end])
    else:
        footer = ""

    return header, sections, footer


def run_prepare(code: str, log):
    import anthropic

    md_out = md_path(code)
    year, month = code[:4], code[4:]
    label = f"{year}/{month}"

    if not TEMPLATE.exists():
        log(f"Template not found: {TEMPLATE.name}")
        return

    log("=== PREPARE DOCUMENT ===")

    # Phase 1 — Convert input files to Markdown
    log("Phase 1: Converting input files...")
    source_material = _convert_inputs(log)
    if source_material is None:
        return

    # Phase 2 — Split template into sections
    log("Phase 2: Splitting template into sections...")
    template_text = TEMPLATE.read_text()
    header, sections, footer = _split_template(template_text)
    log(f"  Found {len(sections)} missionary section(s)")

    # Phase 3 — Call Claude per section
    log("Phase 3: Filling sections via Claude...")
    client = anthropic.Anthropic()
    filled_sections = []

    for heading, section_text in sections:
        log(f"  Sending: {heading}")
        prompt = f"""You are writing prayer requests for the monthly ssPrayerTime prayer guide ({label}).

Below is the template section for one missionary or ministry, followed by all of this month's converted source material. Fill in ONLY the bullet points marked [CONTENT NEEDED] for this section. Use only relevant content from the source material. Match the tone and formatting of the template exactly. Output only the completed section — no explanation, no commentary.

=== SECTION ===
{section_text}

=== SOURCE MATERIAL ===
{source_material}"""

        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        filled = message.content[0].text
        filled_sections.append(filled)
        log(f"  Section done: {heading}")

    # Phase 4 — Reassemble the document
    log("Phase 4: Reassembling document...")
    parts = [header]
    parts.extend(filled_sections)
    parts.append(footer)
    result = "\n".join(parts)

    md_out.write_text(result)
    log(f"Done: {md_out.name}")
    log("Review the document, then run Spellcheck and Open in rapumamd.")


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


def run_open_rapumamd(code: str, log):
    md = md_path(code)

    if not md.exists():
        log(f"File not found: {md.name}")
        return

    log(f"Opening rapumamd for {md.name}...")
    subprocess.Popen(["rapumamd", "settings", str(md)])


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
        tk.Button(btn_frame, text="Open in rapumamd", width=14,
                  command=self._do_open_rapumamd).pack(side="left", padx=6)
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

        # ── Bottom buttons ────────────────────────────────────────────────────
        bottom = tk.Frame(self)
        bottom.grid(row=5, column=0, columnspan=2, pady=(0, 12))
        tk.Button(bottom, text="Clear output",
                  command=self._clear_output).pack(side="left", padx=6)
        tk.Button(bottom, text="Close",
                  command=self.destroy).pack(side="left", padx=6)

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

    def _do_open_rapumamd(self):
        code = self._get_code()
        if code:
            threading.Thread(
                target=run_open_rapumamd, args=(code, self._log), daemon=True
            ).start()

    def _do_archive(self):
        code = self._get_code()
        if not code:
            return

        md = md_path(code)
        pdf = pdf_path(code)
        input_files = sorted(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else []

        lines = ["The following will be zipped and removed:\n"]
        lines.append(f"  \u2022 {md.name}")
        if pdf.exists():
            lines.append(f"  \u2022 {pdf.name}")
        else:
            lines.append(f"  \u2022 {pdf.name} (NOT FOUND — will archive without PDF)")
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
