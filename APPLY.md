# APPLY.md — Live Application-Form Assistant

> Instructions for any AI agent helping Khizar fill a job application form in real time.
> Reads the form (browser tools / screenshot / pasted text), loads this repo's context for the
> job, and generates ready-to-paste answers. Pairs with [AGENT.md](AGENT.md) — the
> **Truthfulness Boundary there applies to every answer generated here.**

## Workflow
```
1. DETECT     → Read the active browser tab (or screenshot / pasted questions)
2. IDENTIFY   → Extract company + role from the page
3. LOAD       → Match against output/{slug}/ (application.json, keyword_report.json,
                cover_letter.txt, job_description.txt) + resume.json + master_resume.json
4. PREFLIGHT  → Confirm posting is live + company/role matches the loaded context
5. KNOCK-OUT  → Scan the WHOLE form for auto-reject questions BEFORE drafting anything
6. ANALYZE    → Enumerate every visible form field
7. GENERATE   → Personalized answer per field, grounded in real history
8. PRESENT    → Formatted copy-paste block
9. PERSIST    → Save answers to output/{slug}/application_answers.md; update tracker
```

## Step 0 — Never apply on Wellfound (or any single-profile-CV board)
Wellfound attaches ONE profile CV to every application — the tailored resume can't be used.
If the form on screen is Wellfound (or any board without a per-application resume upload):
1. Stop. Find the same posting at its origin — company careers page / Greenhouse
   (`boards-api.greenhouse.io/v1/boards/{company}/jobs`) / Lever / Ashby / LinkedIn / Indeed.
2. Continue this flow on the origin posting instead; record the origin URL in the tracker.
3. Posting exists nowhere else → skip the job and say why.

## Step 1–3 — Detect, identify, load
- With browser tools: snapshot the active page; read title, URL, visible fields.
- Without: ask for a screenshot or pasted questions; never guess the form's content.
- Match company against `output/` slugs. Hit → load all four context files. Miss → offer to run
  the full tailoring pipeline first (AGENT.md Steps 1–8); an application without a tailored
  resume is a wasted shot.

## Step 4 — Preflight gate (do not draft before this resolves)
1. Verify the posting is live: JD content visible + an Apply/Submit control. Closed signals:
   `?error=true` final URL, "no longer accepting applications", 404/410, page that is only
   nav/footer.
2. Compare on-screen company + title against the loaded context. Material mismatch → stop and
   ask: re-evaluate, adapt, or abort.
3. Context only from a screenshot/paste → say liveness can't be verified; ask Khizar to confirm.

## Step 5 — Knock-out pre-scan (the ATS auto-reject traps)
Scan the entire form FIRST for these; flag each before generating other answers:

| Question type | Khizar's truthful answer |
|---|---|
| Authorized to work in the US? | **Yes** |
| Will you now or in the future require sponsorship? | **No** |
| US citizen? | **No** — if citizenship is *required*, WARN: likely auto-reject; ask before proceeding |
| Security clearance? | None — if required, WARN: auto-reject |
| Bachelor's degree in CS or related? | **Yes** (B.Sc. CS, University of Karachi) |
| Master's degree? | **Yes** (M.Sc. Intl. Software Systems Science, University of Bamberg) |
| Years of professional software experience | **7+** (Aug 2018 – present); for "X+ years with {React/TypeScript/Node}" count from Apr 2021 (4+) unless the tech was used at Symanto too |
| Location / relocation | Dallas, TX; remote preferred — relocation questions: ASK Khizar |
| Salary expectation | ASK Khizar (or "flexible / market rate" if a free-text field and he pre-approved) |
| Start date / notice period | ASK Khizar |

If a required knock-out answer conflicts with the posting's stated requirement, present:
`⚠️ KNOCK-OUT: form asks "{question}". Truthful answer "{answer}" may auto-reject. Proceed / skip?`
and WAIT.

**NEVER invent answers** for legal, demographic, visa, disability, veteran-status,
background-check, criminal-history, salary, or self-identification fields. Not derivable from
resume.json → mark `ASK KHIZAR`. Demographic/EEO self-identification questions: default
suggestion is "Decline to self-identify" unless Khizar says otherwise.

## Step 6 — Analyze fields
For every field capture: exact label, type (text/textarea/select/radio/checkbox/number/file),
required?, char/word limit, visible options. If the form scrolls beyond view, iterate until all
fields are covered — a half-filled required section = silent rejection.

## Step 7 — Generate answers
- Free-text ("Why us?", "Why this role?"): 3–6 sentences. Reference something SPECIFIC from
  the JD (product, stack, mission) + one quantified proof point from the tailored resume
  (5,000+ DAU PWA, multi-platform React/React Native/Vue delivery, App Store/Play Store
  releases, OpenAI/Gemini integrations). Reuse cover_letter.txt phrasing where it fits —
  don't contradict it.
- "Tell us about a project": pick the bullet-bank fact closest to the JD's primary stack;
  answer in STAR shape (situation → task → action → result).
- Every answer must pass the interview test: Khizar can speak to it for 2 minutes.
- Resume upload field: point to `output/{slug}/SYED_ALAM_Resume.pdf` (verify it exists and
  passed `verify_ats.py`). Cover letter field: `SYED_ALAM_CoverLetter.pdf` or paste
  cover_letter.txt.

## Step 8 — Present
```
## Answers: {Company} — {Role}
Context: output/{slug}/ | ATS coverage: {pct}% | Caveats: {...}

### 1. {Exact form question}
> {ready-to-paste answer}   ← or "ASK KHIZAR: {what to confirm}"
...
Skipped (agent cannot safely fill): {checkboxes/captcha/EEO...} with recommended values
```

## Step 9 — Persist
1. Write `output/{slug}/application_answers.md`: date, state (`filled` → `submitted` once
   confirmed), every Q/A as submitted, files uploaded.
2. On confirmed submission: update the tracker (`python3 lambda.py finalize ...` if not yet
   recorded, or update the application status in `data/applications.db`).

## ATS quirks (field-tested — from career-ops)
- **Ashby** dedupes candidates by email per company. Second application to the same company →
  warn; suggest `smkhizar.alam+{tag}@gmail.com` alias, let Khizar decide.
- **Lever**: programmatic clicks on checkboxes/radios trigger hCaptcha mid-form. Fill only
  text/textarea/select; list checkbox values for Khizar to tick himself.
- **Workable**: SPA re-renders invalidate element refs between fills. Re-query each element
  fresh; never cache refs.
- **react-select widgets** (Greenhouse/Ashby/Lever location fields): DOM rebuilds per
  keystroke. Type slowly (~100ms/char), re-snapshot after every selection.
- **Huge native `<select>`** (1,000+ options: country, university): select by value/label
  directly; NEVER snapshot the whole option list into context.
- Browser-tier rule: web forms → Chrome/browser MCP tools, not OS-level computer use.
  Agent never clicks final **Submit** — Khizar always submits himself.
