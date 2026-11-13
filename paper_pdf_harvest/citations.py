# Synced from SeismoHub (scripts/harvest_literature_list.py; github.com/WANGYuhan2002/seismohub). Do not edit it here:
# change it upstream and re-sync (CONTRIBUTING.md).
"""Resolve reading-list entries (DOI, arXiv ID, URL or free-form citation) to metadata through Crossref / arXiv
(extracted from SeismoHub's scripts/harvest_literature_list.py).
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List

from . import fullbundle_harvest as fb


# --- from SeismoHub scripts/harvest_literature_list.py ---

_DOI_EXTRACT_RE = re.compile(r"\b(10\.\d{4,9}/[^\s,;\"'<>]+)", re.I)


_ARXIV_EXTRACT_RE = re.compile(r"(?:arxiv[:\s/]+|abs/|pdf/)(\d{4}\.\d{4,6}|[a-z-]+/\d{7})(?:v\d+)?", re.I)


def _clean_slug(text: str, max_len: int = 64) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip()).strip("-")
    return s[:max_len] or "paper"


def resolve_citation_to_metadata(http: fb.PoliteSession, raw_spec: str) -> Dict[str, Any]:
    """Resolve a free-form DOI, arXiv ID, URL, or bibliographic query (e.g. 'Aki 1957 space and time spectra')
    into `{doi, arxiv_id, title, journal, year, authors, link}` via Crossref / arXiv."""
    spec = (raw_spec or "").strip()
    if not spec:
        return {}

    # 1. Explicit arXiv ID or URL
    m_ax = _ARXIV_EXTRACT_RE.search(spec)
    if m_ax and "10." not in spec:
        aid = m_ax.group(1)
        return {
            "doi": f"10.48550/arXiv.{aid}" if "." in aid else "",
            "arxiv_id": aid,
            "title": "",
            "journal": "arXiv",
            "year": "",
            "authors": [],
            "link": f"https://arxiv.org/abs/{aid}",
        }

    # 2. Explicit DOI (including old Wiley/Elsevier parentheses DOIs like `10.1016/0031-9201(81)90046-7`)
    m_doi = _DOI_EXTRACT_RE.search(spec)
    doi = fb.normalize_doi(m_doi.group(1).rstrip(".,;]")) if m_doi else ""

    if doi:
        cr = http.get(
            f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/()')}",
            headers={"Accept": "application/json"},
        )
        if cr.ok:
            try:
                msg = (cr.json() or {}).get("message") or {}
                return _meta_from_crossref_msg(msg, fallback_doi=doi)
            except Exception:
                pass
        return {"doi": doi, "arxiv_id": "", "title": "", "journal": "", "year": "", "authors": [], "link": f"https://doi.org/{doi}"}

    # 3. Bibliographic citation / title query via Crossref (`query.bibliographic`)
    q_url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": spec, "rows": "3"})
    res = http.get(q_url, headers={"Accept": "application/json"})
    if res.ok:
        try:
            items = ((res.json() or {}).get("message") or {}).get("items") or []
        except Exception:
            items = []
        for it in items:
            if it.get("type") in ("component", "dataset", "peer-review", "journal-issue"):
                continue
            cand = _meta_from_crossref_msg(it)
            if cand.get("doi") and cand.get("title"):
                return cand
    return {"doi": "", "arxiv_id": "", "title": spec, "journal": "", "year": "", "authors": [], "link": ""}


def _meta_from_crossref_msg(msg: Dict[str, Any], fallback_doi: str = "") -> Dict[str, Any]:
    doi = fb.normalize_doi(str(msg.get("DOI") or fallback_doi))
    title = html_strip(((msg.get("title") or [""])[0] or ""))
    journal = html_strip(((msg.get("container-title") or [""])[0] or ""))
    year = ""
    for k in ("published-print", "published-online", "issued", "created"):
        parts = (((msg.get(k) or {}).get("date-parts") or [[None]])[0]) or [None]
        if parts and parts[0]:
            year = str(parts[0])
            break
    authors: List[str] = []
    for a in (msg.get("author") or []):
        fam = str(a.get("family") or "").strip()
        giv = str(a.get("given") or "").strip()
        if fam:
            authors.append(f"{giv} {fam}".strip())
    return {
        "doi": doi,
        "arxiv_id": "",
        "title": title,
        "journal": journal,
        "year": year,
        "authors": authors,
        "link": f"https://doi.org/{doi}" if doi else "",
    }


def html_strip(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", (text or "")).split())
