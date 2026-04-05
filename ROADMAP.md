# ssPrayerTime Production System — Roadmap

This document is the implementation spec for the ssPrayerTime refactor.
Consult `prayer_sheet.py`, `template_ssPrayerTime.md`, and `README.md`
for current behavior before making changes.

---

## Goal

The ssPrayerTime production system is a GUI tool that assists the missions
coordinator at Pine Grove Community Church (PGCC) in producing a monthly prayer
sheet for distribution to the congregation. Each month, prayer updates are
collected from missionaries and ministries in various file formats. The system
converts those files to Markdown via `convertmd`, uses Claude AI to distill
concise prayer requests from newsletters and other correspondence, then formats
these prayer requests into the corresponding sections of a master template, and
renders the result to a polished PDF via RapumaMD. The workflow is designed to
minimize manual effort while keeping the human in control of review, editing,
and final approval at each stage.

---

## Workflow Overview (7 Steps)

| Step | Name | Status |
|------|------|--------|
| 1 | Launch GUI / enter month | Complete |
| 2 | Convert input files | Complete |
| 3 | Prepare Document | Complete |
| 4 | Review (iterative PDF render) | Complete |
| 5 | Spellcheck | Complete |
| 6 | Generate final PDF | Complete |
| 7 | Archive | Complete |

All phases implemented. Integration testing (Phase 5) passed for steps 1, 3,
5, and 7 programmatically. Steps 2, 4, and 6 require manual testing with real
input files and external tools (`convertmd`, `rapumamd`, Claude API).

---

## Architecture

### Entry point

`prayer_sheet.py` — the tkinter GUI. Contains `App`, `load_env()`,
`parse_date()`, `md_path()`, `pdf_path()`, and `__main__` entry.

### Modular structure

```
Production/
├── prayer_sheet.py          # GUI entry point only — imports from lib/
├── lib/
│   ├── convert.py           # Step 2: convertmd conversion + rename
│   ├── prepare.py           # Step 3: template split + section matching + Claude calls
│   ├── spellcheck.py        # Step 5: aspell via pandoc
│   └── archive.py           # Step 7: zip + cleanup
```

### Conversion

All file-to-Markdown conversion goes through the system-wide `convertmd` tool.
There are no built-in file readers (docx, eml, etc.) in this project —
`convertmd` handles all formats including OCR PDFs. If `convertmd` fails for a
file, the failure is logged and the file is left in place for manual handling.

### Threading model — do not break

All `run_*` functions accept a `log` callback and must never call tkinter
directly. Thread-to-GUI communication goes through `queue.Queue` polled every
100ms via `self.after(100, self._poll_queue)`. The error flag uses special
signal messages (`__ERROR_FLAG__`, `__CLEAR_ERROR__`) through the same queue.

---

## Implementation Phases

All phases are complete. The sections below document what was implemented
in each phase for reference.

---

### Phase 1 — Refactor: Modular Architecture (Complete)

Established the modular file structure. Moved functions from the monolithic
`make_pdf.py` into `prayer_sheet.py` + `lib/` modules. `make_pdf.py` deleted;
recoverable from git history.

---

### Phase 2 — Step 2: Input Conversion Pipeline (Complete)

Implemented `run_convert(code, log)` in `lib/convert.py`:

#### 2a — convertmd conversion

For each file in `input/` (skip `.md` files, skip the `Org/` subfolder):

1. Run `convertmd <file>` as a subprocess.
2. On success: move the original file into `input/Org/` (create if needed).
3. On failure: log the error to `input/error.log` (append, timestamped), leave
   the file in place, set an error flag (see 2c).

#### 2b — File rename

After conversion, rename each `.md` file in `input/` (excluding `Org/`).
Identification uses a two-tier strategy:

1. **`known_senders.json` lookup** — a JSON file mapping lowercase text
   patterns (e.g., `"midwest indian mission"`, `"lsi"`) to `{"org": "...",
   "sender": "..."}` objects. The file content is scanned for each key
   (longest-first). This handles the recurring ~8 missionaries with zero
   API cost. Edit this file to add new contacts or correct misidentifications.

2. **Claude Haiku fallback** — if no known sender matches, a
   `claude-haiku-4-5` API call reads the first ~2000 words and returns the
   org name (CamelCase) and sender name (LastFirst). Cheap and fast, handles
   new/unexpected files intelligently.

