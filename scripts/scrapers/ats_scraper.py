#!/usr/bin/env python3
"""
ATS API scraper — zero-token, zero-anti-bot job pulls straight from company boards.

Reads tracked companies from data/portals.yml and hits their public ATS APIs
(Greenhouse and Lever fully supported; Ashby/Workday documented in SCRAPING.md,
add here when a tracked company needs them). Full JDs come back with the posting —
no browser, no JD-fetch step needed.

Run:
  /opt/homebrew/bin/python3.12 scripts/scrapers/ats_scraper.py [--max-age-days 7] [--all-titles]

Also supports ad-hoc checks without portals.yml:
  /opt/homebrew/bin/python3.12 scripts/scrapers/ats_scraper.py --adhoc greenhouse:postman,lever:stripe

Output:
  data/scraped_jobs/ats_YYYYMMDD_HHMM.json + rows in data/scan_history.tsv
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unified_job_scraper import (  # noqa: E402
    OUTPUT_DIR, REPO_DIR, append_history, dedup_key, load_history, should_skip,
)

PORTALS = REPO_DIR / "data" / "portals.yml"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
TITLE_POSITIVE = ["engineer", "developer", "full stack", "frontend", "front-end", "react",
                  "typescript", "mobile", "node", "software"]


def get_json(url: str, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def strip_html(s: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def fetch_greenhouse(slug: str) -> list[dict]:
    d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    jobs = []
    for j in d.get("jobs", []):
        jobs.append({
            "title": j.get("title", ""),
            "company": slug,
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "description": strip_html(j.get("content", "")),
            "date_posted": (j.get("updated_at") or "")[:10],
            "source": "greenhouse",
        })
    return jobs


def fetch_lever(slug: str) -> list[dict]:
    d = get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    jobs = []
    for j in d if isinstance(d, list) else []:
        cat = j.get("categories") or {}
        jobs.append({
            "title": j.get("text", ""),
            "company": slug,
            "location": cat.get("location", ""),
            "url": j.get("hostedUrl") or j.get("applyUrl", ""),
            "description": strip_html(j.get("descriptionPlain") or j.get("description", "")),
            "date_posted": datetime.fromtimestamp((j.get("createdAt") or 0) / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if j.get("createdAt") else "",
            "source": "lever",
        })
    return jobs


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever}


def tracked_companies() -> list[dict]:
    """Tiny YAML reader for our scaffold format — avoids a PyYAML dependency."""
    if not PORTALS.exists():
        return []
    entries, cur = [], None
    in_tracked = False
    for line in PORTALS.read_text().splitlines():
        if re.match(r"^tracked_companies:\s*\[\]", line):
            return []
        if line.startswith("tracked_companies:"):
            in_tracked = True
            continue
        if in_tracked and re.match(r"^\S", line):  # next top-level key
            break
        if not in_tracked or line.strip().startswith("#"):
            continue
        m = re.match(r"^\s*-\s*name:\s*(.+)$", line)
        if m:
            cur = {"name": m.group(1).strip()}
            entries.append(cur)
        elif cur is not None:
            kv = re.match(r"^\s*(\w+):\s*(.+)$", line)
            if kv:
                cur[kv.group(1)] = kv.group(2).strip()
    return [e for e in entries if str(e.get("enabled", "true")).lower() != "false"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-days", type=float, default=7)
    parser.add_argument("--all-titles", action="store_true", help="skip the title relevance filter")
    parser.add_argument("--adhoc", default="", help="comma list of ats:slug pairs, bypasses portals.yml")
    args = parser.parse_args()

    targets = []
    if args.adhoc:
        for pair in args.adhoc.split(","):
            ats, slug = pair.strip().split(":", 1)
            targets.append({"name": slug, "ats": ats, "ats_slug": slug})
    else:
        targets = tracked_companies()
    if not targets:
        sys.exit("No tracked companies (data/portals.yml empty) and no --adhoc given. "
                 "Add companies to portals.yml — that's what makes this tier free.")

    seen_urls, seen_keys = load_history()
    now = datetime.now(timezone.utc)
    fresh, history_rows = [], []
    counts = {"raw": 0, "new": 0, "dup": 0, "skip": 0, "stale": 0, "title": 0, "errors": 0}
    batch_keys: set[str] = set()

    for t in targets:
        ats, slug = t.get("ats", ""), t.get("ats_slug", t["name"])
        fetcher = FETCHERS.get(ats)
        if not fetcher:
            print(f"[ats] {t['name']}: no fetcher for {ats!r} (supported: {list(FETCHERS)})", file=sys.stderr)
            continue
        try:
            jobs = fetcher(slug)
        except Exception as exc:
            counts["errors"] += 1
            print(f"[ats] {t['name']} ({ats}) failed: {exc}", file=sys.stderr)
            continue
        counts["raw"] += len(jobs)
        for job in jobs:
            job["company"] = t["name"]
            if not args.all_titles and not any(k in job["title"].lower() for k in TITLE_POSITIVE):
                counts["title"] += 1
                continue
            if job["date_posted"]:
                try:
                    age = (now - datetime.fromisoformat(job["date_posted"]).replace(tzinfo=timezone.utc)).days
                    if age > args.max_age_days:
                        counts["stale"] += 1
                        continue
                except ValueError:
                    pass
            key = dedup_key(job["title"], job["company"])
            row = {"url": job["url"], "first_seen": now.strftime("%Y-%m-%d"), "source": job["source"],
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
    out = OUTPUT_DIR / f"ats_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(out, "w") as f:
        json.dump(fresh, f, indent=2)
    print(f"ATS: raw {counts['raw']} | new {counts['new']} | title-skip {counts['title']} | "
          f"stale {counts['stale']} | dup {counts['dup']} | filtered {counts['skip']} | "
          f"errors {counts['errors']} → {out}")


if __name__ == "__main__":
    main()
