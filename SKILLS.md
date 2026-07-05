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

## Core capabilities (v3)
1. **Full-JD retrieval** — fetches the real posting via browser (`navigate` → `get_page_text`) because
   job boards are JS-rendered; snippets aren't enough for ATS.
2. **Fit gate** — drops guaranteed auto-rejects (required degree/citizenship/ML-specialist the
   candidate lacks) and flags soft caveats (hybrid, W-2 contract, 8+ yrs).
3. **Dual-scorer keyword coverage** — targets ≥ 90% for literal ATS matchers (exact JD token
   spelling) AND reads naturally for AI/semantic screeners (evidence + outcome per keyword,
   no stuffing, ≤3 repeats per keyword, title mirroring in the summary).
4. **Bullet bank tailoring** — selects 16+6 bullets from tagged `bullet_bank.json`, orders by
   tier (top-3 rule: JD-primary tech first), and rewrites bullets impact-first while preserving
   each bullet's tech anchors. Core anchors (React, React Native, Vue, TypeScript, Node.js,
   Swift, Kotlin, .NET) always survive.
5. **Aggressive-but-plausible weaving** — truthful/adjacent keywords only; never fabricates
   employers, dates, metrics, or tools with zero adjacency (see AGENT.md boundary).
6. **Deterministic 1-page build** — `make_pdf.py` / `make_cover_letter.py` auto-tighten to exactly 1 page.
7. **Deterministic verification** — `verify_ats.py` extracts the real PDF text and proves: 1 page,
   16+6 bullets, authorization line, core anchors extractable, every claimed keyword actually in
   the PDF (catches ligature corruption + hallucinated coverage). Ship only on PASS.
8. **Bookkeeping** — `lambda.py finalize` writes to `data/applications.db`; dashboard stays in sync.

## Commands
```bash
python3 lambda.py check                                   # verify xelatex, pdfinfo, python
python3 lambda.py init                                    # create data/ + output/, apply schema
python3 make_pdf.py output/{slug}/application.json output/{slug}/SYED_ALAM_Resume.pdf
python3 verify_ats.py output/{slug}/application.json           # MUST pass before shipping
python3 make_cover_letter.py --body output/{slug}/cover_letter.txt --resume resume.json \
    --company "Company" --addressee "Hiring Team" --out output/{slug}/SYED_ALAM_CoverLetter.pdf
python3 lambda.py finalize ...                            # build PDFs + insert DB rows
python3 server.py                                         # dashboard at http://localhost:8000
```

## Batch recipe ("find fresh jobs + tailor")
1. Sweep the sources per [SCRAPING.md](SCRAPING.md)'s source matrix, filtered to the requested
   freshness and workplace, excluding already-applied companies (`output/` + `data/scan_history.tsv`):
   - `unified_job_scraper.py` (Indeed + LinkedIn + Google via JobSpy)
   - `builtin_scraper.py` (BuiltIn, plain HTTP, has posted-age)
   - Dice MCP connector (`search_jobs`, agent runtimes)
   - ATS APIs for watchlist companies (`data/portals.yml`) · RemoteOK/WWR/HN for extra coverage
   - Wellfound only via CloakBrowser visible mode (DataDome) — **discovery only: re-locate every
     Wellfound hit on its origin ATS/careers page and apply there; not found elsewhere → skip**
   For LinkedIn hits, fetch full JDs via the guest API (see AGENT.md Step 1) before triage.
2. For each shortlisted job: **fetch the full JD**, run the **fit gate**, then tailor (Steps 3–8 of
   AGENT.md). Drop bad fits; backfill from fresh results to hit the requested count.
3. Deliver a summary table (company, role, setup, salary, ATS %, resume path, caveats) + apply links.

## Companion skills (same repo)
- **Job scraping** — [SCRAPING.md](SCRAPING.md): tiered toolkit (JobSpy → ATS APIs → Scrapling →
  CloakBrowser → Crawl4AI), the `/opt/homebrew/bin/python3.12` interpreter rule, version-check
  protocol, `scripts/scrapers/unified_job_scraper.py`, `data/scan_history.tsv` dedup contract.
- **Live apply-form assistant** — [APPLY.md](APPLY.md): reads a form in the browser, pre-scans
  knock-out questions (work auth/sponsorship/degree/years), generates grounded copy-paste
  answers from `output/{slug}/` context, persists them to `application_answers.md`.

## Guardrails
- Truthfulness over coverage — never lie to hit 100%; leave real gaps in `missing_keywords`.
- Always verify bullet **order** (generation models mis-order); assemble by bank `id` deterministically.
- `verify_ats.py` PASS is a hard gate — no resume ships on FAIL.
- Core anchors (React, React Native, Vue, TypeScript, Node.js, Swift, Kotlin, .NET) never dropped.
- Resume is always exactly 1 page and full (~95–100%).
