# Synced from SeismoHub (tests/test_fullbundle_harvest.py; github.com/WANGYuhan2002/seismohub). Do not edit it here:
# change it upstream and re-sync (CONTRIBUTING.md).
"""Offline tests of the harvest engine (extracted from SeismoHub's tests/test_fullbundle_harvest.py).

No network: HTTP is faked. PDFs are generated with PyMuPDF. SeismoHub's database tests are not part of this file.
"""
from __future__ import annotations

import json

import pytest

fitz = pytest.importorskip("fitz")

from paper_pdf_harvest import fullbundle_harvest as fb  # noqa: E402


# --- from SeismoHub tests/test_fullbundle_harvest.py ---

TITLE = "Fluid-Controlled Tidal Modulation of Aftershocks Following the Noto Earthquake"


DOI = "10.1029/2026GL125440"


def make_pdf(title: str, *, pages: int = 4, doi: str = "", filler: str = "seismic velocity tomography") -> bytes:
    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page()
        y = 40
        if index == 0:
            page.insert_text((36, y), title, fontsize=9)
            y += 14
            if doi:
                page.insert_text((36, y), f"https://doi.org/{doi}", fontsize=8)
                y += 14
        while y < 780:
            page.insert_text((36, y), (filler + " ") * 4, fontsize=6)
            y += 9
    data = doc.tobytes()
    doc.close()
    return data


