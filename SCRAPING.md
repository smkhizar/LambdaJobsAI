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

## Source matrix (verified 2026-07-04)
| Source | How | Status |
|---|---|---|
| Indeed | JobSpy (`site_name=["indeed"]`) | ✅ works, full JDs |
| LinkedIn | JobSpy + guest JD API `https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}` (no login; gives full JD, posted-age, salary) | ✅ works |
| Google Jobs | JobSpy (`site_name=["google"]` + `google_search_term`) | ⚠️ flaky — returned 0 rows on test; low loss: Google Jobs aggregates the same boards we already hit |
| Dice | Dice MCP connector (`search_jobs`) in agent runtimes — no standalone script | ✅ works (min date filter = 1 day; filter to fresher by `postedDate` yourself) |
| BuiltIn | `scripts/scrapers/builtin_scraper.py` — plain HTTP, server-rendered | ✅ works, no anti-bot; cards carry posted-age/salary/Remote+USA |
| Wellfound | `scripts/scrapers/wellfound_scraper.py` — CloakBrowser **visible** mode (DataDome blocks plain HTTP, Scrapling, and headless). Listing URL: `wellfound.com/jobs?remote=true&role={slug}` (`/role/remote/...` variants 404). **DISCOVERY ONLY — never apply on Wellfound** (see rule below) | ✅ works via visible browser window |

### RULE: Wellfound is discovery-only — always apply at the origin
Wellfound applications attach ONE profile CV for every job (no per-application resume upload),
which defeats tailored resumes. So for every Wellfound hit:
1. Find the SAME posting at its origin: company careers page or ATS (try the Greenhouse API
   first: `boards-api.greenhouse.io/v1/boards/{company}/jobs`, then Lever/Ashby/Workday
   patterns above), or LinkedIn/Indeed.
2. Apply THERE with the tailored PDF. Record the origin URL (not the Wellfound URL) in the
   tracker and keyword_report.
3. If the posting cannot be found anywhere outside Wellfound → **skip the job entirely.**
(Verified example 2026-07-04: Postman "Senior Forward Deployed Engineer" on Wellfound =
`job-boards.greenhouse.io/postman/jobs/6672559003` on Greenhouse.)
| RemoteOK / WWR / HN Who's Hiring | public API / RSS / Algolia | ✅ works, thin volume |
| Glassdoor / ZipRecruiter | via JobSpy | ❌ 403 since May 2026 |

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
4. **CloakBrowser** — Glassdoor, Wellfound + hard sites. **0.4.x API**: no class —
   `import cloakbrowser; browser = cloakbrowser.launch(headless=False); page = browser.new_page()`
   (standard Playwright Browser back). Use `headless=False` for DataDome sites.
5. **Crawl4AI** — general anti-bot sites. **Never Indeed** (403 after 1-2 queries; same for Crawlee).
6. **browser-use** — AI-driven navigation for login flows / weird SPAs. Not currently
   installed; install on demand: `/opt/homebrew/bin/python3.12 -m pip install --user --break-system-packages browser-use`.

Discipline: if a cheaper tier already covered a company/board this run, do NOT re-scrape it
with a more expensive tier.

## The scripts (all share the same filters + scan_history dedup)
```bash
# Indeed + LinkedIn + Google (JobSpy sweep over SEARCH_TITLES.md priorities)
/opt/homebrew/bin/python3.12 scripts/scrapers/unified_job_scraper.py --hours 24 --per-query 25

# BuiltIn (plain HTTP; cards have posted-age so tight windows work)
/opt/homebrew/bin/python3.12 scripts/scrapers/builtin_scraper.py --search react --pages 3 --max-age-hours 24

# Wellfound (OPENS A VISIBLE BROWSER WINDOW — DataDome; never headless)
/opt/homebrew/bin/python3.12 scripts/scrapers/wellfound_scraper.py --roles software-engineer,frontend-engineer --max-age-days 2
```
All write `data/scraped_jobs/*.json` + append every seen job to `data/scan_history.tsv` with a
status (`added|skipped_title|skipped_dup|skipped_staffing|skipped_stale|skipped_expired|skipped_location`).
Dice has no script — use the Dice MCP connector in agent runtimes.

## LinkedIn full-JD guest API (no login, no browser)
```bash
curl -A "Mozilla/5.0" "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
```
`job_id` = digits in `linkedin.com/jobs/view/{id}`. Returns HTML with the FULL description,
`posted-time-ago__text` (exact freshness), location, and salary when present. This fixes the
"LinkedIn gives no description via JobSpy" gap — fetch before triage/tailoring. ~17 parallel
requests tested fine; keep bursts modest.

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
