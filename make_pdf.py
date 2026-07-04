#!/usr/bin/env python3
"""
Generate a 1-page PDF resume from a tailored application.json using XeLaTeX.
Matches the base_resume.html design.
"""

import sys
import os
import json
import subprocess
import re
import shutil

def escape_tex(text: str) -> str:
    """Escape LaTeX special characters."""
    if not isinstance(text, str):
        return str(text)
    
    # Needs a bit more robust handling but this is standard for simple text
    replacements = {
        '\\': '\\textbackslash{}',
        '#': '\\#',
        '$': '\\$',
        '%': '\\%',
        '&': '\\&',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
        '^': '\\textasciicircum{}',
        '~': '\\textasciitilde{}',
        '<': '\\textless{}',
        '>': '\\textgreater{}',
    }
    
    # First protect backslashes (but we must avoid double-escaping later, so we do it char by char carefully)
    res = ""
    for char in text:
        res += replacements.get(char, char)
    return res

def tex_bold(text: str) -> str:
    """Convert **bold** markers to LaTeX \textbf{}."""
    parts = re.split(r"(\*\*.*?\*\*)", text)
    result = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            inner = escape_tex(part[2:-2])
            result.append(f"\\textbf{{{inner}}}")
        else:
            result.append(escape_tex(part))
    return "".join(result)

def build_experience_section(experiences):
    parts = []
    for exp in experiences:
        company = escape_tex(exp.get('company', ''))
        title = escape_tex(exp.get('title', ''))
        date = escape_tex(exp.get('date', ''))
        location = escape_tex(exp.get('location', ''))
        
        block = (
            f"\\noindent\n"
            f"\\textbf{{{company}}} \\hfill \\textit{{{title}}} \\hfill {date}\\\\\n"
            f"\\footnotesize\\textcolor{{darkgray}}{{{location}}}\\normalsize\n"
            f"\\vspace{{-4pt}}\n"
            f"\\begin{{itemize}}[itemsep=1pt, parsep=1pt, topsep=2pt]\n"
        )
        for highlight in exp.get("highlights", []):
            block += f"\\item {tex_bold(highlight)}\n"
        block += "\\end{itemize}\n\\vspace{2pt}\n"
        parts.append(block)
    return "\n".join(parts)

def build_skills_section(skills):
    lines = []
    for skill in skills:
        category = escape_tex(skill.get("category", ""))
        items = ", ".join(escape_tex(item) for item in skill.get("items", []))
        lines.append(f"\\item \\textbf{{{category}:}} {items}")
    return "\n".join(lines)

def build_education_section(education):
    lines = []
    for entry in education:
        degree = escape_tex(entry.get("degree", ""))
        institution = escape_tex(entry.get("institution", ""))
        years = escape_tex(entry.get("years", ""))
        location = escape_tex(entry.get("location", ""))
        
        lines.append(
            f"\\item \\textbf{{{degree}}}, {institution} \\hfill {years}\\\\\n"
            f"\\footnotesize\\textcolor{{darkgray}}{{{location}}}\\normalsize\n"
        )
    return "\n".join(lines)

def _get_page_count(pdf_path: str) -> int:
    result = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return 1

# We add multiple tighten levels. Since user wants "fully covered .. no big space left",
# we also define loosen levels if the page is too empty, but LaTeX naturally fills from top.
# We will focus on fitting 1 page. If it is 1 page but sparse, we might want to increase spacing.
# We'll just define sequential levels and pick the tightest one that fits on 1 page without being too tight,
# actually the opposite: we find the loosest one that fits on 1 page.
_LEVELS = [
    # Level 0 (Loosest)
    {
        r"itemsep=1pt": r"itemsep=3pt",
        r"parsep=1pt": r"parsep=2pt",
        r"\vspace{2pt}": r"\vspace{5pt}",
    },
    # Level 1 (Default)
    {
        # Base template untouched
    },
    # Level 2 (Tight)
    {
        r"itemsep=1pt": r"itemsep=0pt",
        r"parsep=1pt": r"parsep=0pt",
        r"\vspace{2pt}": r"\vspace{0pt}",
    },
    # Level 3 (Tighter)
    {
        r"itemsep=1pt": r"itemsep=0pt",
        r"parsep=1pt": r"parsep=0pt",
        r"\vspace{2pt}": r"\vspace{0pt}",
        r"\documentclass[9pt,letterpaper]{extarticle}": r"\documentclass[8pt,letterpaper]{extarticle}",
        r"top=0.35in, bottom=0.3in, left=0.25in, right=0.25in": r"top=0.3in, bottom=0.25in, left=0.2in, right=0.2in",
    },
    # Level 4 (Tightest)
    {
        r"itemsep=1pt": r"itemsep=0pt",
        r"parsep=1pt": r"parsep=0pt",
        r"\vspace{2pt}": r"\vspace{-1pt}",
        r"\documentclass[9pt,letterpaper]{extarticle}": r"\documentclass[8pt,letterpaper]{extarticle}",
        r"top=0.35in, bottom=0.3in, left=0.25in, right=0.25in": r"top=0.25in, bottom=0.2in, left=0.15in, right=0.15in",
    }
]