class FakeHttp:
    """Minimal PoliteSession stand-in: longest-prefix URL routing, records calls."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, *, headers=None, sensitive_headers=(), max_bytes=0, retries=1):
        self.calls.append(url)
        for prefix in sorted(self.routes, key=len, reverse=True):
            if url.startswith(prefix):
                status, data, extra = self.routes[prefix]
                return fb.HttpResult(url=url, status=status, final_url=url, data=data,
                                     headers=dict(extra or {}), content_type="")
        return fb.HttpResult(url=url, status=404, final_url=url)


def openalex_json(locations, oa_status="closed"):
    return json.dumps({"id": "https://openalex.org/W1", "title": TITLE,
                       "open_access": {"oa_status": oa_status}, "locations": locations}).encode()


@pytest.fixture(autouse=True)
def _hermetic_keys(tmp_path, monkeypatch):
    """Never read the developer's real ~/.config/seismo_harvester/keys.env, and make sure anything
    load_harvest_keys() puts into os.environ is removed again after each test."""
    monkeypatch.setattr(fb, "DEFAULT_KEYS_FILE", tmp_path / "no-such-keys.env")
    for name in ("WILEY_TDM_TOKEN", "ELSEVIER_API_KEY", "ELSEVIER_INSTTOKEN", "SEISMO_HARVEST_KEYS_FILE"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def wiley_token(monkeypatch):
    monkeypatch.setenv("WILEY_TDM_TOKEN", "test-token")


def test_inspect_pdf_gates():
    html = b"<!DOCTYPE html><html><body>Just a moment...</body></html>"
    assert fb.inspect_pdf(html).outcome == fb.NO_PDF_BUT_HTML
    preview = make_pdf(TITLE, pages=1)
    check = fb.inspect_pdf(preview, min_bytes=0)
    assert not check.ok and check.outcome == fb.AUTH_REQUIRED and check.reason == "too_few_pages_1"
    full = make_pdf(TITLE, pages=4)
    check = fb.inspect_pdf(full, min_bytes=0)
    assert check.ok and check.pages == 4 and "Tidal Modulation" in check.head_text
    assert not fb.inspect_pdf(full, min_bytes=10_000_000).ok  # size floor


def test_identity_check_title_doi_and_mismatch():
    text = TITLE + "\nsome body text"
    assert fb.identity_check(text, doi=DOI, title=TITLE)[0]
    # DOI split across lines still counts, but alone needs a looser title match
    assert fb.identity_check("Fluid tidal aftershocks\n https://doi.org/10.1029/\n2026GL125440", doi=DOI, title=TITLE)[0]
    ok, why = fb.identity_check("A completely different paper about glaciers", doi=DOI, title=TITLE)
    assert not ok and why.startswith("identity_mismatch")
    # a merely CITED DOI on an unrelated page is not enough
    ok, _ = fb.identity_check("Glacier calving dynamics\nref: https://doi.org/10.1029/2026GL125440", doi=DOI, title=TITLE)
    assert not ok


def test_tier_for_uses_the_downloaded_copy_not_oa_status():
    assert fb.tier_for("tdm_vor", "", "") == (fb.TIER_TDM, "tdm-licence")
    assert fb.tier_for("tdm_vor", "", "cc-by") == (fb.TIER_OPEN, "cc-by")          # hybrid OA via TDM
    assert fb.tier_for("open_copy", "", "")[0] == fb.TIER_OPEN                     # repository / preprint
    assert fb.tier_for("publisher_copy", "", "") [0] == fb.TIER_TDM               # bronze / subscription
    assert fb.tier_for("open_vor", "cc-by-nc-nd", "") == (fb.TIER_OPEN, "cc-by-nc-nd")


def test_green_paper_fetched_via_tdm_is_not_marked_open(wiley_token):
    """Regression for the original script: oa_status=='green' made a TDM publisher PDF 'OPEN'."""
    locations = [
        {"version": "publishedVersion", "license": None, "pdf_url": None, "source": {"type": "journal"}},
        {"version": "acceptedVersion", "license": None, "pdf_url": None, "source": {"type": "repository"}},
    ]
    http = FakeHttp({
        "https://api.openalex.org/": (200, openalex_json(locations, oa_status="green"), {}),
        "https://api.wiley.com/": (200, make_pdf(TITLE, doi=DOI), {}),
    })
    out = fb.FullBundleHarvester(http, min_bytes=0).harvest(fb.PaperRef("p1", doi=DOI, title=TITLE))
    assert out.app_hit is None and out.held_hit is not None
    assert out.held_hit.tier == fb.TIER_TDM and out.status == fb.HELD_TDM_ONLY


def test_tdm_vor_is_held_and_open_copy_is_attached(wiley_token):
    locations = [
        {"version": "publishedVersion", "license": None, "pdf_url": None, "source": {"type": "journal"}},
        {"version": "acceptedVersion", "license": None, "pdf_url": "https://repo.example.org/am.pdf",
         "source": {"type": "repository", "display_name": "Some Repository"}},
    ]
    http = FakeHttp({
        "https://api.openalex.org/": (200, openalex_json(locations, "green"), {}),
        "https://api.wiley.com/": (200, make_pdf(TITLE, doi=DOI, filler="version of record"), {}),
        "https://repo.example.org/am.pdf": (200, make_pdf(TITLE, filler="accepted manuscript"), {}),
    })
    out = fb.FullBundleHarvester(http, min_bytes=0).harvest(fb.PaperRef("p1", doi=DOI, title=TITLE))
    assert out.held_hit.channel == "wiley_tdm" and out.held_hit.tier == fb.TIER_TDM
    assert out.app_hit.channel == "openalex_repo" and out.app_hit.tier == fb.TIER_OPEN
    assert out.status == fb.SUCCESS

    out2 = fb.FullBundleHarvester(http, min_bytes=0, attach_tdm=True).harvest(fb.PaperRef("p1", doi=DOI, title=TITLE))
    assert out2.app_hit.channel == "wiley_tdm" and out2.held_hit is None


def test_crossref_vor_licence_upgrades_publisher_copy(wiley_token):
    """Brand-new paper: OpenAlex 404 (not indexed yet) but the publisher registered CC-BY for the VoR."""
    crossref = json.dumps({"message": {"license": [
        {"URL": "http://onlinelibrary.wiley.com/termsAndConditions#vor", "content-version": "tdm"},
        {"URL": "http://creativecommons.org/licenses/by/4.0/", "content-version": "vor",
         "start": {"date-parts": [[2026, 11, 7]]}},
    ]}}).encode()
    http = FakeHttp({
        "https://api.openalex.org/": (404, b"", {}),
        "https://api.wiley.com/": (200, make_pdf(TITLE, doi=DOI), {}),
        "https://api.crossref.org/works/": (200, crossref, {}),
    })
    out = fb.FullBundleHarvester(http, min_bytes=0).harvest(fb.PaperRef("p1", doi=DOI, title=TITLE))
    assert out.app_hit is not None and out.held_hit is None
    assert out.app_hit.tier == fb.TIER_OPEN and out.app_hit.license == "cc-by"
    assert [a.channel for a in out.pdf_attempts] == ["wiley_tdm"]  # metadata lookups are not PDF attempts


def test_crossref_licence_rules():
    today = fb._dt.date(2026, 11, 8)
    future = {"license": [{"URL": "https://creativecommons.org/licenses/by/4.0/", "content-version": "vor",
                           "start": {"date-parts": [[2027, 5, 1]]}}]}
    tdm_only = {"license": [{"URL": "https://creativecommons.org/licenses/by/4.0/", "content-version": "am"},
                            {"URL": "https://www.elsevier.com/tdm/userlicense/1.0/", "content-version": "tdm"}]}
    assert fb.crossref_vor_cc_license(future, today) == ""      # embargoed: not open yet
    assert fb.crossref_vor_cc_license(tdm_only, today) == ""    # CC only for the accepted manuscript
    assert fb.cc_label_from_url("https://creativecommons.org/licenses/by-nc-nd/4.0/") == "cc-by-nc-nd"
    assert fb.cc_label_from_url("https://creativecommons.org/publicdomain/zero/1.0/") == "cc0"


def test_wrong_paper_is_rejected(wiley_token):
    http = FakeHttp({
        "https://api.openalex.org/": (200, openalex_json([]), {}),
        "https://api.wiley.com/": (200, make_pdf("Glacier calving and ice shelf collapse"), {}),
    })
    out = fb.FullBundleHarvester(http, min_bytes=0).harvest(fb.PaperRef("p1", doi=DOI, title=TITLE))
    assert out.app_hit is None and out.held_hit is None
    assert any("identity_mismatch" in a.reason for a in out.attempts)


ELS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<full-text-retrieval-response xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">
<coredata><prism:doi>{doi}</prism:doi><dc:title>{title}</dc:title></coredata>
<objects>
<object ref="gr1" category="high" type="IMAGE-HIGH-RES" mimetype="image/jpeg" width="2000" height="1500">https://api.elsevier.com/content/object/eid/1-s2.0-S0040195126000001-gr1_lrg.jpg?httpAccept=%2A%2F%2A</object>
<object ref="gr1" category="thumbnail" type="IMAGE-THUMBNAIL" mimetype="image/gif">https://api.elsevier.com/content/object/eid/1-s2.0-S0040195126000001-gr1.sml?httpAccept=%2A%2F%2A</object>
</objects>
<originalText><xocs:doc><xocs:meta><xocs:attachment-eid>1-s2.0-S0040195126000001-mmc1.xlsx</xocs:attachment-eid></xocs:meta>
<ce:sections><ce:section><ce:section-title>Introduction</ce:section-title><ce:para>{body}</ce:para></ce:section></ce:sections>
</xocs:doc></originalText></full-text-retrieval-response>"""


