# Contributing to LambdaJobsAI

This is a personal project, but issues and pull requests are welcome.

## Development setup

Follow "Prerequisites" and "First-time setup" in [`README.md`](README.md), then set up your own
`resume.json` + `bullet_bank.json` per the "Bring your own data" section — the tailoring engine
has nothing to run against without them.

## Before opening a PR

- `python3 lambda.py check` — confirms XeLaTeX/poppler/Python are all wired up
- Run the scraper/tailoring path you touched end-to-end at least once; there's no test suite yet,
  so a real `output/<slug>/application.json` passing `verify_ats.py` is the bar

## Commit style

Conventional commits — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:` — with a short
imperative summary line.

## Scope

The deterministic pieces (`make_pdf.py`, `make_cover_letter.py`, `lambda.py`, `verify_ats.py`,
scrapers) stay deterministic — judgment calls (keyword strategy, tailoring) belong to the AI agent
following `AGENT.md`, not hardcoded here. Changes that blur that line, or that hardcode
assumptions about one person's resume shape into the deterministic code, are out of scope unless
discussed in an issue first.
