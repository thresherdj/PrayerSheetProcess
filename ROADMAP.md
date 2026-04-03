# ssPrayerTime Rewrite Roadmap

This document describes the planned rewrite of `make_pdf.py`. A Claude agent
should use this as its implementation spec. Read `README.md`, `make_pdf.py`,
and `template_ssPrayerTime.md` for full context before making changes.

---

## Steps That Are Unchanged

- **Step 1 — Collect input files:** No change. User drops source documents
  into `input/` as before.
- **Step 2 — Launch GUI / enter month:** No change. `make_pdf.py` launches
  with a `YYYY/MM` month entry field.
- **Step 4 — Review:** No change. User opens and edits the generated `.md`
  file manually.
- **Step 5 — Spellcheck:** No change. Button runs `aspell` via `pandoc`
  against `wordlist.txt`.
- **Step 7 — Archive:** No change. Zips dated `.md`, `.pdf`, and `input/`
  files into `archive/`, then clears Production.

---

## Step 3 — Prepare Document (REWRITE)

### Goal
Reduce token usage and improve speed by pre-converting input files to
Markdown before sending anything to Claude. Then call Claude once per
missionary section rather than once for the entire document.

### New Prepare Document Workflow

**Phase 1 — Convert input files**

Use the system `convertmd` command to convert every file in `input/` to
`.md`. Call it as a subprocess for each file:

```
convertmd <input_file>
```

`convertmd` writes a `.md` file alongside the original (same name, `.md`
extension). After conversion, read the `.md` versions instead of the raw
`.docx`/`.eml` files. Log each conversion step to the output area.

If `convertmd` fails on a file, fall back to the existing `read_input_file()`
logic for that file and log a warning.

**Phase 2 — Split template into sections**

Parse `template_ssPrayerTime.md` into individual missionary sections. A
section begins at a `## ` heading and ends just before the next `## `
heading (or end of file). Preserve any HTML divs and page-break markers that
fall between sections — attach them to the preceding section so they are
re-inserted correctly when reassembling.

The header block (everything before the first `## ` heading) and the footer
block (the closing scripture quote and trailing divs) should be extracted
separately and passed through unchanged.

**Phase 3 — Call Claude per section**

For each missionary section, send one Claude API call with this structure:

```
You are writing prayer requests for the monthly ssPrayerTime prayer guide
({YYYY/MM}).

Below is the template section for one missionary or ministry, followed by
all of this month's converted source material. Fill in ONLY the bullet
points marked [CONTENT NEEDED] for this section. Use only relevant content
from the source material. Match the tone and formatting of the template
exactly. Output only the completed section — no explanation, no commentary.

=== SECTION ===
{section_text}

=== SOURCE MATERIAL ===
{all_converted_md_content}
```

Use `claude-opus-4-6` (same model as current). Run the section calls
sequentially (not in parallel) to keep log output readable. Log progress
as each section completes: `Section done: {heading}`.

**Phase 4 — Reassemble the document**

Concatenate: header block + filled sections (in original order, with their
preserved divs/page-breaks) + footer block. Write the result to
`{YYYYMM}_ssPrayerTime.md` exactly as before.

### Remove from run_prepare
- The `read_docx()` and `read_eml()` functions can be kept as fallbacks but
  are no longer the primary path.
- The single monolithic prompt that sent template + all input at once is
  replaced by the per-section calls above.

---

## Step 6 — Generate PDF (REWRITE)

### Goal
Replace the weasyprint/pandoc PDF pipeline with `rapumamd`, the system-wide
Markdown-to-PDF tool.

### Changes

**Remove entirely:**
- `run_generate_pdf()` function
- All `weasyprint` imports and usage
- The pandoc HTML conversion step in the PDF workflow
- `prayer_style.css` is no longer needed for PDF generation (keep the file
  in place for reference, but do not use it)

**Replace the Generate PDF button behavior:**

Rename the button label to **"Open in rapumamd"**.

When clicked, the button should launch `rapumamd` as a subprocess pointed
at the current month's dated `.md` file:

```python
subprocess.Popen(["rapumamd", str(md_path(code))])
```

Log `Opening rapumamd for {md_file.name}...` to the output area.

If the dated `.md` file does not exist yet, log an error and do nothing
(same guard as the old generate step).

The archive step currently checks that a `.pdf` file exists before
proceeding. Since PDF generation is now external, update `run_archive()` to
check for the `.pdf` in the `BASE` directory but prompt the user with a
warning (not a hard stop) if it is missing, allowing them to archive without
a PDF if they choose.

---

## Dependencies — What to Remove

After the rewrite, `weasyprint` is no longer used. Remove it from any
install instructions in `README.md`. The `.venv` can keep the package
installed — do not uninstall it, just stop importing it.

Update `README.md` to reflect:
- Step 3's new convertmd + per-section Claude flow
- Step 6's new rapumamd button

---

## Implementation Notes for the Agent

1. Read `make_pdf.py` in full before editing — the threading model, queue
   logging, and GUI layout all need to be preserved.
2. Make all changes in-place to `make_pdf.py`. Do not create a new file.
3. The section-splitting parser must be robust to the template's mixed
   Markdown/HTML. Test against the actual `template_ssPrayerTime.md`.
4. Keep `parse_date()`, `md_path()`, `pdf_path()`, `load_env()`, and the
   entire GUI class structure intact — only modify what is described above.
5. After rewriting, update `README.md` steps 3 and 6 to match the new
   behavior.
