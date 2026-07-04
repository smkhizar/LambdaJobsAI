#!/usr/bin/env python3
"""
LambdaJobsAI Unified Job Scraper Pipeline
==========================================
JobSpy (Indeed + LinkedIn + Google Jobs) sweep with staffing blacklist,
title filtering, cross-run dedup via data/scan_history.tsv, and JSON output
ready for triage.

Run with the toolkit interpreter (see SCRAPING.md — NOT plain `python3`):
  /opt/homebrew/bin/python3.12 scripts/scrapers/unified_job_scraper.py [--hours 24] [--per-query 25] [--priority 3]

Output:
  data/scraped_jobs/jobs_YYYYMMDD_HHMM.json   (new, deduped, filtered jobs)
  data/scan_history.tsv                        (append-only history of every seen job)

Deps (see SCRAPING.md for the version-check protocol):
  pip install "git+https://github.com/speedyapply/JobSpy.git@main"   # python-jobspy
  # PITFALL: `pip install jobspy` from PyPI is a DIFFERENT package (Redis queue)
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_DIR / "data" / "scraped_jobs"
HISTORY_PATH = REPO_DIR / "data" / "scan_history.tsv"
HISTORY_FIELDS = ["url", "first_seen", "source", "title", "company", "status", "location"]

SEARCH_QUERIES_PRIORITY = [
    # Priority 1 (highest)
    ("Software Engineer", 1),
    ("Full Stack Developer", 1),
    ("Frontend Engineer", 1),
    ("Frontend Developer", 1),
    ("React Developer", 1),
    ("React TypeScript Developer", 1),
    ("TypeScript Engineer", 1),
    ("JavaScript Engineer", 1),
    ("Web Application Developer", 1),
    # Priority 2
    ("Senior Frontend Engineer", 2),
    ("Senior Full Stack Engineer", 2),
    ("Senior Software Engineer", 2),
    # Priority 3
    ("React Native Developer", 3),
    ("Mobile Software Engineer", 3),
    # Priority 4
    ("Node.js Developer", 4),
    ("Backend Engineer Node.js", 4),
    # Priority 5
    ("AI Software Engineer", 5),
    ("Generative AI Engineer", 5),
]

STAFFING_BLACKLIST = {
    "insight global", "agiliko", "cybercoders", "teksystems", "robert half",
    "kelly services", "randstad", "manpower", "aerotek", "collabera",
    "mastech", "kforce", "hays", "capgemini", "infosys", "tata consultancy",
    "wipro", "hcl", "cognizant", "accenture", "deloitte", "ibm consulting",
    "tech mahindra", "mindtree", "mphasis", "judge group", "droisys",
    "revature", "synergisticit", "simplilearn", "genzeon", "disys",
    "system soft technologies", "prolifics", "spectrum", "newpage digital",
    "dataannotation", "talentify", "dice", "techfetch", "cyberthink",
    "squadron", "logicplanet", "sigmaways", "mastech digital",
    "nelson", "motion recruitment", "lucas group", "creative circle", "epam",
}

SKIP_TITLE_KEYWORDS = {
    "staff ", "principal", "director", "vp ", "vice president",
    "head of", "intern", "co-op", "fellow",
    "data scientist", "ml research", "devops engineer",
    "sre ", "site reliability", "solutions architect",
    "wordpress", "php only", "ai trainer", "ai evaluator",
    "customer support", "technical support", "sales engineer",
}


def should_skip(title: str, company: str) -> str | None:
    """Return a skip status, or None if the job passes."""
    t, c = title.lower(), company.lower()
    if any(agency in c for agency in STAFFING_BLACKLIST):
        return "skipped_staffing"
    if any(kw in t for kw in SKIP_TITLE_KEYWORDS):
        return "skipped_title"
    return None


def normalize_title(title: str) -> str:
    """Strip trailing '— City, ST' noise so multi-city reposts dedupe."""
    return re.sub(r"\s*-\s*[A-Z][a-z]+.*,\s*[A-Z]{2}(?:,\s*USA)?$", "", title).strip()


def dedup_key(title: str, company: str) -> str:
    return f"{normalize_title(title).lower()}|{company.lower().strip()}"


def load_history() -> tuple[set[str], set[str]]:
    """Return (seen_urls, seen_company_title_keys) from scan_history.tsv."""
    urls: set[str] = set()
    keys: set[str] = set()
    if not HISTORY_PATH.exists():
        return urls, keys
    with open(HISTORY_PATH, newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            urls.add(row.get("url", ""))
            keys.add(dedup_key(row.get("title", ""), row.get("company", "")))
    return urls, keys


def append_history(rows: list[dict[str, str]]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not HISTORY_PATH.exists()
    with open(HISTORY_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS, delimiter="\t", extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def already_applied_slugs() -> set[str]:
    """Company slugs already tailored under output/ — never re-triage those."""
    out = REPO_DIR / "output"
    if not out.is_dir():
        return set()
    return {p.name.lower().replace("-", " ") for p in out.iterdir() if p.is_dir()}


def run_scrape(hours_old: int, per_query: int, max_priority: int) -> list[dict]:
    from jobspy import scrape_jobs  # import here so --help works without the dep

    jobs: list[dict] = []
    queries = [(q, p) for q, p in SEARCH_QUERIES_PRIORITY if p <= max_priority]
    for query, priority in queries:
        print(f"[scrape] p{priority} '{query}' ...", flush=True)
        try:
            df = scrape_jobs(
                site_name=["indeed", "linkedin", "google"],
                search_term=query,
                location="Remote",
                results_wanted=per_query,
                hours_old=hours_old,
                is_remote=True,
                country_indeed="usa",
            )
        except Exception as exc:  # one failed query must not kill the run
            print(f"[scrape]   query failed: {exc}", file=sys.stderr)
            continue
        for _, row in df.iterrows():
            jobs.append(
                {
                    "title": str(row.get("title") or ""),
                    "company": str(row.get("company") or ""),
                    "location": str(row.get("location") or ""),
                    "url": str(row.get("job_url") or ""),
                    "description": str(row.get("description") or ""),
                    "salary_min": row.get("min_amount"),
                    "salary_max": row.get("max_amount"),
                    "date_posted": str(row.get("date_posted") or ""),
                    "source": str(row.get("site") or "jobspy"),
                    "query": query,
                    "priority": priority,
                }
            )
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24, help="max posting age in hours")
    parser.add_argument("--per-query", type=int, default=25, help="results wanted per query")
    parser.add_argument("--priority", type=int, default=5, help="include queries up to this priority")
    args = parser.parse_args()

    seen_urls, seen_keys = load_history()
    applied = already_applied_slugs()

    raw = run_scrape(args.hours, args.per_query, args.priority)
    stamp = datetime.now().strftime("%Y-%m-%d")
    fresh: list[dict] = []
    history_rows: list[dict[str, str]] = []
    counts = {"raw": len(raw), "dup": 0, "staffing": 0, "title": 0, "invalid": 0, "applied": 0, "new": 0}
    batch_keys: set[str] = set()

    for job in raw:
        title, company, url = job["title"], job["company"], job["url"]
        row = {
            "url": url, "first_seen": stamp, "source": job["source"],
            "title": title, "company": company, "location": job["location"],
        }
        if not title or not company or len(job["description"]) < 50:
            counts["invalid"] += 1
            continue  # not even worth recording
        key = dedup_key(title, company)
        if url in seen_urls or key in seen_keys or key in batch_keys:
            counts["dup"] += 1
            continue  # already in history — don't re-append
        batch_keys.add(key)
        skip = should_skip(title, company)
        if skip:
            counts["staffing" if skip == "skipped_staffing" else "title"] += 1
            history_rows.append({**row, "status": skip})
            continue
        if company.lower().strip() in applied:
            counts["applied"] += 1
            history_rows.append({**row, "status": "skipped_dup"})
            continue
        counts["new"] += 1
        history_rows.append({**row, "status": "added"})
        fresh.append(job)

    append_history(history_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(out_path, "w") as f:
        json.dump(fresh, f, indent=2, default=str)

    print(
        f"\nScan {stamp}: raw {counts['raw']} | new {counts['new']} | "
        f"dup {counts['dup']} | staffing {counts['staffing']} | title-skip {counts['title']} | "
        f"already-applied {counts['applied']} | invalid {counts['invalid']}"
    )
    print(f"Output: {out_path}")
    print(f"History: {HISTORY_PATH}")


if __name__ == "__main__":
    main()