def test_elsevier_preview_circuit_breaker(monkeypatch):
    monkeypatch.setenv("ELSEVIER_API_KEY", "k")
    monkeypatch.delenv("WILEY_TDM_TOKEN", raising=False)
    http = FakeHttp({
        "https://api.openalex.org/": (200, openalex_json([]), {}),
        "https://api.elsevier.com/": (200, make_pdf(TITLE, pages=1), {}),  # previews, and no XML full text
    })
    harvester = fb.FullBundleHarvester(http, min_bytes=0, elsevier_preview_breaker=2)
    for i in range(3):
        out = harvester.harvest(fb.PaperRef(f"p{i}", doi=f"10.1016/j.tecto.2026.{i}", title=TITLE))
        assert out.app_hit is None and out.held_hit is None and out.held_xml is None
    pdf_calls = [c for c in http.calls if "httpAccept=application/pdf" in c]
    xml_calls = [c for c in http.calls if "httpAccept=text/xml" in c]
    assert len(pdf_calls) == 2 and len(xml_calls) == 2  # third paper skipped without any Elsevier request
    assert "previews" in harvester.elsevier_disabled_reason
    assert "not entitled from this network" in harvester.elsevier_xml_disabled_reason


def test_elsevier_breaker_still_fetches_open_access_pdfs(monkeypatch):
    """The 2026-11-08 run tripped the breaker on 3 subscribed papers and then skipped the OA ones too."""
    monkeypatch.setenv("ELSEVIER_API_KEY", "k")
    oa_doi = "10.1016/j.epsl.2026.9"
    oa_work = json.dumps({"id": "https://openalex.org/W9", "title": TITLE, "open_access": {"oa_status": "hybrid"},
                          "locations": [{"version": "publishedVersion", "license": "cc-by", "pdf_url": None,
                                         "landing_page_url": f"https://doi.org/{oa_doi}",
                                         "source": {"type": "journal"}}]}).encode()
    http = FakeHttp({
        "https://api.openalex.org/": (200, openalex_json([]), {}),
        f"https://api.openalex.org/works/doi:{oa_doi}": (200, oa_work, {}),
        "https://api.elsevier.com/": (200, make_pdf(TITLE, pages=1), {}),
        f"https://api.elsevier.com/content/article/doi/{oa_doi}?httpAccept=application/pdf":
            (200, make_pdf(TITLE, doi=oa_doi), {}),
    })
    harvester = fb.FullBundleHarvester(http, min_bytes=0, elsevier_preview_breaker=2)
    for i in range(3):
        harvester.harvest(fb.PaperRef(f"p{i}", doi=f"10.1016/j.tecto.2026.{i}", title=TITLE))
    assert harvester.elsevier_disabled_reason
    out = harvester.harvest(fb.PaperRef("oa", doi=oa_doi, title=TITLE))
    assert out.status == fb.SUCCESS
    assert out.app_hit is not None and out.app_hit.channel == "elsevier_tdm" and out.app_hit.tier == fb.TIER_OPEN


