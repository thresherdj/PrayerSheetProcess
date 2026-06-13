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
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
from datetime import datetime
from pathlib import Path

from lib.config import load_config, save_config
from lib.convert import run_convert
from lib.prepare import run_prepare
from lib.assemble import run_assemble
from lib.spellcheck import run_spellcheck
from lib.archive import run_archive

APP_DIR = Path(__file__).parent
ENV_FILE = APP_DIR / ".env"

# Working/archive folders come from ~/.config/mtps/config.json, not cwd —
# so `mtps` can be launched from anywhere. _apply_dirs() keeps these in sync.
WORK_DIR = Path()
ARCHIVE_DIR = Path()
INPUT_DIR = Path()


def _apply_dirs(work, archive, persist=True):
    """Set the working and archive folders (and derived input/) globally.

    Reassigns the module globals that md_path/pdf_path and the GUI read.
    When persist is True, writes the choice back to the config file.
    """
    global WORK_DIR, ARCHIVE_DIR, INPUT_DIR
    WORK_DIR = Path(work)
    ARCHIVE_DIR = Path(archive)
    INPUT_DIR = WORK_DIR / "input"
    if persist:
        save_config({"work_dir": str(WORK_DIR), "archive_dir": str(ARCHIVE_DIR)})


_cfg = load_config()
_apply_dirs(_cfg["work_dir"], _cfg["archive_dir"], persist=False)


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

        # ── Folders (remembered in ~/.config/mtps/config.json) ────────────────
        folders = tk.LabelFrame(self, text="Folders", padx=8, pady=4)
        folders.grid(row=2, column=0, columnspan=2, padx=12, pady=(0, 4), sticky="ew")

        self._work_var = tk.StringVar(value=str(WORK_DIR))
        tk.Label(folders, text="Working:").grid(row=0, column=0, sticky="e")
        tk.Label(folders, textvariable=self._work_var, anchor="w",
                 width=52, fg="#333").grid(row=0, column=1, sticky="w", padx=4)
        tk.Button(folders, text="Change…",
                  command=self._change_work).grid(row=0, column=2, padx=4)

        self._archive_var = tk.StringVar(value=str(ARCHIVE_DIR))
        tk.Label(folders, text="Archive:").grid(row=1, column=0, sticky="e")
        tk.Label(folders, textvariable=self._archive_var, anchor="w",
                 width=52, fg="#333").grid(row=1, column=1, sticky="w", padx=4)
        tk.Button(folders, text="Change…",
                  command=self._change_archive).grid(row=1, column=2, padx=4)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=8)

        tk.Button(btn_frame, text="1. Assemble", width=13,
                  bg="#4a90d9", fg="white", font=("Helvetica", 10, "bold"),
                  command=self._do_assemble).pack(side="left", padx=6)
        tk.Button(btn_frame, text="2. Spellcheck", width=13,
                  command=self._do_spellcheck).pack(side="left", padx=6)
        tk.Button(btn_frame, text="3. Review / PDF", width=15,
                  command=self._do_open_rapumamd).pack(side="left", padx=6)
        tk.Button(btn_frame, text="4. Archive", width=11,
                  command=self._do_archive).pack(side="left", padx=6)

        # ── Legacy input pipeline (pre-capture flow; retiring in Phase 5) ──────
        legacy = tk.Frame(self)
        legacy.grid(row=4, column=0, columnspan=2, pady=(0, 4))
        tk.Label(legacy, text="Legacy:", fg="#888").pack(side="left", padx=(12, 4))
        tk.Button(legacy, text="Convert Input", width=14,
                  command=self._do_convert).pack(side="left", padx=4)
        tk.Button(legacy, text="Prepare (Claude)", width=16,
                  command=self._do_prepare).pack(side="left", padx=4)

        # ── Error indicator ───────────────────────────────────────────────────
        self._error_var = tk.StringVar(value="")
        self._error_label = tk.Label(
            self, textvariable=self._error_var,
            fg="red", font=("Helvetica", 10, "bold")
        )
        self._error_label.grid(row=5, column=0, columnspan=2, pady=(0, 4))

        # ── Output area ───────────────────────────────────────────────────────
        tk.Label(self, text="Output:", anchor="w").grid(
            row=6, column=0, columnspan=2, sticky="w", padx=12)
        self._output = scrolledtext.ScrolledText(
            self, width=70, height=16, state="disabled",
            font=("Courier", 10), wrap="word"
        )
        self._output.grid(row=7, column=0, columnspan=2, padx=12, pady=(0, 12))
        self._output.tag_configure(
            "instruct",
            font=("Courier", 10, "bold"),
            foreground="#1a5f1a",
            spacing1=8, spacing3=4,
            lmargin1=4, lmargin2=4,
        )

        # ── Bottom buttons ────────────────────────────────────────────────────
        bottom = tk.Frame(self)
        bottom.grid(row=8, column=0, columnspan=2, pady=(0, 12))
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
                    self._error_var.set("Errors occurred \u2014 see Output below.")
                    continue
                if msg == "__CLEAR_ERROR__":
                    self._error_var.set("")
                    continue
                self._output.configure(state="normal")
                tag = "instruct" if msg.lstrip().startswith("Next:") else None
                if tag:
                    self._output.insert("end", msg + "\n", tag)
                else:
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

    # ── Folder settings ─────────────────────────────────────────────────────────

    def _change_work(self):
        d = filedialog.askdirectory(
            initialdir=str(WORK_DIR), title="Select working folder")
        if d:
            _apply_dirs(d, ARCHIVE_DIR)
            self._work_var.set(str(WORK_DIR))
            self._log(f"Working folder set to: {WORK_DIR}")

    def _change_archive(self):
        d = filedialog.askdirectory(
            initialdir=str(ARCHIVE_DIR), title="Select archive folder")
        if d:
            _apply_dirs(WORK_DIR, d)
            self._archive_var.set(str(ARCHIVE_DIR))
            self._log(f"Archive folder set to: {ARCHIVE_DIR}")

    # ── Date validation ───────────────────────────────────────────────────────

    def _get_code(self):
        code = parse_date(self._month_var.get())
        if not code:
            messagebox.showerror("Invalid date",
                                 "Enter month as YYYY/MM (e.g. 2026/03)")
        return code

    # ── Button handlers ───────────────────────────────────────────────────────

    def _spawn(self, fn, *args):
        """Run fn(*args) in a daemon thread, routing any uncaught exception to
        the GUI Output + error flag instead of crashing the thread silently."""
        def _wrapped():
            try:
                fn(*args)
            except Exception as e:
                self._log(f"\nUnexpected error: {e}")
                self._log("__ERROR_FLAG__")
        threading.Thread(target=_wrapped, daemon=True).start()

    def _do_convert(self):
        code = self._get_code()
        if not code:
            return

        def _run():
            self._log("__CLEAR_ERROR__")
            if run_convert(code, self._log, WORK_DIR):
                self._log("__ERROR_FLAG__")

        self._spawn(_run)

    def _do_prepare(self):
        code = self._get_code()
        if code:
            self._spawn(run_prepare, code, self._log, WORK_DIR)

    def _do_assemble(self):
        code = self._get_code()
        if code:
            self._spawn(run_assemble, code, self._log, WORK_DIR)

    def _do_spellcheck(self):
        code = self._get_code()
        if code:
            self._spawn(run_spellcheck, code, self._log, WORK_DIR)

    def _do_open_rapumamd(self):
        code = self._get_code()
        if not code:
            return
        md = md_path(code)
        if not md.exists():
            self._log(f"File not found: {md.name} — run Prepare Document first.")
            return
        self._log(f"Opening rapumamd for {md.name}...")

        def launch():
            # rapumamd resolves macros from a macros.py next to the .md (local),
            # which takes precedence over the user-global ~/.config/rapumamd/macros.py.
            # Sync the project's macros.py (source of truth in the app dir) into the
            # work folder so the current project macros are always the ones used.
            try:
                shutil.copy2(APP_DIR / "macros.py", WORK_DIR / "macros.py")
            except OSError as e:
                self._log(f"Warning: could not sync macros.py to the work folder: {e}")

            try:
                proc = subprocess.run(
                    ["rapumamd", "render", str(md)],
                    capture_output=True,
                    text=True,
                    cwd=str(WORK_DIR),
                )
            except FileNotFoundError:
                self._log("Error: 'rapumamd' command not found on PATH. Install it with `pipx install -e ~/MakerSpace/CodingProjects/RapumaMD`.")
                return
            except Exception as e:
                self._log(f"Error launching rapumamd: {e}")
                return

            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "(no output)").strip()
                self._log(f"rapumamd failed (exit {proc.returncode}):\n{err}")
                return

            out = (proc.stdout or "").strip()
            if out:
                self._log(out)
            self._log("rapumamd render complete.")

        threading.Thread(target=launch, daemon=True).start()

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
        lines.append(f"\nZip: {ARCHIVE_DIR / (code + '_ssPrayerTime.zip')}")
        lines.append("\nProceed?")

        if messagebox.askyesno("Confirm Archive", "\n".join(lines)):
            self._spawn(run_archive, code, self._log, WORK_DIR, ARCHIVE_DIR)
        else:
            self._log("Archive cancelled.")


if __name__ == "__main__":
    load_env()
    App().mainloop()
