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

2. **Run the GUI** — Launch `make_pdf.py`, enter the month in `YYYY/MM` format.

3. **Prepare Document** — Click this button to process the month's inputs.
   First, all input files are converted to Markdown via `convertmd`. Then the
   template is split into individual missionary sections, and each section is
   sent to Claude AI separately with the converted source material. Claude
   fills in only the `[CONTENT NEEDED]` placeholders for that section. The
   filled sections are reassembled into the dated `.md` file (e.g.,
   `202603_ssPrayerTime.md`).

4. **Review** — Open the generated `.md` file and review/edit the content as
   needed before generating the PDF.

5. **Spellcheck** — Runs aspell against a custom church wordlist. Review any
   flagged words before proceeding.

6. **Open in rapumamd** — Opens the dated `.md` file in `rapumamd`, the
   system-wide Markdown-to-PDF tool, for PDF generation and preview.

7. **Archive** — When the month is complete, click Archive. This zips the
   dated `.md`, `.pdf`, and all `input/` files into `archive/`, then clears
   Production for the next month.

---

## File Structure

```
Production/
├── template_ssPrayerTime.md     # Master template — edit to change layout/structure
├── make_pdf.py                  # GUI production script
├── prayer_style.css             # Print stylesheet (margins, fonts, QR layout)
├── wordlist.txt                 # Custom aspell dictionary (church names, etc.)
├── .env                         # Anthropic API key (never share or commit)
├── .venv/                       # Python virtual environment
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
| `python-docx` | Reads `.docx` input files (fallback if convertmd fails) |

Install all Python packages:
```bash
python3 -m venv .venv
.venv/bin/pip install anthropic python-docx
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

- **QR codes** are referenced by `<img>` tags in the template. They float
  to the right of each section's description at 1" square.
- **Page breaks** can be inserted anywhere with:
  ```html
  <div style="page-break-after: always;"></div>
  ```
- **Extra spacing** between elements:
  ```html
  <div style="margin-top: 16pt;"></div>
  ```
- After editing the template, always re-run **Prepare Document** to regenerate
  the dated `.md` — existing dated files do not update automatically.
