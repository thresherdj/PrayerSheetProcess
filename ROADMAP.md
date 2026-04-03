# ssPrayerTime Production System — Roadmap

This document is the implementation spec for the ssPrayerTime refactor. Before
making any changes, read `prayer_sheet.py` (or `make_pdf.py` if the rename has
not yet occurred), `template_ssPrayerTime.md`, and `README.md` in full.

---

## Goal

The ssPrayerTime production system is a GUI tool that assists the missions
coordinator at Pine Grove Community Church (PGCC) in producing a monthly prayer
sheet for distribution to the congregation. Each month, prayer updates are
collected from missionaries and ministries in various file formats. The system
converts those files to Markdown, uses Claude AI to distill concise prayer
requests from newsletters and other correspondence, then formats these prayer
requests into the corresponding sections of a master template, and renders the
result to a polished PDF via RapumaMD. The workflow is designed to minimize
manual effort while keeping the human in control of review, editing, and final
approval at each stage.

---

## Workflow Overview (7 Steps)

| Step | Name | Status |
|------|------|--------|
| 1 | Launch GUI / enter month | Complete — needs testing |
| 2 | Convert input files | Partial — needs significant new features |
| 3 | Prepare Document | Partial — needs section matching + missing-section logic |
| 4 | Review (iterative PDF render) | Not implemented — rapumamd button missing |
| 5 | Spellcheck | Complete — needs testing |
| 6 | Generate final PDF | Not implemented — rapumamd button missing |
| 7 | Archive | Complete — needs testing |

---

## Architecture

### Rename main script
Rename `make_pdf.py` → `prayer_sheet.py`. This is the main entry point. Do not
create a new file; rename and update all references.

### Modular structure
Break logic out of the monolithic script into a `lib/` subdirectory alongside
`prayer_sheet.py`. Suggested module breakdown:

```
Production/
├── prayer_sheet.py          # GUI entry point only — imports from lib/
├── lib/
│   ├── convert.py           # Step 2: input conversion + rename
│   ├── prepare.py           # Step 3: template split + Claude calls
│   ├── spellcheck.py        # Step 5: aspell via pandoc
│   └── archive.py           # Step 7: zip + cleanup
```

`prayer_sheet.py` contains only the `App` tkinter class, `load_env()`,
`parse_date()`, `md_path()`, `pdf_path()`, and `__main__` entry. All
`run_*` and helper functions move to their respective `lib/` modules.

### Threading model — do not break
All `run_*` functions accept a `log` callback and must never call tkinter
directly. Thread-to-GUI communication goes through `queue.Queue` polled every
100ms via `self.after(100, self._poll_queue)`. This model must be preserved
across the refactor.

### Salvage from make_pdf.py
The following are complete and should be moved, not rewritten:
- `read_docx()`, `read_eml()`, `read_input_file()` → `lib/convert.py`
- `_split_template()` → `lib/prepare.py`
- `run_spellcheck()` → `lib/spellcheck.py`
- `run_archive()` → `lib/archive.py`
- `_convert_inputs()` → `lib/convert.py` (base logic — see Phase 2 for new features)
- `run_prepare()` → `lib/prepare.py` (base logic — see Phase 3 for updates)
- All GUI code, `load_env()`, `parse_date()`, `md_path()`, `pdf_path()` → `prayer_sheet.py`

---

## Implementation Phases

---

### Phase 1 — Refactor: Modular Architecture

**Goal:** Establish the new file structure before any feature work. Everything
else builds on this.

**Tasks:**
1. Create `lib/` directory.
2. Move functions to their respective modules as described above.
3. Update `prayer_sheet.py` to import from `lib/`.
4. Rename `make_pdf.py` → `prayer_sheet.py`.
5. Verify the GUI launches and all existing buttons still function (Prepare
   Document, Spellcheck, Archive) before proceeding to Phase 2.

**Do not change any logic in this phase — move only.**

---

### Phase 2 — Step 2: Input Conversion Pipeline

**Goal:** Robust, logged, user-visible input file conversion with rename and
error flagging.

This phase rewrites `lib/convert.py` (`_convert_inputs()` and supporting
functions).

#### 2a — convertmd conversion

For each file in `input/` (skip `.md` files, skip the `Org/` subfolder):

1. Run `convertmd <file>` as a subprocess.
2. On success: move the original file into `input/Org/` (create if needed).
3. On failure: log the error to `input/error.log` (append, timestamped), leave
   the file in place, set an error flag (see 2c).

```
input/
├── Org/          # originals moved here after successful conversion
├── error.log     # appended on any failure
└── *.md          # converted files ready for rename
```

#### 2b — File rename

After conversion, rename each `.md` file in `input/` (excluding `Org/`) using
the following logic. This is a separate pass from convertmd.

**Extraction targets:**
- **Sender identity** — try in order: email `From:` header, document author
  metadata, original filename. Extract last and first name where possible.
- **Ministry/organization name** — try in order: email `Subject:` line, document
  title, prominent organization name in the first 500 words of content.

**Output filename format:**
```
OrganizationName_LastFirst_YYYYMM.md
```
Where `YYYYMM` is the current production month entered in the GUI.

Examples:
```
RockInternational_SmithJohn_202604.md
FortWilderness_JonesMary_202604.md
```

**Failure handling:**
- If either the organization name or sender identity cannot be determined
  with reasonable confidence, do not rename the file.
- Log the failure to `input/error.log` (append, timestamped, include filename
  and what was attempted).
- Set the error flag (see 2c).
- Leave the file with its current name in `input/`.

