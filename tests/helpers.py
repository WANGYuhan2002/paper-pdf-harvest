"""Offline test helpers: a routing fake for the HTTP session and generated PDFs."""
from __future__ import annotations

import json
from typing import Dict, Sequence, Tuple

import fitz

from paper_pdf_harvest import fullbundle_harvest as fb


def make_pdf(title: str, *, doi: str = "", lines: Sequence[str] = (), pages: int = 4) -> bytes:
    """A PDF that passes gates 1-3 (>= 40 KB, >= 3 pages, >= 5000 characters) with *title* on page 1."""
    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page()
        y = 40
        if index == 0:
            page.insert_text((36, y), title, fontsize=10)
            y += 14
            if doi:
                page.insert_text((36, y), f"https://doi.org/{doi}", fontsize=8)
                y += 12
            for line in lines:
                page.insert_text((36, y), line, fontsize=8)
                y += 12
        while y < 780:
            page.insert_text((36, y), "seismic rupture tomography attenuation wavefield " * 3, fontsize=6)
            y += 9
    data = doc.tobytes(deflate=False)
    doc.close()
    assert pages < 3 or len(data) >= 40_000  # 1-2 page stubs are meant to fail the gates
    return data


class FakeHttp:
    """Stand-in for PoliteSession: longest-prefix routing, records every requested URL and its headers."""

    def __init__(self, routes: Dict[str, Tuple]):
        self.routes = routes
        self.calls = []
        self.headers = []

    def get(self, url, *, headers=None, sensitive_headers=(), max_bytes=0, retries=1):
        self.calls.append(url)
        self.headers.append(dict(headers or {}))
        for prefix in sorted(self.routes, key=len, reverse=True):
            if url.startswith(prefix):
                status, body, *extra = self.routes[prefix]
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                return fb.HttpResult(url=url, status=status, final_url=url, data=data,
                                     headers=dict(extra[0]) if extra else {}, content_type="")
        return fb.HttpResult(url=url, status=404, final_url=url)


def crossref_message(doi: str, title: str, *, journal: str, year: int, authors: Sequence[str],
                     licences: Sequence[dict] = ()) -> dict:
    return {"message": {
        "DOI": doi, "title": [title], "container-title": [journal], "type": "journal-article",
        "published-print": {"date-parts": [[year, 1, 1]]},
        "author": [{"given": a.split()[0], "family": a.split()[-1]} for a in authors],
        "license": list(licences)}}


def openalex_work(title: str, locations: Sequence[dict] = (), oa_status: str = "closed") -> dict:
    return {"id": "https://openalex.org/W123", "title": title, "open_access": {"oa_status": oa_status},
            "locations": list(locations)}


def arxiv_atom(title: str, authors: Sequence[str], year: int) -> bytes:
    names = "".join(f"<author><name>{a}</name></author>" for a in authors)
    return (f'<?xml version="1.0"?><feed><title>arXiv Query</title><entry><title>{title}</title>'
            f"<published>{year}-01-15T00:00:00Z</published>{names}</entry></feed>").encode()
