#!/usr/bin/env python3
"""
Greenhouse-wide job search WITHOUT hardcoding company names.

Greenhouse has no global search API, so this works in two phases:

  1. --discover   Mine company slugs from the Common Crawl URL index
                  (every boards.greenhouse.io/{slug}/... URL seen on the web).
                  Slugs are cached in data/greenhouse_companies.json with
                  first_seen / last_checked / status metadata.

  2. --sweep N    Check the N least-recently-checked cached companies via the
                  public Greenhouse boards API, keep fresh + title-relevant
                  jobs (full JDs fetched for matches), dedup via
                  data/scan_history.tsv, write data/scraped_jobs/ghwide_*.json.

Run:
  /opt/homebrew/bin/python3.12 scripts/scrapers/greenhouse_discover.py --discover
  /opt/homebrew/bin/python3.12 scripts/scrapers/greenhouse_discover.py --sweep 200 --max-age-days 3

Discovery is idempotent — rerun monthly (new Common Crawl drops ~monthly).
Sweeps are incremental — each run continues where the last stopped, so a cron
running `--sweep 300` rotates through the whole cache over time.
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unified_job_scraper import (  # noqa: E402
    OUTPUT_DIR, REPO_DIR, append_history, dedup_key, load_history, should_skip,
)
from ats_scraper import TITLE_POSITIVE, get_json, strip_html  # noqa: E402

CACHE = REPO_DIR / "data" / "greenhouse_companies.json"
CC_DOMAINS = [
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "boards.eu.greenhouse.io",
    "job-boards.eu.greenhouse.io",
]
SLUG_RE = re.compile(r"greenhouse\.io/([A-Za-z0-9][A-Za-z0-9_-]{1,60})(?:/|\?|$)")
BAD_SLUGS = {"embed", "api", "v1", "boards", "jobs", "js", "assets", "career", "careers"}
FOREIGN = ["india", "canada", "united kingdom", " uk", "germany", "france", "poland", "spain",
           "portugal", "netherlands", "ireland", "australia", "singapore", "japan", "china",
           "brazil", "mexico", "argentina", "colombia", "philippines", "romania", "ukraine",
           "israel", "türkiye", "turkey", "egypt", "nigeria", "kenya", "vietnam", "korea",
           "taiwan", "quebec", "ontario", "british columbia", "bengaluru", "london", "berlin",
           "paris", "amsterdam", "dublin", "sydney", "tokyo", "emea", "apac", "latam"]


def location_ok(loc: str) -> bool:
    """Keep US/remote/unspecified; drop clearly-foreign locations."""
    low = loc.lower()
    if not low.strip():
        return True
    if any(f in low for f in FOREIGN):
        return "remote" in low and ("us" in low or "united states" in low or "americas" in low)
    return True


def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True))


def latest_crawls(n: int = 2) -> list[str]:
    info = get_json("https://index.commoncrawl.org/collinfo.json")
    return [c["id"] for c in info[:n]]


def discover(crawls: int) -> None:
    cache = load_cache()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    added = 0
    for crawl in latest_crawls(crawls):
        for domain in CC_DOMAINS:
            page = 0
            while True:
                url = (f"https://index.commoncrawl.org/{crawl}-index"
                       f"?url={urllib.parse.quote(domain + '/*')}&output=json"
                       f"&fl=url&collapse=urlkey&page={page}")
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        body = r.read().decode("utf-8", "ignore")
                except Exception as exc:
                    print(f"[discover] {crawl} {domain} p{page}: {exc}", file=sys.stderr)
                    break
                if not body.strip() or '"error"' in body[:200]:
                    break
                count_before = len(cache)
                for line in body.splitlines():
                    try:
                        u = json.loads(line)["url"]
                    except Exception:
                        continue
                    m = SLUG_RE.search(urllib.parse.unquote(u))
                    if not m:
                        continue
                    slug = m.group(1).lower().strip()
                    if slug in BAD_SLUGS or slug.isdigit():
                        continue
                    if slug not in cache:
                        cache[slug] = {"first_seen": today, "last_checked": None, "status": "unchecked"}
                added += len(cache) - count_before
                page += 1
                time.sleep(1)
                if page > 50:  # safety
                    break
            print(f"[discover] {crawl} {domain}: cache now {len(cache)} slugs")
    save_cache(cache)
    print(f"Discovered {added} new slugs; total {len(cache)} in {CACHE}")


def sweep(n: int, max_age_days: float) -> None:
    cache = load_cache()
    if not cache:
        sys.exit("Slug cache empty — run --discover first.")
    # least-recently-checked first; never-checked first of all
    order = sorted(cache.items(), key=lambda kv: (kv[1].get("last_checked") or "", kv[0]))
    targets = [slug for slug, meta in order if meta.get("status") != "dead"][:n]

    seen_urls, seen_keys = load_history()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    fresh, history_rows = [], []
    counts = {"companies": 0, "dead": 0, "raw": 0, "new": 0, "dup": 0, "stale": 0, "title": 0, "skip": 0}
    batch_keys: set[str] = set()

    for slug in targets:
        counts["companies"] += 1
        try:
            d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
        except Exception:
            cache[slug].update(last_checked=today, status="dead")
            counts["dead"] += 1
            continue
        jobs = d.get("jobs", [])
        cache[slug].update(last_checked=today, status="ok", openings=len(jobs))
        counts["raw"] += len(jobs)
        matches = []
        for j in jobs:
            title = j.get("title", "")
            if not any(k in title.lower() for k in TITLE_POSITIVE):
                counts["title"] += 1
                continue
            if not location_ok((j.get("location") or {}).get("name", "")):
                counts["foreign"] = counts.get("foreign", 0) + 1
                continue
            upd = (j.get("updated_at") or "")[:10]
            if upd:
                try:
                    age = (now - datetime.fromisoformat(upd).replace(tzinfo=timezone.utc)).days
                    if age > max_age_days:
                        counts["stale"] += 1
                        continue
                except ValueError:
                    pass
            matches.append(j)
        if not matches:
            time.sleep(0.3)
            continue
        # fetch full JDs only for boards with matches
        content = {}
        try:
            dc = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
            content = {j["id"]: j.get("content", "") for j in dc.get("jobs", [])}
        except Exception:
            pass
        for j in matches:
            job = {
                "title": j.get("title", ""), "company": slug,
                "location": (j.get("location") or {}).get("name", ""),
                "url": j.get("absolute_url", ""),
                "description": strip_html(content.get(j.get("id"), "")),
                "date_posted": (j.get("updated_at") or "")[:10],
                "source": "greenhouse-wide",
            }
            key = dedup_key(job["title"], job["company"])
            row = {"url": job["url"], "first_seen": today, "source": "greenhouse-wide",
                   "title": job["title"], "company": slug, "location": job["location"]}
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
        time.sleep(0.3)

    save_cache(cache)
    append_history(history_rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"ghwide_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(out, "w") as f:
        json.dump(fresh, f, indent=2)
    print(f"Greenhouse-wide sweep: {counts['companies']} boards ({counts['dead']} dead) | "
          f"raw {counts['raw']} | new {counts['new']} | title-skip {counts['title']} | "
          f"stale {counts['stale']} | dup {counts['dup']} | filtered {counts['skip']} → {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true", help="mine slugs from Common Crawl")
    parser.add_argument("--crawls", type=int, default=1, help="how many recent crawls to mine")
    parser.add_argument("--sweep", type=int, default=0, metavar="N", help="check N cached companies")
    parser.add_argument("--max-age-days", type=float, default=3)
    args = parser.parse_args()
    if args.discover:
        discover(args.crawls)
    if args.sweep:
        sweep(args.sweep, args.max_age_days)
    if not args.discover and not args.sweep:
        parser.print_help()


if __name__ == "__main__":
    main()
