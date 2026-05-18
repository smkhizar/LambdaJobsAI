#!/usr/bin/env python3
"""Generate a 1-page PDF cover letter from a plain-text body using XeLaTeX.

Usage:
    python3 make_cover_letter.py \\
        --body output/<company>/cover_letter.txt \\
        --resume resume.json \\
        --company "Company Name" \\
        [--addressee "Hiring Manager"] \\
        [--out output/<company>/SYED_ALAM_<Title>_CoverLetter.pdf]

The body file is plain text. Blank lines start a new paragraph.
The header (name, contact info) is pulled from resume.json so it
visually matches the resume.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


# ---- LaTeX escaping (shared style with make_pdf.py) ----------------------

_TEX_REPLACEMENTS = {
    "\\": "\\textbackslash{}",
    "#": "\\#",
    "$": "\\$",
    "%": "\\%",
    "&": "\\&",
    "_": "\\_",
    "{": "\\{",
    "}": "\\}",
    "^": "\\textasciicircum{}",
    "~": "\\textasciitilde{}",
    "<": "\\textless{}",
    ">": "\\textgreater{}",
}


def escape_tex(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return "".join(_TEX_REPLACEMENTS.get(c, c) for c in text)


def tex_bold(text: str) -> str:
    """Convert **bold** markers to \\textbf{}, escaping the rest."""
    parts = re.split(r"(\*\*.*?\*\*)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            out.append(f"\\textbf{{{escape_tex(part[2:-2])}}}")
        else:
            out.append(escape_tex(part))
    return "".join(out)


# ---- Body rendering -------------------------------------------------------


def render_body(body_text: str) -> str:
    """Plain text → LaTeX paragraphs. Blank line = paragraph break."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body_text.strip()) if p.strip()]
    rendered = []
    for p in paragraphs:
        # Collapse internal newlines to spaces; preserve **bold** markers.
        single_line = " ".join(line.strip() for line in p.splitlines())
        rendered.append(tex_bold(single_line))
    return "\n\n".join(rendered)


# ---- Compile --------------------------------------------------------------


def compile_tex(tex: str, output_pdf: Path) -> int:
    """Compile tex string to output_pdf via xelatex. Returns page count.

    Raises RuntimeError if xelatex fails to produce a PDF.
    """
    work_dir = output_pdf.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    tex_path = work_dir / "cover_letter.tex"
    tex_path.write_text(tex, encoding="utf-8")

    result = subprocess.run(
        [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={work_dir}",
            str(tex_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    base = work_dir / "cover_letter"
    produced = base.with_suffix(".pdf")

    if not produced.exists():
        log_tail = "\n".join(result.stdout.splitlines()[-25:])
        raise RuntimeError(
            f"xelatex failed for cover letter (exit {result.returncode}).\n"
            f"--- last log lines ---\n{log_tail}"
        )

    if produced != output_pdf:
        produced.replace(output_pdf)

    for ext in (".tex", ".log", ".aux", ".out"):
        p = base.with_suffix(ext)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    return _page_count(output_pdf)


def _page_count(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return 1


# ---- Tightening levels (mirror make_pdf.py spirit) ------------------------


@dataclass(frozen=True)
class TightenLevel:
    geometry: str
    docclass: str
    parskip: str


_LEVELS: tuple[TightenLevel, ...] = (
    TightenLevel(
        geometry="top=0.9in, bottom=0.9in, left=0.9in, right=0.9in",
        docclass="11pt",
        parskip="8pt",
    ),
    TightenLevel(
        geometry="top=0.75in, bottom=0.75in, left=0.85in, right=0.85in",
        docclass="11pt",
        parskip="6pt",
    ),
    TightenLevel(
        geometry="top=0.6in, bottom=0.6in, left=0.8in, right=0.8in",
        docclass="10pt",
        parskip="5pt",
    ),
    TightenLevel(
        geometry="top=0.5in, bottom=0.5in, left=0.7in, right=0.7in",
        docclass="10pt",
        parskip="4pt",
    ),
)


def _apply_level(template: str, level: TightenLevel) -> str:
    return (
        template.replace(
            "top=0.9in, bottom=0.9in, left=0.9in, right=0.9in",
            level.geometry,
        )
        .replace(r"\documentclass[11pt,letterpaper]{extarticle}",
                 fr"\documentclass[{level.docclass},letterpaper]{{extarticle}}")
        .replace(r"\setlength{\parskip}{8pt}",
                 fr"\setlength{{\parskip}}{{{level.parskip}}}")
    )


# ---- Main -----------------------------------------------------------------


def build(
    *,
    body_text: str,
    resume: dict,
    company: str,
    addressee: str,
    template: str,
    output_pdf: Path,
    today: str | None = None,
) -> Path:
    p = resume.get("personal_info", {})
    company_block_lines: Iterable[str] = (
        [escape_tex(addressee)] if addressee else []
    )
    company_block = (
        "\\\\\n".join([*company_block_lines, escape_tex(company)])
        if company
        else escape_tex(addressee or "")
    )

    replacements = {
        "{{NAME}}": escape_tex(p.get("name", "")),
        "{{EMAIL}}": escape_tex(p.get("email", "")),
        "{{PHONE}}": escape_tex(p.get("phone", "")),
        "{{LOCATION}}": escape_tex(p.get("location", "")),
        "{{LINKEDIN}}": escape_tex(p.get("linkedin", "")),
        "{{DATE}}": escape_tex(today or date.today().strftime("%B %d, %Y")),
        "{{COMPANY_BLOCK}}": company_block,
        "{{BODY}}": render_body(body_text),
    }

    rendered = template
    for k, v in replacements.items():
        rendered = rendered.replace(k, v)

    for level_idx, level in enumerate(_LEVELS):
        tex = _apply_level(rendered, level)
        pages = compile_tex(tex, output_pdf)
        if pages == 1:
            print(f"Cover letter fits on 1 page at level {level_idx}.")
            return output_pdf
        print(f"Level {level_idx}: {pages} pages, tightening…")

    print("WARNING: cover letter could not be forced to 1 page; using tightest level.")
    return output_pdf


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a 1-page PDF cover letter.")
    ap.add_argument("--body", required=True, help="Path to cover letter plain-text body.")
    ap.add_argument("--resume", required=True, help="Path to resume.json (for header).")
    ap.add_argument("--company", required=True, help="Company name (addressed in letter).")
    ap.add_argument("--addressee", default="Hiring Team", help="Salutation line.")
    ap.add_argument("--out", required=True, help="Output PDF path.")
    ap.add_argument("--date", default=None, help="Override date string.")
    args = ap.parse_args()

    body_text = Path(args.body).read_text(encoding="utf-8")
    resume = json.loads(Path(args.resume).read_text(encoding="utf-8"))
    template_path = Path(__file__).parent / "cover_letter_template.tex"
    template = template_path.read_text(encoding="utf-8")

    out_pdf = Path(args.out).resolve()
    build(
        body_text=body_text,
        resume=resume,
        company=args.company,
        addressee=args.addressee,
        template=template,
        output_pdf=out_pdf,
        today=args.date,
    )
    print(f"Cover letter PDF: {out_pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
