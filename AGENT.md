# LambdaJobsAI — Agent Instructions (v2)

> Source of truth for **any** AI agent (Claude, GPT, Gemini, Grok, local LLM) that tailors
> Khizar's resume. Read this file **before every task**. Last updated: 2026-07 (v2).

Working directory: `/Users/khizar/Desktop/Personal/LambdaJobsAI`

## What This Project Does
Given a job (URL, pasted JD, or natural-language ask) → produce a **1-page, ATS-optimized,
tailored resume PDF** (+ optional 1-page cover letter) → save to SQLite → browse in the dashboard.

The AI does the judgement (keyword strategy, tailoring). The repo does the deterministic parts
(`make_pdf.py`, `make_cover_letter.py`, `lambda.py`, dashboard).

---

## Core Rules (NEVER break)
1. **Ground everything in `resume.json`.** Never invent employers, dates, or metrics. Never claim a
   tool the candidate has *zero* adjacency to (see Truthfulness Boundary).
2. **1-Page Rule.** The resume PDF MUST be exactly 1 page. `make_pdf.py` auto-tightens across spacing
   levels 0→4 to fit; you do not hand-shrink fonts. Aim for a full page (~95–100% fill), not sparse.
3. **Bullet counts fixed:** Pinestack = **16** highlights, Symanto = **6** highlights. Always. You may
   reorder and weave keywords; never drop or add whole bullets.
4. **Authorization line:** add `"authorization": "US Work Authorized (No Sponsorship)"` to
   `personal_info` on every tailored `application.json`.
5. **Company name never "Unknown."** Extract it from the JD or URL. Never ask the user for title/company.
6. **Update the database** (`python3 lambda.py finalize ...`) after every generation.

---

## Step 1 — Parse the job AND fetch the FULL description
Extract: company, exact title, seniority, workplace (remote/hybrid/onsite), salary, required years,
core responsibilities, required + preferred tech, domain, and any **hard gates**.

**Always tailor against the FULL JD, not a search-result snippet.** Dice/most boards are
JavaScript-rendered — a plain fetch returns a shell. Use the browser tools
(`navigate` → `get_page_text`) to read the real posting, including the parsed **skill-tag list**,
"Required Qualifications," and "Preferred Qualifications." Those tags are what ATS/AI scorers weight.

Determine the **role angle** (see table below) to decide what to lead with.

## Step 2 — Fit gate (drop or flag hard disqualifiers)
Before tailoring, check for auto-reject gates the candidate cannot truthfully meet:
- A **required** degree in a specific field he lacks (e.g. "Master's in AI/Robotics required").
- **US citizenship** required (he is work-authorized, no sponsorship — confirm before applying).
- Required years **far** above his ~6–7 (a 1–2 yr gap is fine; 10+ hard-required is a stretch).
- A core stack he genuinely lacks (e.g. required Python/PyTorch **ML model development**).
- Staffing/W-2-contract when the user wants direct-hire; **onsite** when the user wants remote.

