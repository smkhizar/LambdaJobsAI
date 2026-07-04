# LambdaJobsAI — Agent Instructions (v3)

> Source of truth for **any** AI agent (Claude, GPT, Gemini, Grok, local LLM) that tailors
> Khizar's resume. Read this file **before every task**. Last updated: 2026-07-04 (v3).
>
> **v3 changes:** bullet bank selection (`bullet_bank.json`), impact-first rewrite policy,
> AI-screener rules (semantic match, not keyword stuffing), exact-token mirroring,
> title mirroring, and mandatory deterministic verification (`verify_ats.py`).

Working directory: `/Users/khizar/Desktop/Personal/LambdaJobsAI`

## What This Project Does
Given a job (URL, pasted JD, or natural-language ask) → produce a **1-page, ATS-optimized,
tailored resume PDF** (+ optional 1-page cover letter) → save to SQLite → browse in the dashboard.

The AI does the judgement (keyword strategy, tailoring). The repo does the deterministic parts
(`make_pdf.py`, `make_cover_letter.py`, `lambda.py`, dashboard).

---

## Core Rules (NEVER break)
1. **Ground everything in `resume.json` / `bullet_bank.json`.** Never invent employers, dates, or
   metrics. Never claim a tool the candidate has *zero* adjacency to (see Truthfulness Boundary).
2. **1-Page Rule.** The resume PDF MUST be exactly 1 page. `make_pdf.py` auto-tightens across spacing
   levels 0→4 to fit; you do not hand-shrink fonts. Aim for a full page (~95–100% fill), not sparse.
3. **Bullet counts fixed:** Pinestack = **16** highlights, Symanto = **6** highlights. Always.
   Select them from `bullet_bank.json` (the bank is larger than the count — that's the tailoring
   headroom). `always_include` bullets must be present; their anchors must survive any rewrite.
4. **Core anchors always survive** — React, React Native, Vue, TypeScript, Node.js, Swift, Kotlin,
   .NET must each appear somewhere in the final resume (bullets preferred, skills at minimum),
   even when the JD asks for none of them. `verify_ats.py` enforces this.
5. **Authorization line:** add `"authorization": "US Work Authorized (No Sponsorship)"` to
   `personal_info` on every tailored `application.json`.
6. **Company name never "Unknown."** Extract it from the JD or URL. Never ask the user for title/company.
7. **Run `python3 verify_ats.py output/{slug}/application.json` after every build.** Ship only on PASS.
8. **Update the database** (`python3 lambda.py finalize ...`) after every generation.

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

## Step 3 — Keyword coverage protocol (target ≥ 90%, two scorers)
Modern portals run **two filters**: a literal keyword matcher (classic ATS) AND an AI/semantic
scorer (Workday, Greenhouse, LinkedIn Recruiter, Ashby, hireEZ). Optimize for both:

**Literal matcher:**
1. Build the JD keyword set from the skill tags + required/preferred sections (languages, frameworks,
   cloud, tools, testing, concepts, domain terms).
2. **Exact-token mirroring:** use the JD's exact spelling at least once — if the JD says "React.js",
   write "React.js" (skills can list `React (React.js)`); "Node" vs "Node.js"; "CI/CD" vs
   "continuous integration"; "RESTful APIs" vs "REST APIs". Literal matchers don't normalize.
3. Coverage: a keyword counts as matched if it appears **anywhere** in the tailored resume text
   (summary, bullets, OR skills) — but keywords in **bullets with evidence** score higher with AI
   screeners than bare skills-list mentions. Prefer weaving into bullets.
4. Leave genuinely-absent tools **out**, honestly. Record them in `keyword_report.json` as
   `missing_keywords`. Do not fabricate to hit 100%.

**AI/semantic scorer (do NOT keyword-stuff):**
- Every keyword must sit inside a sentence that shows **what was done with it and the outcome**.
  A bullet that is a comma-list of tools reads as stuffing and scores WORSE with LLM screeners.
- Keep numbers: scale (5,000+ DAU), multi-customer deployments, store releases, years. AI scorers
  weight quantified evidence heavily.
- **Title mirroring:** the summary's first phrase mirrors the JD title truthfully (e.g. JD
  "Senior Frontend Engineer" → "Senior Frontend Engineer with 6+ years…"). His real employment
  titles never change.
- No keyword may appear more than ~3 times across the resume; repetition past that is a
  stuffing signal.

## Step 4 — Tailor the data
- **Summary:** fully rewritten per JD. 2–3 sentences: mirrored target title + years + top 3–5 JD
  keywords + one quantified proof point. Unique per job — never copy-paste.
- **Experience bullets — select, order, rewrite (see protocol below).**
- **Skills:** reorder categories and items to push JD keywords to the front; **add** adjacent-truthful
  keywords the JD asks for (exact JD token form). Never remove core anchors.

### Bullet selection (from `bullet_bank.json`)
1. Take all `always_include` bullets (they carry the core anchors: React/RN/Vue cross-platform,
   Kotlin/Swift native modules, Node.js APIs, TypeScript, Azure scale, .NET+Angular).
2. Fill the remaining slots to exactly 16 (Pinestack) / 6 (Symanto) by **tag relevance to the JD**
   (bank bullets are tagged: frontend, mobile, backend, realtime, ai, devops, testing, data,
   leadership, …).
3. Bullets left out of this job stay in the bank — nothing is ever deleted from the bank.

### Bullet ordering (what the human recruiter skims)
- **Top-3 rule:** the first 3 Pinestack bullets must each name a JD-primary technology; a recruiter
  decides in the top 3. The first bullet is never a generic/process bullet.
- Order: Tier A = JD-primary stack + the 5,000+ DAU scale bullet (top 4) → Tier B = JD-secondary
  stack → Tier C = quality/process (testing, accessibility, observability, leadership) → Tier D =
  off-angle tech (kept for anchors, placed last).
- **Verify the order deterministically** — assemble bullets by bank `id` in your planned sequence;
  don't trust a generation model to emit order correctly.

### Bullet rewrite policy (v3 — modify allowed, fabrication not)
You may **rewrite** any selected bullet to fit the role angle, under these constraints:
- Same underlying fact: same project, same employer, same real work. Reframe emphasis, don't
  invent new events or metrics.
- Impact-first shape: *strong verb + what + tech + outcome/scale* ("Accomplished X, using Y,
  achieving Z"). Lead with the part of the fact the JD cares about.
- The bullet's `anchors` from the bank must survive the rewrite verbatim (e.g. the native-modules
  bullet always keeps **Kotlin** and **Swift**).
- No merging two bank bullets into one, no splitting one into two (breaks the count + audit trail).
- The interview test still applies: he must be able to talk about the rewritten bullet for 2 minutes.

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

## Step 7 — Verify (do not skip; deterministic, not vibes)
```bash
python3 verify_ats.py output/{slug}/application.json
```
This extracts the **actual PDF text** (what an ATS parser sees) and checks: exactly 1 page;
16+6 bullet counts; `authorization` present; all core anchors extractable from the PDF;
every keyword claimed in `keyword_report.json` really present in the PDF text (catches
ligature/encoding corruption and hallucinated coverage); `always_include` bullet anchors intact.
**Ship only on PASS.** Additionally eyeball:
- Bullet ordering matches your intended tier order.
- No fabricated tool slipped into a bullet; keyword_report `missing_keywords` is honest.

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
`resume.json` (source of truth) · `bullet_bank.json` (tagged bullet pool — select from, never edit
during tailoring) · `RESUME.md` (human-readable) · `master_resume.json` (extended).