**Success condition:** When the full conversion + rename pass completes, only
`.md` files should remain in `input/` (the `Org/` subfolder holds originals).
Any file that failed conversion or rename remains in its original state.

#### 2c — Error flag in GUI

Add a visible error indicator to the GUI (e.g., a red label or status line
below the button row). It should:
- Appear whenever `input/error.log` contains entries from the current run.
- Display a short message: `"Conversion errors — see input/error.log"`
- Clear when a new conversion run starts.

This is a GUI change in `prayer_sheet.py`; the flag state is passed back
through the `log` callback or a return value from `run_convert()`.

---

### Phase 3 — Step 3: Prepare Document

**Goal:** Match converted input files to template sections, send per-section
Claude calls, handle missing inputs gracefully.

This phase updates `lib/prepare.py`.

#### 3a — Section matching

After Step 2, `input/` contains renamed `.md` files in the format
`OrganizationName_LastFirst_YYYYMM.md`. Template sections are `## ` headings
(e.g., `## Rock International`, `## Fort Wilderness`).

Matching logic:
1. Normalize both the section heading and the `OrganizationName` component of
   each filename (lowercase, remove punctuation, collapse spaces).
2. Match on exact or close substring. For example, `rockintl` should match
   `rock international`; use simple fuzzy heuristics or token overlap.
3. A section may match zero, one, or multiple input files.
4. Files that match no section should be logged as a warning (not an error).

#### 3b — Claude call per section

For each section in the template:

- If **one or more** input files matched: concatenate their content as source
  material and send one Claude API call using the prompt structure below.
- If **no input files matched**: leave the `[CONTENT NEEDED]` placeholder
  in place and log: `  Missing input: {heading} — marked for manual review`.

Prompt structure (unchanged from current implementation):
```
You are writing prayer requests for the monthly ssPrayerTime prayer guide
({YYYY/MM}).

Below is the template section for one missionary or ministry, followed by
all of this month's converted source material for that section. Distill
clear and concise prayer requests from the source material. Fill in ONLY
the bullet points marked [CONTENT NEEDED] for this section. Match the tone
and formatting of the template exactly. Output only the completed section —
no explanation, no commentary.

=== SECTION ===
{section_text}

=== SOURCE MATERIAL ===
{matched_input_content}
```

Use `claude-opus-4-6`. Run calls sequentially. Log progress:
`  Section done: {heading}` or `  Missing input: {heading}`.

#### 3c — Reassembly

Unchanged from current implementation: header + filled sections (with
preserved divs/page-breaks) + footer → `{YYYYMM}_ssPrayerTime.md`.

---

### Phase 4 — GUI: rapumamd Button (Steps 4 and 6)

**Goal:** Add the "Open in rapumamd" button for iterative review (Step 4) and
final PDF generation (Step 6). These are the same action; one button serves
both purposes.

**Changes to `prayer_sheet.py`:**

Add an **"Open in rapumamd"** button to the main button row (between Spellcheck
and Archive):

```python
tk.Button(btn_frame, text="Open in rapumamd", width=18,
          command=self._do_open_rapumamd).pack(side="left", padx=6)
```

Handler:
```python
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
```

The user may click this button multiple times during review (Step 4) and once
more for the final render (Step 6). No state tracking is needed — it simply
launches `rapumamd` pointed at the current month's `.md` file each time.

---

### Phase 5 — Integration Testing

Test each step end-to-end in order. Check the following:

| Step | Test |
|------|------|
| 1 | GUI launches, month entry defaults to current month, invalid entry shows error |
| 2 | convertmd runs on each file type; originals move to `Org/`; failures log to `error.log`; rename produces correct filenames; error flag appears when failures exist |
| 3 | Each section matched to correct input file(s); missing sections left with `[CONTENT NEEDED]`; Claude fills present sections correctly; output `.md` is well-formed |
| 4 | "Open in rapumamd" button renders PDF; user can edit `.md` and re-render |
| 5 | Spellcheck flags real misspellings; church names in `wordlist.txt` pass clean |
| 6 | Final PDF renders correctly via "Open in rapumamd" |
| 7 | Archive zips `.md`, `.pdf` (warns but does not block if missing), and `input/` files; clears Production |

---

## Key Constraints

- Do not break the threading model. All `run_*` functions take a `log`
  callback and must never call tkinter directly.
- Preserve `parse_date()`, `md_path()`, `pdf_path()`, `load_env()`, and the
  `App` class structure.
- `weasyprint` is no longer used. Do not import it. Leave it installed in
  `.venv/` but remove it from any documentation.
- The `[CONTENT NEEDED]` placeholder in the template is the signal for both
  missing sections and unfilled sections — do not change it.
- `prayer_style.css` — keep the file in place for reference, do not use it.

---

## Key Files

| File | Purpose |
|------|---------|
| `prayer_sheet.py` | GUI entry point — imports from `lib/` |
| `lib/convert.py` | Step 2: convertmd, rename, error logging |
| `lib/prepare.py` | Step 3: template split, section matching, Claude calls |
| `lib/spellcheck.py` | Step 5: aspell via pandoc |
| `lib/archive.py` | Step 7: zip and cleanup |
| `template_ssPrayerTime.md` | Master template — sections delimited by `## ` headings |
| `wordlist.txt` | Custom aspell dictionary (church names, acronyms) |
| `.env` | `ANTHROPIC_API_KEY=...` — never commit |
| `QR_Codes/` | PNG QR images referenced by `<img>` tags in template |
| `input/` | Monthly source files; `Org/` subfolder holds originals post-conversion |
| `input/error.log` | Appended on any conversion or rename failure |
| `archive/` | Completed monthly zips |