If a gate is disqualifying → **drop it and say why** (don't ship a guaranteed auto-reject).
If it's a soft caveat → **keep it but flag the caveat** so the user can self-select.

## Step 3 — Keyword coverage protocol (target ≥ 90%)
1. Build the JD keyword set from the skill tags + required/preferred sections (languages, frameworks,
   cloud, tools, testing, concepts, domain terms).
2. Compute coverage: a keyword counts as matched if it appears **anywhere** in the tailored resume
   text (summary, bullets, OR skills).
3. Close gaps **aggressively but plausibly** (see boundary). Weave truthful/adjacent keywords into the
   real bullets — not just the skills list — and reorder skills keyword-forward.
4. Leave genuinely-absent tools **out**, honestly. Record them in `keyword_report.json` as
   `missing_keywords`. Do not fabricate to hit 100%.

## Step 4 — Tailor the data
- **Summary:** the ONLY section fully rewritten per JD. 2–3 sentences, lead with the target title +
  the JD's top keywords + years. Unique per job — never copy-paste.
- **Experience bullets:** keep them grounded in the base 16/6. **Reorder** by JD relevance (most
  relevant first) and apply **small, truthful keyword weaves** (see boundary). Do not paraphrase into
  something unrecognizable, merge, or split.
- **Skills:** reorder categories and items to push JD keywords to the front; **add** adjacent-truthful
  keywords the JD asks for. Never remove real base skills.

## Step 5 — Write intermediate files
`output/{company-slug}/` (slug = lowercase, hyphens):
- `application.json` — tailored resume (same schema as `resume.json` + `authorization`)
- `cover_letter.txt` — plain text; blank line = new paragraph; `**bold**` supported
- `keyword_report.json` — `{ company, title, job_url, workplace, ats_keyword_coverage_pct, matched_keywords, missing_keywords, caveat }`
- `job_description.txt` — the full JD you fetched (provenance)

## Step 6 — Build the PDFs
```bash
python3 make_pdf.py output/{slug}/application.json output/{slug}/SYED_ALAM_Resume.pdf
python3 make_cover_letter.py --body output/{slug}/cover_letter.txt --resume resume.json \
    --company "Company Name" --addressee "Hiring Team" --out output/{slug}/SYED_ALAM_CoverLetter.pdf
```
Both scripts auto-tighten to exactly 1 page.

## Step 7 — Verify (do not skip)
- PDF is **exactly 1 page** (`pdfinfo | grep Pages`).
- 16 Pinestack + 6 Symanto bullets present; `authorization` present.
- **Bullet ordering actually matches your intended order** (a known failure mode: an LLM emits the
  right bullets in the wrong order — assemble deterministically or diff before shipping).
- Coverage ≥ target; no fabricated tool slipped into a bullet.

## Step 8 — Save to the database
```bash
python3 lambda.py finalize ...   # inserts company/application/generated_files rows; keeps dashboard in sync
```

---

## Truthfulness Boundary (the heart of v2)
**Allowed (aggressive but plausible)** — weave in keywords the candidate can defend in an interview
because they're genuinely adjacent to real work:
- GraphQL, microservices, Next.js, Redux, Jest/Playwright (adjacent to his React/TS/Node/Cypress work)
- ASP.NET Core, C#, EF Core (adjacent to his .NET/Angular work at Symanto)
- GitHub Actions, AWS (adjacent to his GitLab CI / Azure / Docker work)
- PostgreSQL, MongoDB, Apache Kafka (adjacent to his SQL/NoSQL + MQTT/RabbitMQ work)
- LLM integration, RAG, prompt engineering, GitHub Copilot (adjacent to his OpenAI/Gemini work)

**Forbidden (fabrication)** — never claim these unless they're genuinely in his history:
- A different employer, title, date, or invented metric.
- Deep specialist tools with no adjacency: Oracle, Selenium, **PyTorch/TensorFlow/ML model training**,
  production Kubernetes cluster ownership, GCP depth, Salesforce/Workday admin, security clearances.
- Any "required" gate he can't meet (citizenship, a specific required degree).

If it wouldn't survive a hiring manager asking "tell me about that" — don't write it.

---

## Tailoring Knowledge — lead with, by role angle
| Role angle | Lead with |
|-----------|-----------|
| Frontend (React/TS) | React, TypeScript, component libraries, performance, accessibility (WCAG), state mgmt |
| Full Stack | React + Node.js REST/GraphQL, microservices, SQL/NoSQL, Azure/AWS, CI/CD |
| Mobile / React Native | React Native, Capacitor, native Swift/Kotlin modules, App Store / Play Store |
| Backend / API | Node.js, .NET (C#/ASP.NET Core), REST APIs, auth (OAuth/JWT), cloud |
| AI / Product | OpenAI/Gemini LLM integration, RAG, prompt engineering, agent workflows, reliability |
| .NET / C# | C#, .NET, ASP.NET Core, EF Core, PostgreSQL, plus React frontend |
| Real-time / Distributed | MQTT, Kafka, RabbitMQ, WebSockets, telemetry, event-driven, observability |

## Optional — multi-model orchestration
For batches, a useful division of labor: a strong reasoning model drafts per-job **strategy**
(summary + keyword plan + bullet order); a fast model **generates** the JSON; then **verify
deterministically** (assemble bullets by index; recompute coverage). Always verify — generation
models frequently mis-order bullets.

## Master data (never modified by tailoring)
`resume.json` (source of truth) · `RESUME.md` (human-readable) · `master_resume.json` (extended).
