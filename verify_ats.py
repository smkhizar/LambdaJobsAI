#!/usr/bin/env python3
"""
Deterministic post-build verification for tailored resumes.

Checks what an ATS parser actually sees — not what the generating model
believes it wrote:

  1. PDF is exactly 1 page (pdfinfo).
  2. Bullet counts match bullet_bank.json required_count per company.
  3. `authorization` present in personal_info.
  4. Core tech anchors (React, React Native, Vue, TypeScript, Node.js,
     Swift, Kotlin, .NET) all survive in the EXTRACTED PDF TEXT.
  5. Every `matched_keywords` entry from keyword_report.json is actually
     extractable from the PDF text (catches ligature/encoding corruption
     and keywords the model claimed but never wrote).
  6. always_include bank bullets are present in application.json.

Usage:
    python3 verify_ats.py output/{slug}/application.json [output/{slug}/SYED_ALAM_Resume.pdf]

Exit code 0 = pass, 1 = one or more failures.
"""

import json
import os
import re
import subprocess
import sys

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_PATH = os.path.join(REPO_DIR, "bullet_bank.json")

# Ligatures that PDF text extraction can emit instead of ASCII pairs.
LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl",
    "–": "-", "—": "-", "’": "'",
}


def normalize(text: str) -> str:
    for lig, ascii_form in LIGATURES.items():
        text = text.replace(lig, ascii_form)
    # Collapse all whitespace (PDF line breaks can split phrases).
    return re.sub(r"\s+", " ", text).lower()


def keyword_in_text(keyword: str, norm_text: str) -> bool:
    return normalize(keyword) in norm_text


def pdf_page_count(pdf_path: str) -> int:
    result = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return -1


def pdf_text(pdf_path: str) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"], capture_output=True, text=True
    )
    return result.stdout


def strip_bold(text: str) -> str:
    return text.replace("**", "")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    app_path = sys.argv[1]
    slug_dir = os.path.dirname(app_path)
    pdf_path = sys.argv[2] if len(sys.argv) >= 3 else os.path.join(slug_dir, "SYED_ALAM_Resume.pdf")
    report_path = os.path.join(slug_dir, "keyword_report.json")

    failures: list[str] = []
    warnings: list[str] = []

    with open(app_path) as f:
        app = json.load(f)
    with open(BANK_PATH) as f:
        bank = json.load(f)

    # --- 1. Page count ---------------------------------------------------
    if not os.path.exists(pdf_path):
        failures.append(f"PDF not found: {pdf_path}")
        norm = ""
    else:
        pages = pdf_page_count(pdf_path)
        if pages != 1:
            failures.append(f"PDF has {pages} pages (must be exactly 1)")
        norm = normalize(pdf_text(pdf_path))
        if len(norm) < 500:
            failures.append(
                "Extracted PDF text is suspiciously short "
                f"({len(norm)} chars) — ATS parsers may see an empty resume"
            )

    # --- 2. Bullet counts -------------------------------------------------
    experiences = app.get("experience", [])
    expected = [
        ("Pinestack", bank["pinestack"]["required_count"]),
        ("Symanto", bank["symanto"]["required_count"]),
    ]
    for (label, want), exp in zip(expected, experiences):
        got = len(exp.get("highlights", []))
        if got != want:
            failures.append(f"{label}: {got} bullets, expected {want}")
    if len(experiences) < len(expected):
        failures.append(f"Only {len(experiences)} experience entries, expected {len(expected)}")

    # --- 3. Authorization ---------------------------------------------------
    if "authorization" not in app.get("personal_info", {}):
        failures.append('personal_info.authorization missing ("US Work Authorized (No Sponsorship)")')

    # --- 4. Core anchors in extracted PDF text -----------------------------
    if norm:
        for anchor in bank["core_anchors"]:
            if not keyword_in_text(anchor, norm):
                failures.append(f"Core anchor not extractable from PDF: {anchor!r}")

    # --- 5. Claimed keywords actually extractable ---------------------------
    if norm and os.path.exists(report_path):
        with open(report_path) as f:
            report = json.load(f)
        claimed = report.get("matched_keywords") or report.get("jd_keywords_included") or []
        missing_claims = [kw for kw in claimed if not keyword_in_text(kw, norm)]
        for kw in missing_claims:
            failures.append(f"keyword_report claims {kw!r} matched, but it is NOT in the PDF text")
    elif not os.path.exists(report_path):
        warnings.append(f"No keyword_report.json in {slug_dir} — skipped claim verification")

    # --- 6. always_include bank bullets present -----------------------------
    app_text_norm = normalize(
        " ".join(
            strip_bold(h)
            for exp in experiences
            for h in exp.get("highlights", [])
        )
    )
    for company_key in ("pinestack", "symanto"):
        for bullet in bank[company_key]["bullets"]:
            if not bullet.get("always_include"):
                continue
            # A rewritten bullet still counts if all its anchors survive somewhere.
            anchors = bullet.get("anchors", [])
            missing = [a for a in anchors if not keyword_in_text(a, app_text_norm)]
            if missing:
                failures.append(
                    f"always_include bullet {bullet['id']!r}: anchors missing from "
                    f"experience bullets: {missing}"
                )

    # --- Report ----------------------------------------------------------
    for w in warnings:
        print(f"WARN  {w}")
    if failures:
        for msg in failures:
            print(f"FAIL  {msg}")
        print(f"\n{len(failures)} check(s) failed for {slug_dir}")
        sys.exit(1)
    print(f"PASS  all ATS checks passed for {slug_dir}")


if __name__ == "__main__":
    main()