def test_elsevier_xml_for_another_doi_is_rejected(monkeypatch):
    monkeypatch.setenv("ELSEVIER_API_KEY", "k")
    doi = "10.1016/j.tecto.2026.2"
    xml = ELS_XML.format(doi="10.1016/j.tecto.2026.999", title=TITLE, body="seismic velocity tomography " * 400)
    http = FakeHttp({
        "https://api.openalex.org/": (200, openalex_json([]), {}),
        "https://api.elsevier.com/content/article/doi/": (200, make_pdf(TITLE, pages=1), {}),
        f"https://api.elsevier.com/content/article/doi/{doi}?httpAccept=text/xml": (200, xml.encode(), {}),
    })
    out = fb.FullBundleHarvester(http, min_bytes=0).harvest(fb.PaperRef("pY", doi=doi, title=TITLE))
    assert out.held_xml is None and out.status != fb.HELD_TDM_ONLY
    assert any(a.channel == "elsevier_tdm_xml" and "identity_mismatch" in a.reason for a in out.attempts)


def test_bot_walled_host_is_never_requested():
    locations = [{"version": "publishedVersion", "license": "cc-by", "source": {"type": "journal"},
                  "pdf_url": "https://academic.oup.com/gji/article-pdf/doi/10.1093/gji/x/1/x.pdf"}]
    http = FakeHttp({"https://api.openalex.org/": (200, openalex_json(locations, "gold"), {})})
    out = fb.FullBundleHarvester(http, min_bytes=0, channels=["openalex"]).harvest(
        fb.PaperRef("p1", doi="10.1093/gji/x", title=TITLE))
    assert not any("academic.oup.com" in c for c in http.calls)
    assert out.status == fb.CAPTCHA_OR_BOT_BLOCK


def test_url_rules():
    assert fb.copernicus_pdf_url("10.5194/tc-20-6283-2026")[0] == \
        "https://tc.copernicus.org/articles/20/6283/2026/tc-20-6283-2026.pdf"
    assert fb.copernicus_pdf_url("10.5194/egusphere-2026-1357")[0].endswith(
        "/preprints/2026/egusphere-2026-1357/egusphere-2026-1357.pdf")
    assert fb.copernicus_pdf_url("10.5194/egusphere-egu24-1234") == ("", "")  # GA abstract, not a paper
    assert fb.arxiv_id_from("", "https://arxiv.org/abs/2607.07654v1") == "2607.07654"
    assert fb.arxiv_id_from("10.48550/arXiv.2607.07654") == "2607.07654"
    assert fb.nature_pdf_url("10.1038/s43247-026-04207-2") == "https://www.nature.com/articles/s43247-026-04207-2.pdf"
    assert fb.normalize_doi("https://doi.org/10.1029/X.") == "10.1029/X"
    assert fb.normalize_license_label("Creative Commons Attribution 4.0 International") == "cc-by"
    assert not fb._wanted_supplement("41467_2026_77203_MOESM4_ESM.mp4")
    assert fb._wanted_supplement("1-s2.0-S0012821X20306282-mmc1.pdf")


def test_egu_review_regex_matches_real_uppercase_links():
    page = (
        '<a href="https://se.copernicus.org/preprints/se-2020-151/se-2020-151-RC1.pdf">'
        '<a href="https://se.copernicus.org/preprints/se-2020-151/se-2020-151-AC2-print.pdf">'
        '<a href="https://egusphere.copernicus.org/preprints/2026/egusphere-2026-1357/egusphere-2026-1357-RC1-supplement.pdf">'
        '<a href="https://se.copernicus.org/preprints/se-2020-151/se-2020-151-AR1.pdf">'
        '<a href="https://se.copernicus.org/articles/12/1/2021/se-12-1-2021.pdf">'
    )
    found = fb.EGU_REVIEW_PDF_RE.findall(page)
    assert len(found) == 4 and not any(f.endswith("se-12-1-2021.pdf") for f in found)


