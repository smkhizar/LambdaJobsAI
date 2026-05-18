# LambdaJobsAI

Tailor a 1-page resume + optional 1-page cover letter for any job posting,
generate matching PDFs, save the application to SQLite, and browse everything
in a localhost dashboard.

The actual tailoring is done by **any AI agent** (Claude, GPT, Gemini, local
LLM …) following [AGENT.md](AGENT.md). This repo provides the deterministic
pieces around the AI:

- `make_pdf.py` — XeLaTeX → 1-page resume PDF (auto-tightens until it fits)
- `make_cover_letter.py` — XeLaTeX → 1-page cover letter PDF
- `lambda.py` — CLI: init DB, finalize application, list, prereq check
- `server.py` + `dashboard.html` — localhost dashboard at `http://localhost:8000`
- `resume.json` / `RESUME.md` — the master profile (never modified by tailoring)

## Prerequisites (Linux / macOS / Windows)

| Tool | Linux | macOS | Windows |
|------|-------|-------|---------|
| `xelatex` | `sudo apt install texlive-xetex` | `brew install --cask mactex-no-gui` | install MiKTeX or TeX Live; add to PATH |
| `pdfinfo` | `sudo apt install poppler-utils` | `brew install poppler` | install poppler-windows; add to PATH |
| Python 3.10+ | usually preinstalled | `brew install python` | from python.org or Microsoft Store |

Check everything at once:

```
python3 lambda.py check     # macOS / Linux
py     lambda.py check      # Windows
```

## First-time setup

```
python3 lambda.py init      # creates data/ and output/, applies schema
```

## Per-job workflow (AI agent)

The agent reads `AGENT.md`, then:

1. parses the job (URL, pasted JD, or natural language — any language),
2. writes `output/<slug>/application.json` + `cover_letter.txt` + `keyword_report.json` + `job_description.txt`,
3. calls `python3 lambda.py finalize ...` (one command — builds PDFs and inserts DB rows).

## Dashboard

```
python3 server.py
# http://localhost:8000
```

Search, filter, change status, delete, view PDFs inline.

## Files at a glance

```
.
├── AGENT.md                  # spec for any AI agent (read this first)
├── RESUME.md                 # human-readable master resume
├── resume.json               # source-of-truth structured resume
├── resume_template.tex       # XeLaTeX template for the resume PDF
├── cover_letter_template.tex # XeLaTeX template for the cover letter PDF
├── make_pdf.py               # tailored JSON → 1-page PDF
├── make_cover_letter.py      # cover letter text → 1-page PDF
├── lambda.py                 # CLI orchestrator (init / check / finalize / list)
├── server.py                 # dashboard HTTP server
├── dashboard.html            # dashboard UI (no build step)
├── base_resume.html          # web preview of the resume design
├── data/                     # SQLite DB (gitignored)
└── output/                   # per-company tailored files (gitignored)
```
