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

import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
from pathlib import Path

from lib.convert import run_convert
from lib.prepare import run_prepare
from lib.spellcheck import run_spellcheck
from lib.archive import run_archive

APP_DIR = Path(__file__).parent
WORK_DIR = Path.cwd()
INPUT_DIR = WORK_DIR / "input"
ENV_FILE = APP_DIR / ".env"


# ── Environment ───────────────────────────────────────────────────────────────

def load_env():
    """Load KEY=value pairs from .env into os.environ."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


# ── Path helpers ─────────────────────────────────────────────────────────────

def md_path(code: str) -> Path:
    return WORK_DIR / f"{code}_ssPrayerTime.md"


def pdf_path(code: str) -> Path:
    return WORK_DIR / f"{code}_ssPrayerTime.pdf"


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

        tk.Button(btn_frame, text="1. Convert Input", width=16,
                  command=self._do_convert).pack(side="left", padx=6)
        tk.Button(btn_frame, text="2. Prepare Document", width=18,
                  bg="#4a90d9", fg="white", font=("Helvetica", 10, "bold"),
                  command=self._do_prepare).pack(side="left", padx=6)
        tk.Button(btn_frame, text="3. Spellcheck", width=13,
                  command=self._do_spellcheck).pack(side="left", padx=6)
        tk.Button(btn_frame, text="4. Review / PDF", width=15,
                  command=self._do_open_rapumamd).pack(side="left", padx=6)
        tk.Button(btn_frame, text="5. Archive", width=11,
                  command=self._do_archive).pack(side="left", padx=6)

        # ── Error indicator ───────────────────────────────────────────────────
        self._error_var = tk.StringVar(value="")
        self._error_label = tk.Label(
            self, textvariable=self._error_var,
            fg="red", font=("Helvetica", 10, "bold")
        )
        self._error_label.grid(row=3, column=0, columnspan=2, pady=(0, 4))

        # ── Output area ───────────────────────────────────────────────────────
        tk.Label(self, text="Output:", anchor="w").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=12)
        self._output = scrolledtext.ScrolledText(
            self, width=70, height=16, state="disabled",
            font=("Courier", 10), wrap="word"
        )
        self._output.grid(row=5, column=0, columnspan=2, padx=12, pady=(0, 12))

        # ── Bottom buttons ────────────────────────────────────────────────────
        bottom = tk.Frame(self)
        bottom.grid(row=6, column=0, columnspan=2, pady=(0, 12))
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
                # Internal signal: set or clear the error flag
                if msg == "__ERROR_FLAG__":
                    self._error_var.set("Conversion errors \u2014 see input/error.log")
                    continue
                if msg == "__CLEAR_ERROR__":
                    self._error_var.set("")
                    continue
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

    def _do_convert(self):
        code = self._get_code()
        if not code:
            return

        def _run():
            self._log("__CLEAR_ERROR__")
            had_errors = run_convert(code, self._log, WORK_DIR)
            if had_errors:
                self._log("__ERROR_FLAG__")

        threading.Thread(target=_run, daemon=True).start()

    def _do_prepare(self):
        code = self._get_code()
        if code:
            threading.Thread(
                target=run_prepare, args=(code, self._log, WORK_DIR), daemon=True
            ).start()

    def _do_spellcheck(self):
        code = self._get_code()
        if code:
            threading.Thread(
                target=run_spellcheck, args=(code, self._log, WORK_DIR), daemon=True
            ).start()

    def _do_open_rapumamd(self):
        code = self._get_code()
        if not code:
            return
        md = md_path(code)
        if not md.exists():
            self._log(f"File not found: {md.name} — run Prepare Document first.")
            return
        self._log(f"Opening rapumamd for {md.name}...")
        subprocess.Popen(["rapumamd", str(md)])

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
                target=run_archive, args=(code, self._log, WORK_DIR), daemon=True
            ).start()
        else:
            self._log("Archive cancelled.")


if __name__ == "__main__":
    load_env()
    App().mainloop()