def test_elsevier_attachment_eid_regex_handles_namespace():
    xml = ("<xocs:attachment-eid>1-s2.0-S0012821X20306282-mmc1.pdf</xocs:attachment-eid>"
           "<attachment-eid>1-s2.0-S0012821X20306282-gr1.jpg</attachment-eid>")
    assert fb.ELSEVIER_ATTACHMENT_EID_RE.findall(xml) == [
        "1-s2.0-S0012821X20306282-mmc1.pdf", "1-s2.0-S0012821X20306282-gr1.jpg"]


def test_code_and_data_scan_finds_data_availability_links():
    doc = fitz.open()
    for i in range(4):
        page = doc.new_page()
        page.insert_text((36, 60), "Introduction text " * 5, fontsize=8)
        if i == 2:
            page.insert_text((36, 120), "Data Availability Statement", fontsize=9)
            page.insert_text((36, 135), "Code: https://github.com/swp-eth/dasnoise and 10.5281/zenodo.1234567.", fontsize=8)
    data = doc.tobytes()
    doc.close()
    urls = {e["url"] for e in fb.scan_pdf_for_code_data_urls(data)}
    assert "https://github.com/swp-eth/dasnoise" in urls
    assert "https://doi.org/10.5281/zenodo.1234567" in urls


class _Resp:
    def __init__(self, status, headers=None, body=b""):
        self.status_code, self.headers, self._body = status, headers or {}, body

    def iter_content(self, chunk_size=65536):
        yield self._body

    def close(self):
        pass


def test_sensitive_headers_dropped_on_cross_domain_redirect():
    session = fb.PoliteSession(sleep=lambda s: None)
    seen = []

    def fake_get(url, headers=None, **kwargs):
        seen.append((url, dict(headers or {})))
        if url.startswith("https://api.wiley.com/"):
            return _Resp(302, {"Location": "https://alm.wiley.com/file.pdf"})
        if url.startswith("https://alm.wiley.com/"):
            return _Resp(302, {"Location": "https://cdn.example.net/file.pdf"})
        return _Resp(200, {"Content-Type": "application/pdf"}, b"%PDF-1.7 body")

    session.session.get = fake_get
    res = session.get("https://api.wiley.com/x", headers={"Wiley-TDM-Client-Token": "secret"},
                      sensitive_headers=("Wiley-TDM-Client-Token",))
    assert res.ok and res.final_url == "https://cdn.example.net/file.pdf"
    assert "Wiley-TDM-Client-Token" in seen[1][1]          # same registered domain: kept
    assert "Wiley-TDM-Client-Token" not in seen[2][1]      # left wiley.com: dropped


def test_load_harvest_keys_never_overrides_environment(tmp_path, monkeypatch):
    keys = tmp_path / "keys.env"
    keys.write_text('export WILEY_TDM_TOKEN="from-file"\nexport ELSEVIER_API_KEY="els-file"\nexport OTHER="x"\n')
    monkeypatch.setenv("WILEY_TDM_TOKEN", "from-env")
    monkeypatch.delenv("ELSEVIER_API_KEY", raising=False)
    monkeypatch.delenv("OTHER", raising=False)
    monkeypatch.setenv("SEISMO_HARVEST_KEYS_FILE", str(keys))
    assert fb.load_harvest_keys() == {"WILEY_TDM_TOKEN": True, "ELSEVIER_API_KEY": True}
    import os
    assert os.environ["WILEY_TDM_TOKEN"] == "from-env" and os.environ["ELSEVIER_API_KEY"] == "els-file"
    assert "OTHER" not in os.environ  # only the known key names are imported


def test_load_harvest_keys_treats_an_empty_variable_as_unset(tmp_path, monkeypatch):
    """A 'WILEY_TDM_TOKEN=' line copied into .env (python-dotenv sets "") must not shadow keys.env (2026-11-13)."""
    import os
    keys = tmp_path / "keys.env"
    keys.write_text('export WILEY_TDM_TOKEN="from-file"\n')
    monkeypatch.setenv("WILEY_TDM_TOKEN", "")
    monkeypatch.setenv("ELSEVIER_API_KEY", "  ")
    monkeypatch.setenv("SEISMO_HARVEST_KEYS_FILE", str(keys))
    assert fb.load_harvest_keys() == {"WILEY_TDM_TOKEN": True, "ELSEVIER_API_KEY": False}
    assert os.environ["WILEY_TDM_TOKEN"] == "from-file"
    assert "ELSEVIER_API_KEY" not in os.environ  # blank and in no keys file: unset, not "  "
