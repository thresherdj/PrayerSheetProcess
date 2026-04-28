"""Step 3: Template split, section matching, and Claude API calls."""

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = APP_DIR / "template_ssPrayerTime.md"


def _split_template(template_text):
    """Split template into header, missionary sections, and footer.

    Returns (header, sections, footer) where sections is a list of
    (heading_line, section_text) tuples.

    Sections are delimited by @missionary() macro lines. Post-footer
    sections (e.g. Life Source) use @title() as the section delimiter.
    """
    lines = template_text.splitlines(keepends=True)

    # Find all @missionary(...) section positions
    heading_indices = [
        i for i, line in enumerate(lines) if re.match(r"^@missionary\(", line)
    ]

    # Detect footer: the closing scripture quote block.
    # Footer starts at the paragraph beginning with "Jesus reminds us"
    footer_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Jesus reminds us"):
            footer_start = i
            break

    # Find post-footer @title() sections (like Life Source on page 3)
    if footer_start is not None:
        for i, line in enumerate(lines):
            if i > footer_start and re.match(r"^@title\(", line):
                heading_indices.append(i)
        heading_indices.sort()

    if not heading_indices:
        # No sections found — return everything as header
        return template_text, [], ""

    # Header: everything before the first @missionary()
    header = "".join(lines[:heading_indices[0]])

    # Categorize headings as pre/post footer
    post_footer_heading_indices = []
    if footer_start is not None:
        post_footer_heading_indices = [
            idx for idx in heading_indices if idx > footer_start
        ]

    # Build sections list — includes all headings (pre and post footer)
    sections = []
    for pos, h_idx in enumerate(heading_indices):
        heading_line = lines[h_idx].strip()
        if pos + 1 < len(heading_indices):
            next_h = heading_indices[pos + 1]
        else:
            next_h = len(lines)

        # Section text from heading to next heading (or end)
        section_text = "".join(lines[h_idx:next_h])

        # Check if this section contains the footer quote — if so, split it
        if footer_start is not None and h_idx < footer_start < next_h:
            # Section ends at footer_start, footer is separate
            section_text = "".join(lines[h_idx:footer_start])

        sections.append((heading_line, section_text))

    # Extract footer block
    if footer_start is not None:
        if post_footer_heading_indices:
            footer_end = post_footer_heading_indices[0]
        else:
            footer_end = len(lines)
        footer = "".join(lines[footer_start:footer_end])
    else:
        footer = ""

    return header, sections, footer


# ── Section matching (3a) ────────────────────────────────────────────────────

def _normalize(text):
    """Normalize text for fuzzy matching: lowercase alpha-only tokens."""
    # Split CamelCase: "RockInternational" → "Rock International"
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Remove everything except letters and spaces
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    return text.lower().split()


def _token_similarity(tok_a, tok_b):
    """Score how well two tokens match.

    Returns a float: 1.0 for exact match, 0.8+ for strong prefix match,
    0.0 for no match. Prefix must be at least 3 chars to count.
    """
    if tok_a == tok_b:
        return 1.0
    # Prefix matching — the shorter must be at least 3 chars
    shorter, longer = (tok_a, tok_b) if len(tok_a) <= len(tok_b) else (tok_b, tok_a)
    if len(shorter) >= 3 and longer.startswith(shorter):
        return len(shorter) / len(longer)
    return 0.0


def _tokens_match(tokens_a, tokens_b):
    """Check if two token lists match via overlap or prefix matching.

    Returns True if enough tokens overlap. Handles abbreviations by checking
    if tokens from one list are prefixes of tokens in the other (min 3 chars).
    """
    if not tokens_a or not tokens_b:
        return False

    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    hits = 0
    for s in shorter:
        for l in longer:
            if _token_similarity(s, l) >= 0.5:
                hits += 1
                break

    # Require at least half the shorter token list to match
    return hits >= max(1, len(shorter) / 2)


