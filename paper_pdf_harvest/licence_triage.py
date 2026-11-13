# Synced from SeismoHub (scripts/zotero_triage_import.py; github.com/WANGYuhan2002/seismohub). Do not edit it here:
# change it upstream and re-sync (CONTRIBUTING.md).
"""Licence triage for PDFs downloaded in a browser or with Zotero (extracted from SeismoHub's
scripts/zotero_triage_import.py).

Fail-closed: a publisher PDF is OPEN only when an open / Creative Commons statement on the PDF, a preprint DOI, or
verified open-access metadata backs it, and the PDF carries neither "All rights reserved" nor an institution
download stamp. Everything else is LICENSED_TDM_ONLY and stays local.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import fullbundle_harvest as fb
from . import pmc_oa_and_whitelist_channel as pw


# --- from SeismoHub scripts/zotero_triage_import.py ---

_RIGHTS_RESERVED_RE = re.compile(r"all\s+rights\s+reserved", re.I)


# A publisher's per-download stamp that names the subscribing institution, e.g. "Downloaded from
# https://academic.oup.com/... by <Institution> user on 09 November 2026" or "Downloaded from
# https://www.science.org at <Institution> on November 09, 2026". "by guest" (an anonymous, open download)
# does not count.
_INSTITUTION_STAMP_RE = re.compile(
    r"downloaded\s+from\s+\S+(?:\s+\S+){0,3}?\s+(?:by|at)\s+(?!guest\b)(?:the\s+)?\S.{0,120}?"
    r"\s(?:user\s+)?on\s+(?:\[|\d|[a-z]{3,9}\.?\s+\d)",
    re.I | re.S,
)


_OPEN_STATEMENT_RE = re.compile(
    r"creativecommons\.org|creative\s+commons|open\s+access\s+article|this\s+is\s+an\s+open\s+access|"
    r"open\s+access\s+this\s+article|cc[\s-]+by(?:\b|[\s-]+[0-9])|"
    r"©\s*\d{4}\.?\s*the\s+authors?\b|\bthe\s+author\(s\)\s*\d{4}",
    re.I,
)


_PREPRINT_DOI_PREFIXES = ("10.22541/essoar.", "10.31223/", "10.48550/arxiv.", "10.21203/rs.")


def inspect_pdf_license_signals(pdf_bytes: bytes) -> Dict[str, Any]:
    """Scan first 2 pages and last page of a PDF for explicit open/CC vs subscription/institution-stamp statements."""
    import fitz

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        n = doc.page_count
        idxs = sorted({i for i in (0, 1, n - 1) if 0 <= i < n})
        head_two = " ".join(doc[i].get_text("text") or "" for i in range(min(2, n)))
        sampled = " ".join(doc[i].get_text("text") or "" for i in idxs)

    has_open = bool(_OPEN_STATEMENT_RE.search(sampled))
    has_reserved = bool(_RIGHTS_RESERVED_RE.search(head_two))
    has_institution_stamp = bool(_INSTITUTION_STAMP_RE.search(sampled))
    cc_slug = fb.normalize_license_label(sampled) if "creative commons" in sampled.lower() or "creativecommons.org" in sampled.lower() else ""
    if cc_slug and not cc_slug.startswith("cc"):
        cc_slug = "cc-by"
    return {
        "has_open_statement": has_open,
        "has_rights_reserved": has_reserved,
        "has_institution_stamp": has_institution_stamp,
        "pdf_cc_slug": cc_slug,
    }


def classify_pdf_compliance(
    pdf_bytes: bytes,
    *,
    doi: str,
    journal: str = "",
    openalex_work: Optional[Dict[str, Any]] = None,
    crossref_vor_cc: str = "",
) -> Tuple[str, str, str, str]:
    """Decide `(tier, kind, license_slug, why)` for a browser/Zotero-saved PDF.

    Fail-closed: a publisher PDF only gets `TIER_OPEN` when positively backed by an open/CC statement,
    preprint prefix, or verified OA metadata WITHOUT `'All rights reserved'` / institutional subscription stamp.
    """
    clean_doi = fb.normalize_doi(doi or "")
    low_doi = clean_doi.lower()
    sig = inspect_pdf_license_signals(pdf_bytes)

    # 1. Preprints (ESSOAr, EarthArXiv, arXiv, Research Square) are open copies by repository policy
    if low_doi.startswith(_PREPRINT_DOI_PREFIXES):
        return fb.TIER_OPEN, "open_copy", sig["pdf_cc_slug"] or "preprint-open", "preprint_doi"

    # 2. Explicit Creative Commons / Open-Access statement printed on the PDF itself wins
    if sig["has_open_statement"]:
        lic = sig["pdf_cc_slug"] or "open-access-statement"
        return fb.TIER_OPEN, "open_vor", lic, f"pdf_carries_open_statement({lic})"

    # 3. Subscription markers without an open statement -> strictly TDM-only (same rules as SeismoHub's tdm_qa_guard)
    if sig["has_rights_reserved"]:
        return fb.TIER_TDM, "publisher_copy", "publisher-all-rights-reserved", "pdf_says_all_rights_reserved"
    if sig["has_institution_stamp"]:
        return fb.TIER_TDM, "publisher_copy", "licensed-browser-download", "pdf_carries_institution_download_stamp"

    # 4. Metadata-verified Gold/Hybrid CC VoR (when PDF has neither CC text nor 'All rights reserved'/institution download stamp)
    meta_lic = (
        fb.vor_open_license(openalex_work)
        or crossref_vor_cc
        or pw.infer_gold_oa_vor_license(doi=clean_doi, journal=journal, openalex_work=openalex_work)
    )
    if meta_lic and fb.is_open_license(meta_lic):
        return fb.TIER_OPEN, "open_vor", meta_lic, f"metadata_vor_open({meta_lic})"

    # 5. Default fail-closed: treat unverified publisher PDFs as institution-licensed TDM-only
    return fb.TIER_TDM, "publisher_copy", "publisher-licensed-unverified", "no_open_license_found_fail_closed"


def discover_input_pdfs(paths: Iterable[Path]) -> List[Tuple[Path, Optional[Dict[str, Any]]]]:
    """Collect `(pdf_path, optional_bib_entry)` from Zotero export folders, Zotero `storage/`, or plain dirs/files."""
    from .matching import parse_bib

    found: List[Tuple[Path, Optional[Dict[str, Any]]]] = []
    seen_paths: set[Path] = set()

    for raw_p in paths:
        p = raw_p.expanduser().resolve()
        if p.is_file() and p.suffix.lower() == ".pdf":
            if p not in seen_paths:
                seen_paths.add(p)
                found.append((p, None))
            continue
        if not p.is_dir():
            continue

        # 1) If folder has a Zotero `.bib`, parse structured entries first so BibTeX DOIs are authoritative
        bibs = sorted(p.glob("*.bib"))
        for bib in bibs:
            for entry in parse_bib(bib):
                rel = entry.get("file_rel") or ""
                if not rel:
                    continue
                cand = (p / rel).resolve()
                if cand.is_file() and cand.suffix.lower() == ".pdf" and cand not in seen_paths:
                    seen_paths.add(cand)
                    found.append((cand, entry))

        # 2) Also pick up any remaining `.pdf` files recursively (e.g. Zotero `storage/<8char>/*.pdf` or flat folder)
        for pdf_file in sorted(p.rglob("*.pdf")):
            rp = pdf_file.resolve()
            if rp not in seen_paths and not rp.name.startswith("._"):
                seen_paths.add(rp)
                found.append((rp, None))

    return found
