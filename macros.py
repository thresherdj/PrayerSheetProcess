"""Project-local macros for TestMDs documents."""


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