def _match_files_to_sections(sections, md_files, log):
    """Match input .md files to template sections by organization name.

    Returns a dict: heading_line → list of Path objects.
    """
    matches = {heading: [] for heading, _ in sections}
    matched_files = set()

    # Build normalized section tokens
    section_tokens = {}
    for heading, _ in sections:
        # Extract arguments from @missionary(name, org) or @title(text)
        m = re.match(r'^@(?:missionary|title)\((.+)\)\s*$', heading)
        raw = m.group(1) if m else heading
        section_tokens[heading] = _normalize(raw)

    for f in md_files:
        # Extract OrgName from "OrgName_LastFirst_YYYYMM.md"
        parts = f.stem.split("_")
        if not parts:
            continue
        org_name = parts[0]
        file_tokens = _normalize(org_name)

        best_heading = None
        best_score = 0.0

        for heading, s_tokens in section_tokens.items():
            if _tokens_match(file_tokens, s_tokens):
                # Score by sum of best per-token similarities
                score = sum(
                    max((_token_similarity(ft, st) for st in s_tokens), default=0.0)
                    for ft in file_tokens
                )
                if score > best_score:
                    best_score = score
                    best_heading = heading

        if best_heading:
            matches[best_heading].append(f)
            matched_files.add(f)
            log(f"  Matched: {f.name} → {best_heading}")
        else:
            log(f"  Warning: {f.name} matched no section")

    return matches


# ── Main entry point ─────────────────────────────────────────────────────────

def run_prepare(code: str, log, work_dir: Path):
    import anthropic

    md_out = work_dir / f"{code}_ssPrayerTime.md"
    input_dir = work_dir / "input"
    year, month = code[:4], code[4:]
    label = f"{year}/{month}"

    if not TEMPLATE.exists():
        log(f"Template not found: {TEMPLATE.name}")
        return

    log("=== PREPARE DOCUMENT ===")

    # Phase 1 — Read converted .md files from input/
    log("Reading input files...")
    md_files = sorted(
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".md" and f.name != "error.log"
    ) if input_dir.exists() else []

    if not md_files:
        log("No .md files found in input/ — run Convert Input Files first.")
        return

    for f in md_files:
        log(f"  Found: {f.name}")

    # Phase 2 — Split template into sections
    log("Splitting template into sections...")
    template_text = TEMPLATE.read_text()
    header, sections, footer = _split_template(template_text)
    log(f"  Found {len(sections)} section(s)")

    # Phase 3 — Match input files to sections
    log("Matching input files to sections...")
    matches = _match_files_to_sections(sections, md_files, log)

    # Phase 4 — Call Claude per section (only those with matched input)
    log("Filling sections via Claude...")
    client = anthropic.Anthropic()
    filled_sections = []

    for heading, section_text in sections:
        matched_files = matches[heading]

        if not matched_files:
            log(f"  Missing input: {heading} — marked for manual review")
            filled_sections.append(section_text)
            continue

        # Concatenate matched source material
        source_parts = []
        for f in matched_files:
            source_parts.append(f"--- {f.name} ---\n{f.read_text(errors='replace')}")
        matched_content = "\n\n".join(source_parts)

        log(f"  Sending: {heading}")
        prompt = f"""You are writing prayer requests for the monthly ssPrayerTime prayer guide ({label}).

Below is the template section for one missionary or ministry, followed by all of this month's converted source material for that section. Distill clear and concise prayer requests from the source material. Each @prayer() line has [CONTENT NEEDED] after the macro call on the same line — fill in ONLY those placeholders with concise prayer text. Labeled lines look like "@prayer(Topic Name) [CONTENT NEEDED]" — keep the label, replace only [CONTENT NEEDED]. Unlabeled lines look like "@prayer() [CONTENT NEEDED]". Preserve all @prayer() macro calls exactly as written — only replace the [CONTENT NEEDED] text that follows them. Preserve all other macros (@missionary, @hrule, @title) and HTML tags exactly as they appear. Output only the completed section — no explanation, no commentary.

=== SECTION ===
{section_text}

=== SOURCE MATERIAL ===
{matched_content}"""

        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        filled = message.content[0].text
        filled_sections.append(filled)
        log(f"  Section done: {heading}")

    # Phase 5 — Reassemble the document
    log("Reassembling document...")
    parts = [header]
    parts.extend(filled_sections)
    parts.append(footer)
    result = "\n".join(parts)

    md_out.write_text(result)
    log(f"Done: {md_out.name}")
    log(f"Next: open and edit {md_out.name} in a text editor, then click 3. Spellcheck.")
