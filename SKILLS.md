# SKILLS.md — LambdaJobsAI Resume Tailor

A description of the **resume-tailoring skill** this repo implements, for any agent runtime
(Hermes, Claude Code, Cowork, GPT, Gemini, local). Pair this with [AGENT.md](AGENT.md), which holds
the step-by-step rules. This file is the "what it does / when to use it / interface" summary.

## Skill name
`lambdajobs-resume-tailor`

## What it does
Turns a job posting into a **1-page, ATS-optimized tailored resume PDF** (and optional matching
cover letter) grounded in the candidate's real history, then records the application to SQLite and a
localhost dashboard.

## When to trigger
- The user pastes a **job URL** or **job description**.
- The user says "tailor my resume for …", "apply to …", "make a resume/cover letter for …".
- A batch ask: "find fresh jobs and tailor resumes" (see the Batch recipe below).

## Inputs
- A job: URL, pasted JD text, or a natural-language description (any language).
- Master data (read-only): `resume.json` (source of truth), `RESUME.md`, `master_resume.json`.

## Outputs (per job, in `output/{company-slug}/`)
| File | Purpose |
|------|---------|
| `application.json` | tailored resume data (schema of `resume.json` + `authorization`) |
| `SYED_ALAM_Resume.pdf` | 1-page resume PDF |
| `cover_letter.txt` → `SYED_ALAM_CoverLetter.pdf` | optional 1-page cover letter |
| `keyword_report.json` | company, title, url, ATS coverage %, matched + missing keywords, caveat |
| `job_description.txt` | the full JD that was fetched (provenance) |

## Core capabilities (v2)
1. **Full-JD retrieval** — fetches the real posting via browser (`navigate` → `get_page_text`) because
   job boards are JS-rendered; snippets aren't enough for ATS.
2. **Fit gate** — drops guaranteed auto-rejects (required degree/citizenship/ML-specialist the
   candidate lacks) and flags soft caveats (hybrid, W-2 contract, 8+ yrs).
3. **Keyword coverage** — targets ≥ 90% of the JD's keyword set; reports matched vs missing.
4. **Aggressive-but-plausible tailoring** — weaves truthful/adjacent keywords into real bullets;
   never fabricates employers, dates, metrics, or tools with zero adjacency (see AGENT.md boundary).
5. **Deterministic 1-page build** — `make_pdf.py` / `make_cover_letter.py` auto-tighten to exactly 1 page.
6. **Verification** — confirms 1 page, 16+6 bullets, correct bullet ordering, coverage, no fabrication.
7. **Bookkeeping** — `lambda.py finalize` writes to `data/applications.db`; dashboard stays in sync.

## Commands
```bash
python3 lambda.py check                                   # verify xelatex, pdfinfo, python
python3 lambda.py init                                    # create data/ + output/, apply schema
python3 make_pdf.py output/{slug}/application.json output/{slug}/SYED_ALAM_Resume.pdf
python3 make_cover_letter.py --body output/{slug}/cover_letter.txt --resume resume.json \
    --company "Company" --addressee "Hiring Team" --out output/{slug}/SYED_ALAM_CoverLetter.pdf
python3 lambda.py finalize ...                            # build PDFs + insert DB rows
python3 server.py                                         # dashboard at http://localhost:8000
```

## Batch recipe ("find fresh jobs + tailor")
1. Search a jobs source (e.g. Dice connector) for the candidate's angles, filtered to the requested
   freshness (e.g. posted ≤ 24h) and workplace (e.g. remote), excluding already-applied companies
   under `output/`.
2. For each shortlisted job: **fetch the full JD**, run the **fit gate**, then tailor (Steps 3–8 of
   AGENT.md). Drop bad fits; backfill from fresh results to hit the requested count.
3. Deliver a summary table (company, role, setup, salary, ATS %, resume path, caveats) + apply links.

## Guardrails
- Truthfulness over coverage — never lie to hit 100%; leave real gaps in `missing_keywords`.
- Always verify bullet **order** (generation models mis-order); prefer deterministic assembly.
- Resume is always exactly 1 page and full (~95–100%).
