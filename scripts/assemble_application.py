#!/usr/bin/env python3
"""
Deterministic application.json assembler (AGENT.md v3).

Takes a per-job strategy config (the LLM's judgement, expressed compactly) and
assembles the tailored application.json from bullet_bank.json + resume.json —
guaranteeing bullet counts, always_include presence, anchor survival, and order.

Config schema (JSON):
{
  "slug": "acme",                        # output/{slug}/
  "company": "Acme", "title": "Senior Frontend Engineer", "url": "https://...",
  "summary": "…2-3 sentences…",
  "bullets_pinestack": ["ps-…", x16],    # ordered ids from bullet_bank
  "bullets_symanto":  ["sy-…", x6],
  "rewrites": {"ps-…": "rewritten text (anchors must survive)"},
  "skills": [{"category": "…", "items": ["…"]}],
  "keywords": {"matched": [...], "missing": [...], "caveat": "..."}
}

Usage: python3 scripts/assemble_application.py config.json
Writes: output/{slug}/application.json + output/{slug}/keyword_report.json
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = json.load(open(sys.argv[1]))
    bank = json.load(open(REPO / "bullet_bank.json"))
    base = json.load(open(REPO / "resume.json"))

    bullets = {b["id"]: b for co in ("pinestack", "symanto") for b in bank[co]["bullets"]}

    for co, key in (("pinestack", "bullets_pinestack"), ("symanto", "bullets_symanto")):
        ids = cfg[key]
        want = bank[co]["required_count"]
        if len(ids) != want:
            sys.exit(f"FATAL: {co} needs {want} bullets, config has {len(ids)}")
        if len(set(ids)) != len(ids):
            sys.exit(f"FATAL: duplicate ids in {key}")
        required = {b["id"] for b in bank[co]["bullets"] if b.get("always_include")}
        missing = required - set(ids)
        if missing:
            sys.exit(f"FATAL: {co} missing always_include bullets: {missing}")

    def text_for(bid: str) -> str:
        text = cfg.get("rewrites", {}).get(bid, bullets[bid]["text"])
        for anchor in bullets[bid].get("anchors", []):
            if anchor.lower() not in text.lower():
                sys.exit(f"FATAL: rewrite of {bid} lost anchor {anchor!r}")
        return text

    app = {
        "personal_info": {**base["personal_info"],
                          "authorization": "US Work Authorized (No Sponsorship)"},
        "summary": cfg["summary"],
        "experience": [
            {**{k: v for k, v in base["experience"][0].items() if k != "highlights"},
             "highlights": [text_for(i) for i in cfg["bullets_pinestack"]]},
            {**{k: v for k, v in base["experience"][1].items() if k != "highlights"},
             "highlights": [text_for(i) for i in cfg["bullets_symanto"]]},
        ],
        "skills": cfg["skills"],
        "education": base["education"],
    }

    out_dir = REPO / "output" / cfg["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "application.json", "w") as f:
        json.dump(app, f, indent=2)

    kw = cfg.get("keywords", {})
    total = len(kw.get("matched", [])) + len(kw.get("missing", []))
    report = {
        "company": cfg["company"], "title": cfg["title"], "job_url": cfg.get("url", ""),
        "workplace": cfg.get("workplace", "Remote"),
        "ats_keyword_coverage_pct": round(100 * len(kw.get("matched", [])) / total) if total else None,
        "matched_keywords": kw.get("matched", []),
        "missing_keywords": kw.get("missing", []),
        "caveat": kw.get("caveat", ""),
    }
    with open(out_dir / "keyword_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"assembled: {out_dir}/application.json ({cfg['company']} — {cfg['title']})")


if __name__ == "__main__":
    main()
