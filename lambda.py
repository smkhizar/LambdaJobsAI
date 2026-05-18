#!/usr/bin/env python3
"""LambdaJobsAI orchestrator — one CLI to finalize a tailored application.

Typical usage (after an AI agent has produced the tailored JSON + cover letter):

    python3 lambda.py finalize \\
        --tailored output/cohere-health/application.json \\
        --cover    output/cohere-health/cover_letter.txt \\
        --company  "Cohere Health" \\
        --title    "Senior Frontend Engineer" \\
        --url      "https://example.com/job/123" \\
        --jd-file  output/cohere-health/job_description.txt \\
        --keywords output/cohere-health/keyword_report.json \\
        --runtime  "claude-opus-4-7"

This single command will:
  1. ensure data/applications.db + output/ exist (schema auto-applied)
  2. run make_pdf.py to produce the 1-page resume PDF
  3. run make_cover_letter.py to produce the 1-page cover letter PDF
  4. insert/update companies, applications, generated_files rows

Other subcommands:
    python3 lambda.py init             # create data/ + DB + output/
    python3 lambda.py check            # check prerequisites (xelatex, etc.)
    python3 lambda.py list             # list applications in DB
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "applications.db"
OUTPUT_DIR = ROOT / "output"
RESUME_JSON = ROOT / "resume.json"
MAKE_PDF = ROOT / "make_pdf.py"
MAKE_COVER = ROOT / "make_cover_letter.py"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT UNIQUE NOT NULL,
  slug       TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id             INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  job_title              TEXT NOT NULL DEFAULT '',
  job_url                TEXT DEFAULT '',
  job_description        TEXT DEFAULT '',
  tailored_resume_json   TEXT DEFAULT '',
  llm_runtime            TEXT DEFAULT '',
  status                 TEXT DEFAULT 'generated',
  tailored               INTEGER DEFAULT 1,
  cover_letter_generated INTEGER DEFAULT 1,
  cover_letter_content   TEXT DEFAULT '',
  keyword_report         TEXT DEFAULT '{}',
  created_at             TEXT NOT NULL,
  updated_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_files (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  file_type      TEXT NOT NULL,
  file_path      TEXT NOT NULL,
  created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company_id);
CREATE INDEX IF NOT EXISTS idx_files_app ON generated_files(application_id);
"""


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return s.strip("-")


def open_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def rel_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


# -----------------------------------------------------------------------------
# Subcommands
# -----------------------------------------------------------------------------


def cmd_init(_: argparse.Namespace) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open_db() as conn:
        conn.commit()
    print(f"Initialized:\n  DB:     {DB_PATH}\n  Output: {OUTPUT_DIR}")
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    """Verify prerequisites. Useful for any AI agent before generating."""
    problems: list[str] = []

    def need(binary: str, hint: str) -> None:
        if not shutil.which(binary):
            problems.append(f"missing `{binary}` — {hint}")
        else:
            print(f"  ✓ {binary}: {shutil.which(binary)}")

    print("Prerequisites:")
    need("xelatex", "install via TeX Live / MacTeX / `brew install --cask mactex-no-gui`")
    need("pdfinfo", "install poppler (e.g. `brew install poppler`)")
    need("python3", "Python 3.10+")

    for required in (RESUME_JSON, MAKE_PDF, MAKE_COVER):
        if not required.exists():
            problems.append(f"missing file: {required}")
        else:
            print(f"  ✓ {required.name}")

    if problems:
        print("\nProblems detected:")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("\nAll good.")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    if not DB_PATH.exists():
        print("(no DB yet — run `python3 lambda.py init` first)")
        return 0
    with open_db() as conn:
        rows = conn.execute(
            """
            SELECT a.id, c.name AS company, a.job_title, a.status,
                   a.llm_runtime, a.created_at
              FROM applications a
              JOIN companies c ON c.id = a.company_id
             ORDER BY a.created_at DESC
            """
        ).fetchall()
    if not rows:
        print("(no applications)")
        return 0
    for r in rows:
        print(f"  #{r['id']:>3}  {r['created_at'][:10]}  "
              f"{r['company']:<28} {r['job_title']:<35} "
              f"[{r['status']:<10}] ({r['llm_runtime']})")
    return 0


