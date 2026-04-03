# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A GUI production tool that produces the monthly **ssPrayerTime** prayer sheet for PGCC Missions. It uses the Anthropic API to distill concise prayer requests from missionary newsletters and correspondence, formats them into a master template, and renders the result to PDF via `rapumamd`.

The main entry point is `prayer_sheet.py`. Core logic lives in `lib/` as separate modules.

## Running the Tool

```bash
cd /home/dennis/MakerSpace/CodingProjects/MissionaryPrayerSheet/Production
.venv/bin/python prayer_sheet.py
```

Or if the venv is active:
```bash
python prayer_sheet.py
```

The script bootstraps its own venv path at startup (`sys.path.insert`), so it can also be run directly with the system `python3`.

## Architecture

`prayer_sheet.py` is the tkinter GUI entry point. All core logic lives in `lib/`:

```
Production/
├── prayer_sheet.py      # GUI only — App class, load_env, parse_date, md_path, pdf_path
├── lib/
│   ├── convert.py       # Step 2: convertmd subprocess, file rename, error logging
│   ├── prepare.py       # Step 3: template split, section matching, Claude API calls
│   ├── spellcheck.py    # Step 5: aspell via pandoc
│   └── archive.py       # Step 7: zip and cleanup
```

All long-running work runs in daemon threads to keep the GUI responsive. Thread-to-GUI communication goes through a `queue.Queue` polled every 100ms via `self.after(100, self._poll_queue)`.

**Step 2 — Convert input files (`lib/convert.py`):**
1. Runs `convertmd <file>` on each file in `input/` (skips `.md` files and the `Org/` subfolder).
2. On success: moves the original into `input/Org/`.
3. On failure: appends to `input/error.log`, sets an error flag in the GUI.
4. Rename pass: extracts sender identity and organization name from each converted `.md`, renames to `OrganizationName_LastFirst_YYYYMM.md`. Failures are logged and flagged.

**Step 3 — Prepare Document (`lib/prepare.py`):**
1. `_split_template()` — parses `template_ssPrayerTime.md` into `(header, sections, footer)`. Sections delimited by `## ` headings. Footer identified by line starting with `"Jesus reminds us"`.
2. Section matching — normalized fuzzy match between `OrganizationName` component of input filenames and `## ` section headings.
3. `run_prepare()` — one `claude-opus-4-6` API call per section with section text + matched source material. Sequential, not parallel. Sections with no matching input file retain `[CONTENT NEEDED]` placeholder.
4. Reassembles and writes `{YYYYMM}_ssPrayerTime.md`.

**Other buttons:**
- **Open in rapumamd** — launches `rapumamd` on the dated `.md` for iterative review (Step 4) and final PDF generation (Step 6).
- **Spellcheck** — pipes the dated `.md` through `pandoc -t plain` then `aspell list` against `wordlist.txt`.
- **Archive** — zips dated `.md`, `.pdf` (warns but doesn't block if missing), and all `input/` files into `archive/{YYYYMM}_ssPrayerTime.zip`, then deletes the originals.

## Key Files

| File | Purpose |
|------|---------|
| `prayer_sheet.py` | GUI entry point |
| `lib/convert.py` | Input conversion and rename logic |
| `lib/prepare.py` | Template splitting and Claude API calls |
| `lib/spellcheck.py` | Spellcheck logic |
| `lib/archive.py` | Archive logic |
| `template_ssPrayerTime.md` | Master template; edit to change sections or layout |
| `wordlist.txt` | Custom aspell dictionary (church names, acronyms) |
| `.env` | `ANTHROPIC_API_KEY=...` (never commit) |
| `QR_Codes/` | PNG QR images referenced by `<img>` tags in the template |
| `input/` | Drop source files here before running Convert |
| `input/Org/` | Originals moved here after successful conversion |
| `input/error.log` | Appended on any conversion or rename failure |
| `archive/` | Completed monthly zips |

## Template Structure

Sections are `## ` headings. Each section ends before the next `## ` heading. The footer begins at the line starting with `"Jesus reminds us"`. Placeholders are `[CONTENT NEEDED]` bullets — Claude fills only these. Sections with no matching input file retain their placeholders for manual review.

HTML page-break and spacing divs are valid inside the template:
```html
<div style="page-break-after: always;"></div>
<div style="margin-top: 16pt;"></div>
```

QR codes float right via the `qr-code` CSS class:
```html
<img src="QR_Codes/SomeOrg.png" class="qr-code" alt="Org Name">
```

## Dependencies

System: `python3`, `python3-tk`, `pandoc`, `aspell`, `aspell-en`, `convertmd`, `rapumamd`

Python (in `.venv/`): `anthropic`, `python-docx`

```bash
python3 -m venv .venv
.venv/bin/pip install anthropic python-docx
```

## Key Constraints When Editing

- Do not break the threading model — all `run_*` functions take a `log` callback and must not call tkinter directly.
- Preserve `parse_date()`, `md_path()`, `pdf_path()`, `load_env()`, and the `App` class structure in `prayer_sheet.py`.
- `weasyprint` is no longer used — do not import it.
- The `[CONTENT NEEDED]` placeholder is the signal for both unfilled and missing sections — do not change it.
- Consult `ROADMAP.md` before making any structural changes.
