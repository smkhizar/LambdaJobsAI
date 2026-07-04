# LambdaJobsAI

Tailor a **1-page, ATS-optimized resume** (+ optional 1-page cover letter) for any job posting,
generate matching PDFs, save the application to SQLite, and browse everything in a localhost dashboard.

The tailoring is done by **any AI agent** (Claude, GPT, Gemini, Grok, local LLM) following
[AGENT.md](AGENT.md) — the rules — and [SKILLS.md](SKILLS.md) — what the skill does and its interface.
This repo provides the deterministic pieces around the AI:

- `make_pdf.py` — XeLaTeX → 1-page resume PDF (auto-tightens across spacing levels until it fits)
- `make_cover_letter.py` — XeLaTeX → 1-page cover letter PDF (matches the resume header)
- `lambda.py` — CLI: init DB, finalize application, list, prereq check
- `server.py` + `dashboard.html` — localhost dashboard at `http://localhost:8000`
- `resume.json` / `RESUME.md` / `master_resume.json` — the master profile (never modified by tailoring)

## How v3 tailoring works (the short version)
1. **Fetch the full JD** (browser, since job boards are JS-rendered) — not just a search snippet.
2. **Fit gate** — drop guaranteed auto-rejects (required degree/citizenship/ML the candidate lacks);
   flag soft caveats (hybrid, contract, high years).
3. **Dual-scorer keyword coverage** — ≥ 90% for literal ATS matchers (exact JD token spelling)
   AND natural evidence-based prose for AI/semantic screeners (no stuffing, title mirroring).
4. **Bullet bank** — select 16 Pinestack + 6 Symanto bullets from tagged `bullet_bank.json`,
   order by JD relevance (top-3 rule), rewrite impact-first; core anchors (React, React Native,
   Vue, TypeScript, Node.js, Swift, Kotlin, .NET) always survive.
5. **Aggressive-but-plausible** — weave truthful/adjacent keywords into the real bullets; never
   fabricate employers, dates, metrics, or tools with zero adjacency.
6. **1 page, always** — auto-fit; add `authorization` line.
7. **Verify deterministically** — `python3 verify_ats.py output/{slug}/application.json` extracts
   the real PDF text and gates shipping → **finalize** (DB + dashboard).

See [AGENT.md](AGENT.md) for the full protocol and the truthfulness boundary.

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

The agent reads `AGENT.md` + `SKILLS.md`, then:

1. parses the job and **fetches the full JD** (URL, pasted text, or natural language — any language),
2. runs the **fit gate**, tailors, and writes `output/<slug>/application.json` + `cover_letter.txt` +
   `keyword_report.json` + `job_description.txt`,
3. calls `python3 lambda.py finalize ...` (builds PDFs and inserts DB rows).

## Batch workflow ("find fresh jobs + tailor")

Search a jobs source for the candidate's angles (filtered by freshness/workplace, excluding
already-applied companies under `output/`), fetch each full JD, drop bad fits, tailor the rest, and
deliver a summary table with apply links, ATS coverage %, and caveats. See SKILLS.md → Batch recipe.

## Dashboard

```
python3 server.py
# http://localhost:8000
```

Search, filter, change status, delete, view PDFs inline.

## Files at a glance

```
.
├── AGENT.md                  # v3 rules for any AI agent (read this first)
├── bullet_bank.json          # tagged bullet pool (tailoring selects from this)
├── verify_ats.py             # deterministic post-build ATS verification (hard gate)
├── SKILLS.md                 # what the skill does + interface + batch recipe
├── RESUME.md                 # human-readable master resume
├── resume.json               # source-of-truth structured resume
├── master_resume.json        # extended master profile
├── resume_template.tex       # XeLaTeX template for the resume PDF
├── cover_letter_template.tex # XeLaTeX template for the cover letter PDF
├── make_pdf.py               # tailored JSON → 1-page PDF (auto-fit)
├── make_cover_letter.py      # cover letter text → 1-page PDF (auto-fit)
├── lambda.py                 # CLI orchestrator (init / check / finalize / list)
├── server.py                 # dashboard HTTP server
├── dashboard.html            # dashboard UI (no build step)
├── base_resume.html          # web preview of the resume design
├── data/                     # SQLite DB (gitignored)
└── output/                   # per-company tailored files (gitignored)
```

## Hermes integration
The `lambda-tailor` Hermes profile drives this repo. Its persona/rules live in the profile's
`SOUL.md` and reference this repo's `AGENT.md` as the source of truth. See [hermes.md](hermes.md).
