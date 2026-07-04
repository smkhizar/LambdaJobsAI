#!/usr/bin/env python3
"""
Wellfound (AngelList Talent) job scraper — DataDome-protected, so this uses
CloakBrowser in VISIBLE mode (a real browser window opens on screen; do not run
headless — DataDome blocks it, as does plain HTTP and Scrapling).

Listing URL that works (verified 2026-07-04): https://wellfound.com/jobs?remote=true&role={slug}
Cards carry: title, company, "Remote • City", salary range, posted-age ("today",
"yesterday", "N days ago").

Run:
  /opt/homebrew/bin/python3.12 scripts/scrapers/wellfound_scraper.py \
      --roles software-engineer,frontend-engineer --max-age-days 2

Output:
  data/scraped_jobs/wellfound_YYYYMMDD_HHMM.json + rows in data/scan_history.tsv
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unified_job_scraper import (  # noqa: E402
    OUTPUT_DIR, append_history, dedup_key, load_history, should_skip,
)

JOB_LINK_RE = re.compile(r'href="(/jobs/\d[^"]*)"')
COMPANY_RE = re.compile(r'href="/company/([^"/?]+)')
TEXT_RE = re.compile(r">([^><]{2,90})<")
AGE_RE = re.compile(r"^(today|yesterday|(\d+)\s+days?\s+ago|(\d+)\s+weeks?\s+ago)$", re.I)
NOISE = {"Save", "Apply", "•", "Actively Hiring", "Promoted"}


def age_days(texts: list[str]) -> float | None:
    for t in texts:
        m = AGE_RE.match(t.strip())
        if not m:
            continue
        s = m.group(1).lower()
        if s == "today":
            return 0
        if s == "yesterday":
            return 1
        if m.group(2):
            return int(m.group(2))
        if m.group(3):
            return int(m.group(3)) * 7
    return None


def parse_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    matches = list(JOB_LINK_RE.finditer(html))
    for i, m in enumerate(matches):
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else m.start() + 2500
        segment = html[m.start():seg_end]
        before = html[max(0, m.start() - 4000):m.start()]
        comp_slugs = COMPANY_RE.findall(before)
        texts = [t.strip() for t in TEXT_RE.findall(segment) if t.strip() and t.strip() not in NOISE]
        title = next((t for t in texts if len(t) > 8 and not AGE_RE.match(t) and "$" not in t and "Remote" not in t), "")
        salary = next((t for t in texts if "$" in t), None)
        location = next((t for t in texts if "Remote" in t), "Remote")
        jobs.append(
            {
                "title": title,
                "company": (comp_slugs[-1].replace("-", " ").title() if comp_slugs else ""),
                "location": location,
                "url": "https://wellfound.com" + m.group(1),
                "description": "",
                "needs_jd_fetch": True,
                "salary": salary,
                "age_days": age_days(texts),
                "source": "wellfound",
            }
        )
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roles", default="software-engineer,frontend-engineer",
                        help="comma-separated wellfound role slugs")
    parser.add_argument("--max-age-days", type=float, default=2)
    args = parser.parse_args()

    import cloakbrowser  # 0.4.x API: module-level launch(); no CloakBrowser class

    seen_urls, seen_keys = load_history()
    all_jobs: list[dict] = []
    browser = cloakbrowser.launch(headless=False)
    page = browser.new_page()
    try:
        for role in args.roles.split(","):
            url = f"https://wellfound.com/jobs?remote=true&role={role.strip()}"
            try:
                page.goto(url, timeout=90000)
                page.wait_for_timeout(7000)
                html = page.content()
            except Exception as exc:
                print(f"[wellfound] {role} failed: {exc}", file=sys.stderr)
                continue
            if "verification required" in html.lower() or "just a moment" in html.lower():
                print(f"[wellfound] {role}: DataDome challenge — solve it in the visible window, rerun", file=sys.stderr)
                continue
            all_jobs.extend(parse_listing(html))
    finally:
        browser.close()

    stamp = datetime.now().strftime("%Y-%m-%d")
    fresh, history_rows = [], []
    counts = {"raw": len(all_jobs), "stale": 0, "dup": 0, "skip": 0, "unparsed": 0, "new": 0}
    batch_keys: set[str] = set()
    for job in all_jobs:
        if not job["title"] or not job["company"]:
            counts["unparsed"] += 1
            continue
        if job["age_days"] is not None and job["age_days"] > args.max_age_days:
            counts["stale"] += 1
            continue
        key = dedup_key(job["title"], job["company"])
        row = {"url": job["url"], "first_seen": stamp, "source": "wellfound",
               "title": job["title"], "company": job["company"], "location": job["location"]}
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
    out = OUTPUT_DIR / f"wellfound_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(out, "w") as f:
        json.dump(fresh, f, indent=2)
    print(f"Wellfound: raw {counts['raw']} | new {counts['new']} | stale {counts['stale']} | "
          f"dup {counts['dup']} | filtered {counts['skip']} | unparsed {counts['unparsed']} → {out}")


if __name__ == "__main__":
    main()
