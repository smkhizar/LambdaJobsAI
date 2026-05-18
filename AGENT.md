# LambdaJobsAI — Agent Instructions

Working directory: `/home/khizar/Desktop/Projects/LambdaJobsAI`

## What This Project Does
Takes a job URL and/or job description → generates a tailored 1-page PDF resume + cover letter → saves to SQLite database → files viewable in dashboard.

---

## Quick Start (for any AI agent)

```
Read: AGENT.md, RESUME.md, resume.json

Tailor my resume for: [PASTE JOB URL OR DESCRIPTION]
```

Execute all 5 steps below in order.

---

## Core Rules (never break)
1. **Never invent** skills, experience, or metrics not in `resume.json`.
2. **1-Page Rule**: Resume PDF MUST fit on exactly 1 page. Remove 1-2 least relevant bullets only if needed.
3. **Company name must never be "Unknown"** — extract it from the JD or URL.
4. **Update database** after every generation.
5. **Extract job title and company** automatically from the JD — never ask the user.

---

## Step 1: Parse the Job

From the URL or description, extract:
- Company name (required — never "Unknown")
- Job title
- Seniority level
- Core responsibilities
- Required technologies and skills
- Domain/product area
- Remote/hybrid/onsite
- Salary if mentioned

Determine role angle: Senior Frontend, Full Stack, Mobile/React Native, AI/Product, or Real-time/IoT.

---

## Step 2: Tailor Resume Data

1. Read `RESUME.md` and `resume.json` (`resume.json` is the source of truth for all data).
2. Generate tailored resume JSON with:
   - **Summary**: Rewrite completely for the exact role. 2-3 sentences, concise.
   - **Experience**: Reorder bullets by relevance to JD. Rephrase using JD language where truthful. Remove 1-2 least relevant bullets only if needed for 1-page fit.
   - **Skills**: Group by category. Push JD keywords to front. Add missing keywords only if the user possesses them based on adjacent experience — never fabricate.
3. Generate cover letter answering:
   1. Why this role fits the user.
   2. Why the user is relevant to the company.
   3. What the user has done that proves the fit (real examples only).
   4. Why the user is worth talking to.
   - Tone: Confident, direct, specific. 3 short paragraphs. No corporate filler ("passionate", "results-driven", "synergy").
4. Generate keyword match report: `{ matched_keywords: [...], missing_keywords: [...] }`.

---

## Step 3: Save Intermediate Files

Create directory `output/{company-slug}/` and save:
- `application.json` — tailored resume data (matches `resume.json` schema)
- `cover_letter.txt` — plain text cover letter
- `keyword_report.json` — matched vs missing keywords

company-slug = lowercase, hyphens only (e.g. "cohere-health", "cvs-health")

---

## Step 4: Generate PDFs

```bash
# Resume PDF
python3 make_pdf.py output/{company-slug}/application.json output/{company-slug}/SYED_ALAM_{JobTitle}_Resume.pdf
```

`make_pdf.py` uses **XeLaTeX** to render `resume_template.tex` → PDF. It maps `application.json` to the template. It automatically tries different levels of tightening to force the resume to exactly 1 page.

### 1-Page Full-Page Rule (CRITICAL)
- The PDF **MUST be exactly 1 page** — never 2 pages, never with blank space at the bottom.
- After generating, `make_pdf.py` automatically checks the page count and adjusts margins/spacing to fit.
- If the script warns it cannot fit on 1 page even at maximum tightening: you must drop 1-2 least-relevant bullets from the oldest role, then regenerate.
- If the content is **too short** (large blank gap at bottom): add a bullet or two from `resume.json` that were omitted, or expand existing bullets slightly. The page must look full and professional — not sparse.
- Target: content fills ~95-100% of the page.

---

## Step 5: Save to Database

Database: `data/applications.db` (SQLite)

```sql
-- Schema
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
  file_type      TEXT NOT NULL,   -- 'resume_pdf', 'cover_letter_pdf', 'tailored_json'
  file_path      TEXT NOT NULL,   -- relative path from project root
  created_at     TEXT NOT NULL
);
```

Insert/update company → insert application → insert generated_files rows.

---

## Tailoring Knowledge

### What to Lead With by Role Type

| Role Type | Lead With |
|-----------|-----------|
| Frontend Engineer | React, TypeScript, Vue.js, dashboards, 3D, performance |
| Full Stack Engineer | React + Node.js APIs, SQL/NoSQL, Azure, full SDLC |
| Mobile Engineer | React Native, Capacitor, Swift/Kotlin native modules, app store |
| Backend/API | Node.js, REST APIs, PostgreSQL, authentication, cloud |
| AI/Product | OpenAI, Gemini, GenAI integration, product-aware engineering |
| Real-time/IoT | MQTT, RabbitMQ, WebSockets, telemetry, beacon SDKs |

### Bullet Rules (CRITICAL — do not stray from original experience)
- Keep all bullets from `resume.json` **verbatim** — same words, same structure.
- You may **reorder** bullets by JD relevance (most relevant at top).
- You may make **small, truthful keyword additions** within an existing bullet if the skill is genuinely implied (e.g. ".NET REST APIs" → ".NET REST APIs using **C#**"). Never fabricate.
- Drop 1-2 bullets only as a last resort for 1-page fit — prefer adjusting font size first.
- **Never** rewrite or paraphrase bullets. Never merge/split bullets. Never change tone or specificity.
- The **summary** paragraph is the only section that should be fully rewritten per JD.

### Keyword Strategy
- Push JD keywords to front of skills categories.
- Add missing keywords to **skills section** if the user actually has adjacent experience (e.g. "SQL Server" if user knows PostgreSQL/SQL).
- Never add a keyword the user has zero experience with.
- If JD uses a different name for something the user has ("ASP.NET Web API" for ".NET REST APIs"), count it as matched and add the alias to skills.

### 1-Page Full-Page Enforcement
- US Letter size, margins as defined in `make_pdf.py` and matching `resume_template.tex`.
- If too long: reduce font size (7.5pt → 7.2pt), then drop 1-2 oldest/least-relevant bullets.
- If too short (blank space at bottom): add omitted bullets from `resume.json` to fill the page.
- Summary must be ≤ 3 sentences.
- Page must look full and professional — aim for 95-100% page fill.

---

## Dashboard

Start the dashboard server:
```bash
python3 server.py
# Opens at http://localhost:8000
```

The dashboard shows all generated applications from `data/applications.db` with search, filter, file links, and status tracking.