# -----------------------------------------------------------------------------
# Finalize (the main flow)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class FinalizeArgs:
    tailored: Path
    cover: Path | None
    company: str
    title: str
    url: str
    jd_text: str
    keywords: dict
    runtime: str
    addressee: str
    out_dir: Path | None
    skip_pdf: bool


def _read_text_or_file(value: str | None) -> str:
    if not value:
        return ""
    p = Path(value)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return value


def _safe_job_title(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") or "Role"


def _generate_resume_pdf(tailored_json: Path, out_pdf: Path) -> Path:
    subprocess.run(
        ["python3", str(MAKE_PDF), str(tailored_json), str(out_pdf)],
        cwd=str(ROOT),
        check=True,
    )
    return out_pdf


def _generate_cover_pdf(
    *, body_path: Path, out_pdf: Path, company: str, addressee: str
) -> Path:
    subprocess.run(
        [
            "python3", str(MAKE_COVER),
            "--body", str(body_path),
            "--resume", str(RESUME_JSON),
            "--company", company,
            "--addressee", addressee,
            "--out", str(out_pdf),
        ],
        cwd=str(ROOT),
        check=True,
    )
    return out_pdf


def _upsert_company(conn: sqlite3.Connection, name: str, slug: str) -> int:
    row = conn.execute(
        "SELECT id FROM companies WHERE slug = ?", (slug,)
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO companies (name, slug, created_at) VALUES (?, ?, ?)",
        (name, slug, _now()),
    )
    return int(cur.lastrowid)


def _insert_application(
    conn: sqlite3.Connection,
    *,
    company_id: int,
    args: FinalizeArgs,
    tailored_json_text: str,
    cover_letter_text: str,
) -> int:
    now = _now()
    cur = conn.execute(
        """
        INSERT INTO applications (
          company_id, job_title, job_url, job_description,
          tailored_resume_json, llm_runtime, status,
          tailored, cover_letter_generated, cover_letter_content,
          keyword_report, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'generated', 1, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            args.title,
            args.url,
            args.jd_text,
            tailored_json_text,
            args.runtime,
            1 if cover_letter_text else 0,
            cover_letter_text,
            json.dumps(args.keywords, ensure_ascii=False),
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def _insert_file(
    conn: sqlite3.Connection, *, application_id: int, file_type: str, file_path: Path
) -> None:
    conn.execute(
        "INSERT INTO generated_files (application_id, file_type, file_path, created_at) "
        "VALUES (?, ?, ?, ?)",
        (application_id, file_type, rel_to_root(file_path), _now()),
    )


def cmd_finalize(ns: argparse.Namespace) -> int:
    if not RESUME_JSON.exists():
        print(f"resume.json missing at {RESUME_JSON}", file=sys.stderr)
        return 2

    keywords = {}
    if ns.keywords:
        kw_path = Path(ns.keywords)
        if kw_path.exists():
            keywords = json.loads(kw_path.read_text(encoding="utf-8"))
        else:
            try:
                keywords = json.loads(ns.keywords)
            except json.JSONDecodeError:
                keywords = {}

    args = FinalizeArgs(
        tailored=Path(ns.tailored).resolve(),
        cover=Path(ns.cover).resolve() if ns.cover else None,
        company=ns.company,
        title=ns.title,
        url=ns.url or "",
        jd_text=_read_text_or_file(ns.jd_file),
        keywords=keywords,
        runtime=ns.runtime or "",
        addressee=ns.addressee or "Hiring Team",
        out_dir=Path(ns.out_dir).resolve() if ns.out_dir else None,
        skip_pdf=bool(ns.skip_pdf),
    )

    if not args.tailored.exists():
        print(f"Tailored JSON not found: {args.tailored}", file=sys.stderr)
        return 2

    slug = slugify(args.company)
    out_dir = args.out_dir or (OUTPUT_DIR / slug)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy/move tailored JSON into canonical location if it isn't already.
    canonical_json = out_dir / "application.json"
    if args.tailored.resolve() != canonical_json.resolve():
        canonical_json.write_text(
            args.tailored.read_text(encoding="utf-8"), encoding="utf-8"
        )

    tailored_text = canonical_json.read_text(encoding="utf-8")

    safe_title = _safe_job_title(args.title)
    resume_pdf = out_dir / f"SYED_ALAM_{safe_title}_Resume.pdf"
    cover_pdf = out_dir / f"SYED_ALAM_{safe_title}_CoverLetter.pdf"
    cover_txt: Path | None = None
    cover_text = ""

    if args.cover and args.cover.exists():
        cover_text = args.cover.read_text(encoding="utf-8")
        cover_txt = out_dir / "cover_letter.txt"
        if args.cover.resolve() != cover_txt.resolve():
            cover_txt.write_text(cover_text, encoding="utf-8")

    # Save keyword report alongside outputs (handy for the dashboard / agent recall)
    if keywords:
        (out_dir / "keyword_report.json").write_text(
            json.dumps(keywords, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if not args.skip_pdf:
        _generate_resume_pdf(canonical_json, resume_pdf)
        if cover_txt:
            _generate_cover_pdf(
                body_path=cover_txt,
                out_pdf=cover_pdf,
                company=args.company,
                addressee=args.addressee,
            )

    with open_db() as conn:
        company_id = _upsert_company(conn, args.company, slug)
        app_id = _insert_application(
            conn,
            company_id=company_id,
            args=args,
            tailored_json_text=tailored_text,
            cover_letter_text=cover_text,
        )
        _insert_file(
            conn, application_id=app_id,
            file_type="tailored_json", file_path=canonical_json,
        )
        if resume_pdf.exists():
            _insert_file(
                conn, application_id=app_id,
                file_type="resume_pdf", file_path=resume_pdf,
            )
        if cover_pdf.exists():
            _insert_file(
                conn, application_id=app_id,
                file_type="cover_letter_pdf", file_path=cover_pdf,
            )
        conn.commit()

    print(f"Finalized application #{app_id}:")
    print(f"  Company:  {args.company}")
    print(f"  Title:    {args.title}")
    print(f"  Resume:   {resume_pdf if resume_pdf.exists() else '(skipped)'}")
    print(f"  Cover:    {cover_pdf if cover_pdf.exists() else '(none)'}")
    print(f"  Out dir:  {out_dir}")
    return 0


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="lambda.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create data/, output/, and the SQLite schema"
                   ).set_defaults(func=cmd_init)

    sub.add_parser("check", help="check prerequisites (xelatex, pdfinfo, files)"
                   ).set_defaults(func=cmd_check)

    sub.add_parser("list", help="list applications in the DB"
                   ).set_defaults(func=cmd_list)

    f = sub.add_parser("finalize",
                       help="register a tailored application, generate PDFs, save to DB")
    f.add_argument("--tailored", required=True, help="path to application.json")
    f.add_argument("--cover", default=None, help="path to cover_letter.txt (optional)")
    f.add_argument("--company", required=True, help="company name (never 'Unknown')")
    f.add_argument("--title", required=True, help="job title")
    f.add_argument("--url", default="", help="job posting URL")
    f.add_argument("--jd-file", default="", help="path to job description text file")
    f.add_argument("--keywords", default="", help="keyword_report.json path or inline JSON")
    f.add_argument("--runtime", default="", help="LLM runtime label (e.g. claude-opus-4-7)")
    f.add_argument("--addressee", default="Hiring Team", help="cover letter salutation")
    f.add_argument("--out-dir", default=None, help="override output directory")
    f.add_argument("--skip-pdf", action="store_true", help="don't build PDFs (DB only)")
    f.set_defaults(func=cmd_finalize)

    return ap


def main() -> int:
    ap = build_parser()
    ns = ap.parse_args()
    return int(ns.func(ns) or 0)


if __name__ == "__main__":
    sys.exit(main())
