# Synced from SeismoHub (.claude/skills/seismohub-pdf-harvest/scripts/harvest_status.py; github.com/WANGYuhan2002/seismohub). Do not edit it here:
# change it upstream and re-sync (CONTRIBUTING.md).
"""Summaries of harvest reports from their metadata only (extracted from SeismoHub's harvest_status.py).

Nothing here opens a PDF or an XML file, so licensed full text is never read. URLs are shown as host + path only,
so no token-bearing query string is ever printed.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# --- from SeismoHub .claude/skills/seismohub-pdf-harvest/scripts/harvest_status.py ---

NEXT_STEP = {
    "success": "nothing to do",
    "held_tdm_only": "licensed copy kept in tdm_bundles/ (local reading only); --retry-failed later for an open copy",
    "captcha_or_bot_block": "publisher blocks scripts: download in a browser, then paper-pdf-harvest triage",
    "no_pdf_but_html": "host served HTML (e.g. PMC): open the link in a browser and save the PDF",
    "auth_required": "login wall: browser download from a network with access",
    "no_oa_copy": "no open copy found: browser download, author page or repository",
    "transient_error": "timeouts / HTTP 5xx: rerun with --retry-failed later",
    "unsupported": "not attachable (duplicate, not a paper, or rejected format)",
    "unsupported_content_type": "rejected format: usually a dataset or software record",
}


def host_path(url: str) -> str:
    """Host + path only. Query strings are dropped so no token-bearing parameter is ever printed."""
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.netloc}{parts.path}" if parts.netloc else url.split("?", 1)[0]


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def matches(row: Dict[str, Any], args: argparse.Namespace) -> bool:
    if args.doi and (row.get("doi") or "").lower() not in {d.lower() for d in args.doi}:
        return False
    if args.paper_id and str(row.get("paper_id") or "") not in set(args.paper_id):
        return False
    if args.journal and not any(j.lower() in (row.get("journal") or "").lower() for j in args.journal):
        return False
    return True


def outcome_channel(row: Dict[str, Any]) -> str:
    for key in ("app_copy", "held_copy", "held_xml"):
        part = row.get(key)
        if isinstance(part, dict) and part.get("channel"):
            return str(part["channel"])
    return ""


# Outcome of one report row, best first. Merging several reports keeps the best outcome per paper
# (a paper attached in an earlier run stays attached even if a later run skipped it).
OUTCOMES = (
    ("attached", "open copy saved / attached"),
    ("already_had_pdf", "already had a PDF"),
    ("duplicate", "same PDF already on another paper"),
    ("held", "held licensed copy (local only)"),
    ("not_attached", "verified copy not attached"),
    ("no_full_text", "no full text yet"),
)


RANK = {key: len(OUTCOMES) - i for i, (key, _label) in enumerate(OUTCOMES)}


def outcome(row: Dict[str, Any]) -> str:
    reason = str(row.get("attach_reason") or "")
    if row.get("attached"):
        return "attached"
    if reason.startswith("already_has_pdf"):
        return "already_had_pdf"
    if reason.startswith(("same_pdf_already_attached_to", "inferred_doi_already_attached_to")):
        return "duplicate"
    if row.get("held_copy") or row.get("held_xml"):
        return "held"
    if row.get("app_copy"):
        return "not_attached"
    return "no_full_text"


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    outcomes = Counter(outcome(r) for r in rows)
    missing = [r for r in rows if outcome(r) == "no_full_text"]
    missing_status = Counter(r.get("status") or "unknown" for r in missing)
    attached = Counter(outcome_channel(r) for r in rows if outcome(r) == "attached")
    held = Counter(outcome_channel(r) or "unknown" for r in rows if outcome(r) == "held")
    missing_journals = Counter((r.get("journal") or "unknown") for r in missing)
    failures: Counter = Counter()
    for r in missing:
        for a in r.get("attempts") or []:
            if a.get("outcome") and a.get("outcome") != "success":
                host = urllib.parse.urlsplit(a.get("url") or "").netloc or a.get("channel") or "?"
                failures[f"{a['outcome']} @ {host}"] += 1
    return {
        "papers": len(rows),
        "outcomes": {key: outcomes.get(key, 0) for key, _label in OUTCOMES},
        "no_full_text_by_status": dict(missing_status.most_common()),
        "attached_by_channel": dict(attached.most_common()),
        "held_by_channel": dict(held.most_common()),
        "no_full_text_by_journal": dict(missing_journals.most_common(10)),
        "top_failures": dict(failures.most_common(8)),
    }


def print_summary(label: str, summary: Dict[str, Any]) -> None:
    print(f"{label}  ({summary['papers']} papers)")
    labels = dict(OUTCOMES)
    for key, value in summary["outcomes"].items():
        if value:
            print(f"  {labels[key]:<34} {value:>5}")
    if summary["attached_by_channel"]:
        print("attached open copies by channel: "
              + ", ".join(f"{k}={v}" for k, v in summary["attached_by_channel"].items()))
    if summary["held_by_channel"]:
        print("held licensed copies (local only) by channel: "
              + ", ".join(f"{k}={v}" for k, v in summary["held_by_channel"].items()))
    if summary["no_full_text_by_status"]:
        print("no full text yet, by status:")
        for key, value in summary["no_full_text_by_status"].items():
            print(f"  {key:<26} {value:>5}   {NEXT_STEP.get(key, '')}")
        print("  by journal: " + ", ".join(f"{k} ({v})" for k, v in summary["no_full_text_by_journal"].items()))
        if summary["top_failures"]:
            print("  most common failed attempts:")
            for key, value in summary["top_failures"].items():
                print(f"    {value:>4}  {key}")


def print_attempts(rows: Iterable[Dict[str, Any]]) -> None:
    for r in rows:
        print(f"\n{r.get('doi') or r.get('paper_id')}  [{r.get('status')}]  {(r.get('title') or '')[:90]}")
        if r.get("reason"):
            print(f"  reason: {r['reason']}")
        for key in ("app_copy", "held_copy"):
            part = r.get(key)
            if isinstance(part, dict):
                print(f"  {key}: {part.get('channel')} {part.get('license_tier')} {part.get('pages')}p "
                      f"licence={part.get('license')} from {host_path(part.get('source_url') or '')}")
        for a in r.get("attempts") or []:
            http = f" HTTP {a['http_status']}" if a.get("http_status") else ""
            print(f"  - {a.get('channel', ''):<14} {a.get('outcome', ''):<24}{http}  {host_path(a.get('url') or '')}"
                  + (f"  ({a['reason'][:120]})" if a.get("reason") else ""))
