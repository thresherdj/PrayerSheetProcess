# ssPrayerTime Production System

## Overview

This system produces the monthly **ssPrayerTime** prayer sheet for Pine Grove
Community Church (PGCC) Missions. Each month, prayer requests and missionary
updates are collected from various sources, reviewed by Claude AI, and compiled
into a formatted PDF ready for distribution.

---

## Workflow

1. **Collect input files** — Drop the month's source documents (emails, Word
   files, etc.) into the `input/` folder.

2. **Run the GUI** — Launch `prayer_sheet.py`, enter the month in `YYYY/MM` format.

3. **Prepare Document** — Click this button to process the month's inputs.
   First, all input files are converted to Markdown via `convertmd`. Then the
   template is split into individual missionary sections, and each section is
   sent to Claude AI separately with the converted source material. Claude
   fills in only the `[CONTENT NEEDED]` placeholders for that section. The
   filled sections are reassembled into the dated `.md` file (e.g.,
   `202603_ssPrayerTime.md`).

4. **Review** — Open the generated `.md` file and review/edit the content as
   needed.

5. **Spellcheck** — Runs aspell against a custom church wordlist. Review any
   flagged words before proceeding.

6. **Render PDF independently** — Use `rapumamd` outside this tool to render
   the dated `.md` to PDF. The production tool does not launch rapumamd.

7. **Archive** — When the month is complete, click Archive. This zips the
   dated `.md`, `.pdf` (if present), and all `input/` files into `archive/`,
   then clears Production for the next month.

---

## File Structure

```
Production/
├── prayer_sheet.py              # GUI entry point
├── macros.py                    # Project-local RapumaMD macros
├── template_ssPrayerTime.md     # Master template — edit to change layout/structure
├── known_senders.json           # Pattern → org/sender lookup for file rename
├── wordlist.txt                 # Custom aspell dictionary (church names, etc.)
├── .env                         # Anthropic API key (never share or commit)
├── .venv/                       # Python virtual environment
├── lib/
│   ├── convert.py               # Step 2: convertmd conversion + rename
│   ├── prepare.py               # Step 3: template split + Claude API calls
│   ├── spellcheck.py            # Step 5: aspell via pandoc
│   └── archive.py               # Step 7: zip and cleanup
├── QR_Codes/                    # QR code images (1" square, float right in PDF)
├── input/                       # Monthly source files — cleared on archive
└── archive/                     # Zipped monthly archives
```

### QR Code Files

| File | Organization |
|------|-------------|
| `MidwestIndianMissionOrg.png` | Midwest Indian Mission |
| `LivingStonesInternationalOrg.png` | Living Stones International |
| `FortWildernessCom.png` | Fort Wilderness |
| `OperationChristmasChildOrg.png` | Operation Christmas Child |
| `RockInternationalOrg.png` | ROCK International |
| `WildOrg.png` | WILD |
| `lifesourceministries.org.png` | Life Source |
| `InternationalMessengersOrg.png` | International Messengers (reserved) |

To update a QR code, replace the image file in `QR_Codes/` keeping the same
filename. To change which QR appears with which section, edit the `<img>` tag
in `template_ssPrayerTime.md`.

---

## Dependencies

### System Packages
Install via your package manager (`apt`, etc.):

| Package | Purpose |
|---------|---------|
| `python3` | Runs the GUI script |
| `python3-tk` | tkinter GUI framework (usually included with python3) |
| `pandoc` | Used by spellcheck to extract plain text |
| `aspell` | Spellchecker |
| `aspell-en` | English dictionary for aspell |
| `convertmd` | Converts input files (.docx, .eml, etc.) to Markdown |
| `rapumamd` | Markdown-to-PDF renderer (replaces weasyprint) |

### Python Packages
Installed in `.venv/` — no system-wide installation needed:

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude AI API client (Prepare Document) |

Install all Python packages:
```bash
python3 -m venv .venv
.venv/bin/pip install anthropic
```

### API Key
An **Anthropic API key** is required for the Prepare Document step.
Obtain one at [console.anthropic.com](https://console.anthropic.com).

Add it to the `.env` file in this folder:
```
ANTHROPIC_API_KEY=your-key-here
```

The script loads this automatically at startup. Never paste the key into
chat or commit it to version control.

---

## Template Editing Notes

The template uses RapumaMD macros (defined in `macros.py`, expanded at render time):

- `@missionary(Name, Organization)` — section heading
- `@prayer(label)` — prayer request bullet; an optional label appears bold before an em dash, with the prayer text following on the same line. `[CONTENT NEEDED]` after the macro is what Claude fills. Examples: `@prayer(Topic) [CONTENT NEEDED]`, `@prayer() [CONTENT NEEDED]`
- `@hrule(1pt)` — horizontal rule between sections
- `@title(text)` — styled title block
- `@today()` — current date

**QR codes** are referenced by `<img>` tags with `class="qr-code"` — they float
right at 1" square.

After editing the template, always re-run **Prepare Document** to regenerate
the dated `.md` — existing dated files do not update automatically.
