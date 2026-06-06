"""Project-local macros for the ssPrayerTime template."""


_section_qr_stack = []


def _escape(text: str) -> str:
    """Escape LaTeX special characters in user-supplied text."""
    for ch, esc in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                    ("#", r"\#"), ("_", r"\_")]:
        text = text.replace(ch, esc)
    return text


def missionary(*args) -> str:
    """@missionary(name, organization) — section heading for a missionary entry."""
    name = _escape(args[0]) if args else "Name"
    org = _escape(args[1]) if len(args) > 1 else ""
    if org:
        return f"\\subsection*{{{name} — {org}}}"
    return f"\\subsection*{{{name}}}"


def missionary_section(*args) -> str:
    """@missionary_section(name, organization, qr_path) — open a section with
    the QR floated to the top-right (wrapfigure) and the heading + body +
    bullets flowing as normal, page-breakable text. Must be paired with
    @end_missionary_section(). qr_path optional; omitted = full width.

    Floated (not minipage) so a long section can split across a page break and
    fill the space, rather than leaping whole to the next page.
    """
    name = _escape(args[0]) if args else "Name"
    org = _escape(args[1]) if len(args) > 1 else ""
    qr = args[2].strip() if len(args) > 2 else ""
    _section_qr_stack.append(qr)
    heading = f"{name} — {org}" if org else name

    if not qr:
        return f"\n\n\\subsection*{{{heading}}}\n\n"

    return (
        "\n\n```{=latex}\n"
        "\\begin{wrapfigure}{r}{1.15in}\n"
        "\\vspace{-\\baselineskip}\n"
        f"\\includegraphics[width=1in]{{{qr}}}\n"
        "\\end{wrapfigure}\n"
        f"\\subsection*{{{heading}}}\n"
        "```\n\n"
    )


def end_missionary_section(*args) -> str:
    """@end_missionary_section() — close a section opened by
    @missionary_section(). The QR is floated at the section top now, so this
    just ends the section's text block."""
    if _section_qr_stack:
        _section_qr_stack.pop()
    return "\n\n"


def title_section(*args) -> str:
    """@title_section(text, qr_path) — a post-footer section (e.g. Life Source).
    Structurally identical to @missionary_section: a left-aligned \\subsection*
    heading with the QR floated top-right and the body flowing/breakable. (An
    earlier centered-title version fought wrapfig and shifted the body's
    margins, so the heading uses the same style as the other sections.)
    Paired with @end_title_section(). qr_path optional.
    """
    text = _escape(args[0]) if args else "Untitled"
    qr = args[1].strip() if len(args) > 1 else ""
    _section_qr_stack.append(qr)
    heading = f"\\subsection*{{{text}}}"

    if not qr:
        return f"\n\n{heading}\n\n"

    return (
        "\n\n```{=latex}\n"
        "\\begin{wrapfigure}{r}{1.15in}\n"
        "\\vspace{-\\baselineskip}\n"
        f"\\includegraphics[width=1in]{{{qr}}}\n"
        "\\end{wrapfigure}\n"
        f"{heading}\n"
        "```\n\n"
    )


def end_title_section(*args) -> str:
    """@end_title_section() — close a section opened by @title_section()."""
    return end_missionary_section(*args)


def prayer(*args) -> str:
    """@prayer(label) — start a prayer request bullet point.
    If a label is given, it is bold followed by an em dash.
    Text after the macro call continues in default style.
    e.g. @prayer(Lake Lucerne Gospel Chapel) pray for new members
    """
    label = args[0].strip() if args and args[0].strip() else ""
    if label:
        return f"- **{label}** —"
    return f"-"

def title(*args) -> str:
    """@title(text, size, styles) — styled title block.

    Parameters:
        text   — the title text (required)
        size   — font size, e.g. 24pt (default: 24pt)
        styles — space-separated style flags (default: bold center)

    Style flags (combine any):
        bold        bold text
        italic      italic text
        smallcaps   small capitals
        underline   underlined text
        mono        monospaced / typewriter
        sans        sans-serif
        center      centered (default)
        left        left-aligned
        right       right-aligned
        rule        add a horizontal rule below

    Examples:
        @title(My Document)
        @title(My Document, 28pt)
        @title(My Document, 24pt, bold center rule)
        @title(My Document, 20pt, bold italic smallcaps center)
    """
    text = args[0] if args else "Untitled"
    size = args[1] if len(args) > 1 else "24pt"
    style_str = args[2] if len(args) > 2 else "bold center"
    styles = set(style_str.lower().split())

    # Build the inner text with typography wrappers (inside out)
    inner = text
    if "bold" in styles:
        inner = f"\\textbf{{{inner}}}"
    if "italic" in styles:
        inner = f"\\textit{{{inner}}}"
    if "smallcaps" in styles:
        inner = f"\\textsc{{{inner}}}"
    if "underline" in styles:
        inner = f"\\underline{{{inner}}}"
    if "mono" in styles:
        inner = f"\\texttt{{{inner}}}"
    if "sans" in styles:
        inner = f"\\textsf{{{inner}}}"

    # Wrap in font size
    inner = f"\\begingroup\\fontsize{{{size}}}{{{size}}}\\selectfont {inner}\\endgroup"

    # Alignment
    if "right" in styles:
        inner = f"\\begin{{flushright}}{inner}\\end{{flushright}}"
    elif "left" in styles:
        inner = f"\\noindent {inner}"
    else:
        # center is the default
        inner = f"\\begin{{center}}{inner}\\end{{center}}"

    # Optional rule below
    if "rule" in styles:
        inner += "\n\\vspace{4pt}\n\\noindent\\rule{\\textwidth}{0.5pt}\n"

    return inner
