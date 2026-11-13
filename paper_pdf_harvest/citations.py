# Synced from SeismoHub (scripts/harvest_literature_list.py; github.com/WANGYuhan2002/seismohub). Do not edit it here:
# change it upstream and re-sync (CONTRIBUTING.md).
"""Resolve reading-list entries (DOI, arXiv ID, URL or free-form citation) to metadata through Crossref / arXiv
(extracted from SeismoHub's scripts/harvest_literature_list.py).
"""
from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any, Dict, List

from . import fullbundle_harvest as fb


# --- from SeismoHub scripts/harvest_literature_list.py ---

_DOI_EXTRACT_RE = re.compile(r"\b(10\.\d{4,9}/[^\s,;\"'<>]+)", re.I)


_ARXIV_EXTRACT_RE = re.compile(r"(?:arxiv[:\s/]+|abs/|pdf/)(\d{4}\.\d{4,6}|[a-z-]+/\d{7})(?:v\d+)?", re.I)


# A new-style arXiv ID given on its own, e.g. "2310.01234" or "2310.01234v2" (use .match: the whole spec).
_BARE_ARXIV_RE = re.compile(r"(\d{4}\.\d{4,6})(?:v\d+)?$")


def _clean_slug(text: str, max_len: int = 64) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip()).strip("-")
    return s[:max_len] or "paper"


def arxiv_metadata(http: fb.PoliteSession, arxiv_id: str) -> Dict[str, Any]:
    """Title, authors and year of an arXiv preprint from the arXiv API (`export.arxiv.org/api/query?id_list=`).

    The title matters: the harvester does not ask OpenAlex about `10.48550` DOIs, so without it the identity check
    (gate 4) has nothing to compare the downloaded PDF with and rejects it as `identity_mismatch`."""
    meta: Dict[str, Any] = {
        "doi": f"10.48550/arXiv.{arxiv_id}" if _BARE_ARXIV_RE.match(arxiv_id) else "",
        "arxiv_id": arxiv_id,
        "title": "",
        "journal": "arXiv",
        "year": "",
        "authors": [],
        "link": f"https://arxiv.org/abs/{arxiv_id}",
    }
    res = http.get(
        "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": arxiv_id, "max_results": "1"}),
        headers={"Accept": "application/atom+xml"},
    )
    text = res.text() if res.ok else ""
    entry = text.split("<entry>", 1)[1] if "<entry>" in text else ""
    entry_id = re.search(r"<id>(.*?)</id>", entry, re.S)
    if entry_id and "/api/errors" in entry_id.group(1):  # the API answers a bad ID with an "Error" entry
        entry = ""
    title = re.search(r"<title[^>]*>(.*?)</title>", entry, re.S)
    if title:
        meta["title"] = " ".join(html.unescape(title.group(1)).split())
    meta["authors"] = [" ".join(html.unescape(name).split())
                       for name in re.findall(r"<name>(.*?)</name>", entry, re.S) if name.strip()]
    year = re.search(r"<published>(\d{4})", entry)
    if year:
        meta["year"] = year.group(1)
    return meta


CITATION_MIN_SHARE = 0.6  # share of the citation's words that the resolved Crossref record must contain


def citation_agrees(citation: str, meta: Dict[str, Any]) -> bool:
    """Does a Crossref record plausibly answer a free-form citation? Its title, authors, year and journal must contain
    most of the citation's words (at least two of them, and CITATION_MIN_SHARE). Crossref ranks *something* first
    for almost any query, so without this check an unknown or mistyped citation quietly fetches an unrelated paper."""
    words = [w for w in fb._tokens(citation) if len(w) >= 3 and w not in fb._STOPWORDS]
    if not words:
        return False
    record = " ".join([str(meta.get("title") or ""), str(meta.get("journal") or ""), str(meta.get("year") or ""),
                       " ".join(meta.get("authors") or [])])
    vocab = set(fb._tokens(record))
    hits = sum(1 for w in words if w in vocab)
    return hits >= min(2, len(words)) and hits / len(words) >= CITATION_MIN_SHARE


def resolve_citation_to_metadata(http: fb.PoliteSession, raw_spec: str) -> Dict[str, Any]:
    """Resolve a free-form DOI, arXiv ID, URL, or bibliographic query (e.g. 'Aki 1957 space and time spectra')
    into `{doi, arxiv_id, title, journal, year, authors, link}` via Crossref / arXiv.

    A DOI in the spec wins over an arXiv ID (it names the version of record), except an arXiv DOI
    (`10.48550/arXiv.<id>`), which is an arXiv ID. A free-form citation resolves only to a Crossref record that
    agrees with it (`citation_agrees`); otherwise the result has no DOI and the entry is reported as unresolved."""
    spec = (raw_spec or "").strip()
    if not spec:
        return {}

    m_doi = _DOI_EXTRACT_RE.search(spec)
    doi = fb.normalize_doi(m_doi.group(1).rstrip(".,;]")) if m_doi else ""

    # 1. arXiv: an arXiv DOI, or an arXiv ID / URL / bare ID in a spec without another DOI. (This used to test for
    #    "10." in the spec, which sent every October ID such as 2310.01234 to the Crossref query below.)
    if doi.lower().startswith(fb.ARXIV_DOI_PREFIX):
        return arxiv_metadata(http, re.sub(r"v\d+$", "", doi[len(fb.ARXIV_DOI_PREFIX):]))
    if not doi:
        m_ax = _ARXIV_EXTRACT_RE.search(spec) or _BARE_ARXIV_RE.match(spec)
        if m_ax:
            return arxiv_metadata(http, m_ax.group(1))

    # 2. Explicit DOI (including old Wiley/Elsevier parentheses DOIs like `10.1016/0031-9201(81)90046-7`)
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

    # 3. Bibliographic citation / title query via Crossref (`query.bibliographic`): the first record that agrees
    q_url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": spec, "rows": "5"})
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
            if cand.get("doi") and cand.get("title") and citation_agrees(spec, cand):
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
