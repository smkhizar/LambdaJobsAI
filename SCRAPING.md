# SCRAPING.md — Job Scraping Toolkit (for any AI agent)

> Portable instructions for **any** agent (Hermes, Claude Code, GPT, Gemini, local LLM) that
> scrapes jobs for this project. Pairs with [AGENT.md](AGENT.md) (tailoring rules) and
> [SEARCH_TITLES.md](SEARCH_TITLES.md) (query priorities). Last verified: 2026-07-04.

## ⚠️ Interpreter — the #1 pitfall on this machine
The scraping toolkit lives in the **Homebrew Python 3.12 user site**
(`~/Library/Python/3.12/lib/python/site-packages`). Three other Pythons on this machine do
NOT have it:

| Interpreter | Has toolkit? |
|---|---|
| `/opt/homebrew/bin/python3.12` | ✅ **USE THIS** |
| `python3` (3.13, uv-managed) | ❌ |
| `python3.12` on PATH (`~/.local/bin`, uv-managed) | ❌ looks right, isn't |
| `/Users/khizar/.hermes/hermes-agent/venv/bin/python3` | ❌ hermes framework only |

Always invoke: `/opt/homebrew/bin/python3.12`

## Version-check protocol (run at the START of any scraping session)
These libraries update frequently (anti-bot arms race). Stale versions = blocks.

```bash
# 1. Installed versions
/opt/homebrew/bin/python3.12 -m pip list 2>/dev/null | grep -iE "jobspy|scrapling|cloakbrowser|crawl4ai|camoufox"

# 2. Latest on PyPI
for p in python-jobspy scrapling cloakbrowser crawl4ai camoufox; do
  echo -n "$p latest: "; curl -s https://pypi.org/pypi/$p/json | /opt/homebrew/bin/python3.12 -c "import json,sys;print(json.load(sys.stdin)['info']['version'])"
done

# 3. Upgrade anything stale (JobSpy comes from git main, not PyPI!)
/opt/homebrew/bin/python3.12 -m pip install --user --upgrade --break-system-packages scrapling cloakbrowser crawl4ai camoufox
/opt/homebrew/bin/python3.12 -m pip install --user --upgrade --break-system-packages "git+https://github.com/speedyapply/JobSpy.git@main"

# 4. Smoke test (must print all versions without error)
/opt/homebrew/bin/python3.12 -c "from jobspy import scrape_jobs; from importlib.metadata import version; print('jobspy', version('python-jobspy'), '| scrapling', version('scrapling'), '| cloakbrowser', version('cloakbrowser'), '| crawl4ai', version('crawl4ai'))"
```

After a major-version jump, re-verify the library's API against its GitHub README/CHANGELOG
before a big run (e.g. Scrapling 0.2→0.4 changed imports; CloakBrowser 0.4.x kept
`new_page()` no-arg but ships a new Chromium that re-downloads on first run).

Baseline as of 2026-07-04: python-jobspy 1.1.82 · scrapling 0.4.9 · cloakbrowser 0.4.7 ·
crawl4ai 0.9.0 · camoufox 0.4.11. If installed ≥ these, you're current enough; still run the check.

**PITFALL:** `pip install jobspy` from PyPI is a **different package** (Redis job queue).
Only ever install `python-jobspy` from the speedyapply git repo. (A wrong-package `jobspy`
was found and removed from the system Python 3.9 site on 2026-07-04 — if `import jobspy`
ever returns a Redis queue API, you're on the wrong interpreter or the trap is back.)

## Tiered tool chain (cheapest first)
1. **JobSpy** — one call sweeps Indeed + LinkedIn + Google Jobs. Primary breadth tool.
   Glassdoor/ZipRecruiter return 403 through it (since May 2026).
2. **ATS public APIs** — zero anti-bot, real-time, full JDs. For tracked companies
   (`data/portals.yml`) and freshness: Greenhouse `boards-api.greenhouse.io/v1/boards/{co}/jobs?content=true`,
   Lever `api.lever.co/v0/postings/{co}?mode=json`, Ashby GraphQL, Workday `wday/cxs` POST,
   BambooHR, Teamtailor RSS, Breezy JSON, RemoteOK `remoteok.com/api`, WeWorkRemotely RSS,
   HN Who's Hiring via Algolia. Endpoint + parse details: hermes lambda-scraper SOUL.md, or
   career-ops `modes/scan.md` (github.com/santifer/career-ops).
3. **Scrapling StealthyFetcher** — Indeed deep-queries beyond JobSpy. Camoufox fingerprint,
   0 blocks tested. `result.text` is EMPTY — use `result.html_content` / `result.css()`.
4. **CloakBrowser** — Glassdoor + hard sites. `headless=False`, `humanize=True`;
   `new_page()` takes no arguments.
5. **Crawl4AI** — general anti-bot sites. **Never Indeed** (403 after 1-2 queries; same for Crawlee).
6. **browser-use** — AI-driven navigation for login flows / weird SPAs. Not currently
   installed; install on demand: `/opt/homebrew/bin/python3.12 -m pip install --user --break-system-packages browser-use`.

Discipline: if a cheaper tier already covered a company/board this run, do NOT re-scrape it
with a more expensive tier.

## The unified script
```bash
/opt/homebrew/bin/python3.12 scripts/scrapers/unified_job_scraper.py --hours 24 --per-query 25
```
JobSpy sweep over [SEARCH_TITLES.md](SEARCH_TITLES.md) priorities → staffing blacklist +
title filter → cross-run dedup → writes `data/scraped_jobs/jobs_*.json` + appends every
seen job to `data/scan_history.tsv` with a status
(`added|skipped_title|skipped_dup|skipped_staffing|skipped_stale|skipped_expired|skipped_location`).

## Dedup contract (all agents must honor)
Before creating any triage task / tailoring anything, check all three:
1. `data/scan_history.tsv` — URL or normalized company+title already seen
2. `output/` — company slug already tailored/applied
3. `data/applications.db` — company already tracked

## Liveness rule
Aggregator/ATS API results are real-time — trust them. Any URL from a **search-engine result**
(Google cache, WebSearch) can be weeks stale: fetch it first; expired signals are
`?error=true` final URL (Greenhouse), "no longer available/position has been filled/expired",
or a page with <~300 chars of real content. Record expired as `skipped_expired`, move on.

## Filters (summary — full list in the script)
USA remote only · no staffing agencies · no staff/principal/director/intern/data-scientist/
devops/wordpress titles · ≤7 days old · dedupe multi-city reposts by normalized title+company ·
must have title+company+description(>50 chars). Ghost-job signals (30+ days old, 20+ cities,
absurd salary span) → flag, don't silently drop.

## Indeed CSS selectors (verified May 2026)
Card `div.cardOutline` · title `span[id^="jobTitle"]` · company `[data-testid="company-name"]` ·
location `[data-testid="text-location"] span` · JD page `#jobDescriptionText` ·
pagination `&start=10,20…` · job key `a[data-jk]` attrib.

## Anti-bot rules (tested)
- Do NOT rotate user agents — detected. Camoufox/CloakBrowser fingerprints instead.
- 1.5–2s delay between Scrapling queries.
- JobSpy handles anti-bot internally; no browser needed.