def compile_tex(tex_content: str, output_pdf_path: str):
    work_dir = os.path.dirname(output_pdf_path)
    tex_path = os.path.join(work_dir, "resume.tex")
    
    with open(tex_path, "w") as f:
        f.write(tex_content)
    
    subprocess.run(
        ["xelatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={work_dir}", tex_path],
        capture_output=True, text=True, timeout=60
    )
    # Run twice for references if needed, though usually not for simple resumes
    
    # Cleanup ALL temp files (including leftovers from earlier attempts)
    base = os.path.join(work_dir, "resume")
    for ext in [".tex", ".log", ".aux", ".out", ".synctex.gz", ".fdb_latexmk", ".fls", ".bbl", ".blg"]:
        try:
            if os.path.exists(base + ext):
                os.remove(base + ext)
        except:
            pass
            
    # Rename generated PDF to target if needed
    if os.path.exists(base + ".pdf") and base + ".pdf" != output_pdf_path:
        os.rename(base + ".pdf", output_pdf_path)

def generate_pdf(data: dict, template_path: str, output_pdf: str):
    with open(template_path, "r") as f:
        base_tex = f.read()
        
    p = data.get("personal_info", {})
    replacements = {
        "{{NAME}}": escape_tex(p.get("name", "")),
        "{{EMAIL}}": escape_tex(p.get("email", "")),
        "{{PHONE}}": escape_tex(p.get("phone", "")),
        "{{LOCATION}}": escape_tex(p.get("location", "")),
        "{{LINKEDIN}}": escape_tex(p.get("linkedin", "")),
        "{{SUMMARY}}": tex_bold(data.get("summary", "")),
        "{{EXPERIENCE_SECTION}}": build_experience_section(data.get("experience", [])),
        "{{SKILLS_SECTION}}": build_skills_section(data.get("skills", [])),
        "{{EDUCATION_SECTION}}": build_education_section(data.get("education", [])),
    }
    
    rendered_tex = base_tex
    for k, v in replacements.items():
        rendered_tex = rendered_tex.replace(k, v)
        
    best_level = None
    # Start from loosest to tightest. We want the loosest one that fits on 1 page exactly.
    for level, mods in enumerate(_LEVELS):
        tex_attempt = rendered_tex
        for old, new in mods.items():
            tex_attempt = tex_attempt.replace(old, new)
            
        compile_tex(tex_attempt, output_pdf)
        pages = _get_page_count(output_pdf)
        
        if pages == 1:
            best_level = level
            print(f"Success: Fits on 1 page at tighten level {level}.")
            break
        else:
            print(f"Level {level} resulted in {pages} pages, trying tighter...")
            
    if best_level is None:
        print("WARNING: Could not fit on 1 page even at maximum tightening.")
        
    print(f"PDF generated: {output_pdf}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 make_pdf.py <application.json> [output.pdf]", file=sys.stderr)
        sys.exit(1)
        
    json_path = sys.argv[1]
    if len(sys.argv) >= 3:
        pdf_path = sys.argv[2]
    else:
        work_dir = os.path.dirname(json_path)
        pdf_path = os.path.join(work_dir, 'SYED_ALAM_Resume.pdf')
        
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    template_path = os.path.join(os.path.dirname(__file__), "resume_template.tex")
    generate_pdf(data, template_path, pdf_path)

if __name__ == "__main__":
    main()
