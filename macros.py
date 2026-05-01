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
    """@missionary_section(name, organization, qr_path) — open a two-column
    section with the body text on the left and the QR code on the right.
    Must be paired with @end_missionary_section() at the end of the section.
    qr_path is optional; if omitted the section runs full width.

    Layout: text in a fixed-width left minipage, QR in a fixed-width right
    minipage. Every line in the section has the same width — no wrapfigure
    flow inconsistency.
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
        "\\noindent\\begin{minipage}[t]{0.78\\textwidth}\n"
        f"\\subsection*{{{heading}}}\n"
        "```\n\n"
    )


def end_missionary_section(*args) -> str:
    """@end_missionary_section() — close a section opened by @missionary_section()."""
    qr = _section_qr_stack.pop() if _section_qr_stack else ""
    if not qr:
        return "\n\n"

    return (
        "\n\n```{=latex}\n"
        "\\end{minipage}\\hfill"
        "\\begin{minipage}[t]{0.20\\textwidth}\n"
        "\\vspace{0pt}\n"
        f"\\includegraphics[width=1in]{{{qr}}}\n"
        "\\end{minipage}\n"
        "```\n\n"
    )

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
