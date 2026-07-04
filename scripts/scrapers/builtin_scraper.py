#!/usr/bin/env python3
"""
BuiltIn.com job scraper (plain HTTP — no anti-bot as of 2026-07, verify with SCRAPING.md
protocol if it starts returning 403/challenge pages).

Scrapes builtin.com remote dev/engineering listings, parses job cards from the
server-rendered HTML, filters by posting age, and appends to data/scan_history.tsv
via the unified pipeline's dedup helpers.

Run:
  /opt/homebrew/bin/python3.12 scripts/scrapers/builtin_scraper.py --search react --pages 3 --max-age-hours 24

Output:
  data/scraped_jobs/builtin_YYYYMMDD_HHMM.json  (jobs list, same shape as unified scraper)
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unified_job_scraper import (  # noqa: E402
    OUTPUT_DIR, append_history, dedup_key, load_history, should_skip,
)

BASE = "https://builtin.com/jobs/remote/dev-engineering"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

CARD_RE = re.compile(
    r'data-id="company-title"[^>]*>\s*<span>(?P<company>[^<]+)</span>.*?'
    r'href="(?P<href>/job/[^"]+)"[^>]*data-id="job-card-title"[^>]*>(?P<title>[^<]+)</a>',
    re.S,
)
AGE_RE = re.compile(r"(?:Reposted\s+)?(\d+)\s+(Minute|Hour|Day|Week|Month)s?\s+Ago", re.I)
SALARY_RE = re.compile(r">([\d.]+K?-[\d.]+K?\s+Annually)<")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def age_hours(card_html: str) -> float | None:
    m = AGE_RE.search(card_html)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}[unit]


def parse_page(html: str) -> list[dict]:
    jobs: list[dict] = []
    matches = list(CARD_RE.finditer(html))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 4000
        card = html[m.start():end]
        sal = SALARY_RE.search(card)
        jobs.append(
            {
                "title": m.group("title").strip(),
                "company": m.group("company").strip(),
                "location": "Remote (USA)" if ">USA<" in card else "Remote",
                "url": "https://builtin.com" + m.group("href"),
                "description": "",
                "needs_jd_fetch": True,
                "salary": sal.group(1) if sal else None,
                "age_hours": age_hours(card),
                "reposted": "Reposted" in card,
                "source": "builtin",
            }
        )
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", default="", help="keyword filter (e.g. react)")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--max-age-hours", type=float, default=24)
    args = parser.parse_args()

    seen_urls, seen_keys = load_history()
    all_jobs: list[dict] = []
    for page in range(1, args.pages + 1):
        url = f"{BASE}?page={page}"
        if args.search:
            url += f"&search={urllib.request.quote(args.search)}"
        try:
            html = fetch(url)
        except Exception as exc:
            print(f"[builtin] page {page} failed: {exc}", file=sys.stderr)
            break
        page_jobs = parse_page(html)
        if not page_jobs:
            break
        all_jobs.extend(page_jobs)
        time.sleep(1.5)

    stamp = datetime.now().strftime("%Y-%m-%d")
    fresh, history_rows = [], []
    counts = {"raw": len(all_jobs), "stale": 0, "dup": 0, "skip": 0, "new": 0}
    batch_keys: set[str] = set()
    for job in all_jobs:
        key = dedup_key(job["title"], job["company"])
        row = {"url": job["url"], "first_seen": stamp, "source": "builtin",
               "title": job["title"], "company": job["company"], "location": job["location"]}
        if job["age_hours"] is not None and job["age_hours"] > args.max_age_hours:
            counts["stale"] += 1
            continue
        if job["url"] in seen_urls or key in seen_keys or key in batch_keys:
            counts["dup"] += 1
            continue
        batch_keys.add(key)
        skip = should_skip(job["title"], job["company"])
        if skip:
            counts["skip"] += 1
            history_rows.append({**row, "status": skip})
            continue
        counts["new"] += 1
        history_rows.append({**row, "status": "added"})
        fresh.append(job)

    append_history(history_rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"builtin_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(out, "w") as f:
        json.dump(fresh, f, indent=2)
    print(f"BuiltIn: raw {counts['raw']} | new {counts['new']} | stale {counts['stale']} | "
          f"dup {counts['dup']} | filtered {counts['skip']} → {out}")


if __name__ == "__main__":
    main()
