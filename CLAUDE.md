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
│   ├── convert.py       # Step 2: convertmd subprocess, rename, error logging
│   ├── prepare.py       # Step 3: template split, Claude API calls
│   ├── spellcheck.py    # Step 5: aspell via pandoc
│   └── archive.py       # Step 7: zip and cleanup
```

All long-running work runs in daemon threads to keep the GUI responsive. Thread-to-GUI communication goes through a `queue.Queue` polled every 100ms via `self.after(100, self._poll_queue)`.

**Step 2 — Convert Input Files (`lib/convert.py`):**
1. Runs `convertmd <file>` on each non-`.md` file in `input/` (all conversion goes through the system-wide `convertmd` tool — no built-in readers).
2. On success: moves the original into `input/Org/`.
3. On failure: appends to `input/error.log`, sets an error flag in the GUI.
4. Rename pass: identifies each file by checking `known_senders.json` first (instant, free), then falling back to a `claude-haiku-4-5` API call for unknown files. Renames to `OrganizationName_LastFirst_YYYYMM.md`. Failures are logged and flagged.

**Step 3 — Prepare Document (`lib/prepare.py`):**
1. Reads `.md` files from `input/` and matches them to template sections by normalized organization name.
2. `_split_template()` — parses `template_ssPrayerTime.md` into `(header, sections, footer, num_pre_footer)`. Sections delimited by `@missionary_section(...)` lines. Footer identified by line starting with `"Jesus reminds us"`. Post-footer sections (e.g. Life Source) use `@title()` as the section delimiter. `num_pre_footer` says how many of the returned sections appear before the footer in source order, so the reassembler can put the footer between them and the post-footer sections instead of dumping it at the very end.
3. `run_prepare()` — one `claude-opus-4-6` API call per section with section text + only the matched source material. Sequential, not parallel. Sections with no matching input retain `[CONTENT NEEDED]` placeholder.
4. Reassembles in source order: `header + filled_sections[:num_pre_footer] + footer + filled_sections[num_pre_footer:]`. Writes `{YYYYMM}_ssPrayerTime.md`.

**Other buttons:**
- **Open in rapumamd** — launches `rapumamd` on the dated `.md` for iterative review (Step 4) and final PDF generation (Step 6).
- **Spellcheck** — pipes the dated `.md` through `pandoc -t plain` then `aspell list` against `wordlist.txt`.
- **Archive** — zips dated `.md`, `.pdf` (warns but doesn't block if missing), and all `input/` files into `archive/{YYYYMM}_ssPrayerTime.zip`, then deletes the originals.

### Template Structure

The template uses RapumaMD macros (expanded at render time via `macros.py`):

- `@missionary_section(Name, Organization, qr_path)` / `@end_missionary_section()` — open/close a two-column section. Heading + body + bullets sit in a fixed-width left minipage; the QR code sits in a fixed-width right minipage. Every line in the section has uniform width — no wrapfigure flow inconsistency. `qr_path` is optional; if omitted the section runs full width.
- `@missionary(Name, Organization)` — legacy section heading (just emits a `\subsection*`); kept for backwards compatibility.
- `@prayer(label)` — a prayer request bullet. The optional label appears bold before an em dash; prayer text (or `[CONTENT NEEDED]`) follows on the same line after the macro call. e.g. `@prayer(Topic Name) [CONTENT NEEDED]` or `@prayer() [CONTENT NEEDED]`.
- `@hrule(1pt)` — horizontal rule between sections.
- `@title(text)` — styled title block (document title and post-footer sections like Life Source).
- `@today()` — current date (used in frontmatter and title).

Sections are delimited by `@missionary_section(...)` lines. The footer begins at the line starting with `"Jesus reminds us"`. Post-footer sections (e.g., Life Source on page 3) use `@title()` as the delimiter and are handled correctly.

The two-column layout works by emitting pandoc raw-LaTeX fences (` ```{=latex} ` ... ` ``` `) around `\begin{minipage}` / `\end{minipage}` tags. This is required because pandoc treats raw `\begin{...}...\end{...}` blocks in markdown as opaque LaTeX and does not process bullets/paragraphs inside; the fence form keeps the LaTeX scaffolding raw while letting the body content between fences be processed as markdown.

The `@missionary_section` / `@end_missionary_section` pair shares state through a module-level stack in `macros.py` so the closing macro knows the QR path supplied by the opener. RapumaMD caches loaded macro modules across calls within a render so this state persists correctly.

## Key Files

| File | Purpose |
|------|---------|
| `prayer_sheet.py` | GUI entry point |
| `lib/convert.py` | Input conversion via convertmd + rename |
| `lib/prepare.py` | Template splitting and Claude API calls |
| `lib/spellcheck.py` | Spellcheck logic |
| `lib/archive.py` | Archive logic |
| `template_ssPrayerTime.md` | Master template; edit to change sections or layout |
| `macros.py` | Project-local RapumaMD macros (missionary_section, end_missionary_section, missionary, prayer, title) |
| `wordlist.txt` | Custom aspell dictionary (church names, acronyms) |
| `.env` | `ANTHROPIC_API_KEY=...` (never commit) |
| `QR_Codes/` | PNG QR images referenced by `<img>` tags in the template |
| `known_senders.json` | Lookup table mapping text patterns to org/sender names |
| `input/` | Drop source files here before running Convert |
| `archive/` | Completed monthly zips |

## Dependencies

System: `python3`, `python3-tk`, `pandoc`, `aspell`, `aspell-en`, `convertmd`, `rapumamd`

Python (in `.venv/`): `anthropic`

```bash
python3 -m venv .venv
.venv/bin/pip install anthropic
```

## Key Constraints When Editing

- Do not break the threading model — all `run_*` functions take a `log` callback and must not call tkinter directly.
- Preserve `parse_date()`, `md_path()`, `pdf_path()`, `load_env()`, and the `App` class structure in `prayer_sheet.py`.
- The `[CONTENT NEEDED]` placeholder is the signal for both unfilled and missing sections — do not change it.
- Consult `ROADMAP.md` before making any structural changes.
