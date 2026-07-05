# Hermes Agent Integration

This project is fully integrated with **Hermes Agent** via the `lambdajobs-resume-agent` skill.

## Quick Start

1. Start Hermes with the skill preloaded:
   ```bash
   hermes -s lambdajobs-resume-agent
   ```

2. Or load it in an existing session:
   ```
   /skill lambdajobs-resume-agent
   ```

## How It Works

When you give Hermes any job posting (URL or pasted description), it will:

1. Parse the job following `AGENT.md` rules
2. Tailor your resume (`summary` rewritten, bullets selected, ordered, and truthfully rewritten)
3. Generate keyword match/missing report
4. Create mandatory cover letter (strict ATS + AI-screener style rules)
5. Run `python3 lambda.py finalize` (produces 1-page PDFs + updates DB)
6. Commit changes to git with proper changelog
7. Show you the results + dashboard link

## Project Commands (via Hermes)

- Check environment: `python3 lambda.py check`
- Initialize DB: `python3 lambda.py init`
- List all applications: `python3 lambda.py list`
- Start dashboard: `python3 server.py` → http://localhost:8000

## Rules

Hermes **strictly** follows every rule in `AGENT.md`:
- Never invents experience
- Bullets come from `bullet_bank.json`; truthful impact-first rewrites are allowed when anchors survive
- Resume must be exactly 1 page
- Cover letter must be exactly 1 page
- Always runs `finalize` so DB and dashboard stay in sync

## Location

Project root: `/Users/khizar/Desktop/Personal/LambdaJobsAI`

---

Generated and maintained by Hermes.