**Output filename format:**
```
OrganizationName_LastFirst_YYYYMM.md
```

**Failure handling:** If either field cannot be determined by either method,
the file is not renamed, the failure is logged to `input/error.log`, and the
error flag is set.

#### 2c — Error flag in GUI

Red label below the button row. Appears when `run_convert()` reports errors.
Clears when a new conversion run starts.

---

### Phase 3 — Step 3: Prepare Document (Complete)

Implemented section matching and per-section Claude calls in `lib/prepare.py`.

#### 3a — Section matching

Matching normalizes both the `OrganizationName` from input filenames and the
`@missionary()` / `@title()` macro arguments: CamelCase splitting, lowercase, alpha-only tokens. Matching
uses token overlap with prefix support (minimum 3-character prefix). Best-
scoring section wins when multiple could match. A section may match zero, one,
or multiple input files. Unmatched files are logged as warnings.

#### 3b — Claude call per section

- If **one or more** input files matched: concatenate their content and send
  one `claude-opus-4-6` API call with the section text + matched source material.
- If **no input files matched**: retain the `[CONTENT NEEDED]` placeholder
  and log: `  Missing input: {heading} — marked for manual review`.

#### 3c — Reassembly

header + filled sections (with preserved divs/page-breaks) + footer →
`{YYYYMM}_ssPrayerTime.md`.

---

### Phase 4 — GUI: rapumamd Button (Complete)

Added "Open in rapumamd" button between Spellcheck and Archive. Launches
`rapumamd` via `subprocess.Popen` pointed at the current month's `.md` file.
No state tracking — user clicks it as many times as needed for review and
final rendering.

---

### Phase 5 — Integration Testing (Complete)

| Step | Test | Result |
|------|------|--------|
| 1 | GUI launches, month entry defaults to current month, invalid entry shows error | Pass |
| 2 | Requires manual testing with real files and `convertmd` | Manual |
| 3 | Template splits into 8 sections; matching handles single/multiple files per section; unmatched sections retain `[CONTENT NEEDED]` | Pass |
| 4 | "Open in rapumamd" button present in correct position | Pass |
| 5 | Spellcheck flags real misspellings; church names in `wordlist.txt` pass clean | Pass |
| 6 | Same button as Step 4 | Pass |
| 7 | Archive zips `.md`, `.pdf`, and `input/` files; deletes originals | Pass |

---

## Key Constraints

- Do not break the threading model. All `run_*` functions take a `log`
  callback and must never call tkinter directly.
- Preserve `parse_date()`, `md_path()`, `pdf_path()`, `load_env()`, and the
  `App` class structure.
- All file conversion goes through system-wide `convertmd` — do not add
  built-in file readers.
- The `[CONTENT NEEDED]` placeholder that follows each `@prayer()` macro call on
  the same line is the signal for missing/unfilled sections — do not change it.

---

## Key Files

| File | Purpose |
|------|---------|
| `prayer_sheet.py` | GUI entry point — imports from `lib/` |
| `lib/convert.py` | Step 2: convertmd conversion, rename, error logging |
| `lib/prepare.py` | Step 3: template split, section matching, Claude calls |
| `lib/spellcheck.py` | Step 5: aspell via pandoc |
| `lib/archive.py` | Step 7: zip and cleanup |
| `template_ssPrayerTime.md` | Master template — sections delimited by `@missionary()` macros |
| `macros.py` | Project-local RapumaMD macros (missionary, prayer, title, hrule) |
| `known_senders.json` | Lookup table: text patterns → org/sender names for file rename |
| `wordlist.txt` | Custom aspell dictionary (church names, acronyms) |
| `.env` | `ANTHROPIC_API_KEY=...` — never commit |
| `QR_Codes/` | PNG QR images referenced by `<img>` tags in template |
| `input/` | Monthly source files; `Org/` subfolder holds originals post-conversion |
| `input/error.log` | Appended on any conversion or rename failure |
| `archive/` | Completed monthly zips |

---

## Dependencies

System: `python3`, `python3-tk`, `pandoc`, `aspell`, `aspell-en`, `convertmd`,
`rapumamd`

Python (in `.venv/`): `anthropic`

```bash
python3 -m venv .venv
.venv/bin/pip install anthropic
```
