# Synced from SeismoHub (scripts/harvest_pdfs.py; github.com/WANGYuhan2002/seismohub). Do not edit it here:
# change it upstream and re-sync (CONTRIBUTING.md).
"""The licence seal and the browser-download hints (extracted from SeismoHub's scripts/harvest_pdfs.py).

``keep_non_open_in_bundle`` is the last line of defence before anything is written to ``open_pdfs/``: only an
OPEN copy passes, and a publisher copy whose first pages say "All rights reserved" without an open-licence
statement is re-tiered to LICENSED_TDM_ONLY and kept in its bundle, whatever the licence metadata claims.
"""
from __future__ import annotations

import re

# ``harvest --attach-tdm`` refuses to run (exit 3) before it touches the network or any file.
ATTACH_TDM_SEALED_MESSAGE = (
    "--attach-tdm is sealed. TDM-licensed copies stay in tdm_bundles/ (local use only) and are never written to\n"
    "open_pdfs/ or handed to a hosted AI service. Nothing was read or written. Run without --attach-tdm.\n"
    "--attach-tdm 已封住：TDM 许可的全文只留在 tdm_bundles/（仅本地使用），不会写进 open_pdfs/，也不会交给云端 AI。\n"
    "本次没有读写任何东西。去掉 --attach-tdm 再运行。"
)


# --- from SeismoHub scripts/harvest_pdfs.py ---

# Sealed 2026-11-09 (owner: 「封住」). Re-opening needs the owner's OK *and* a TDM guard on every path that sends an
# attached PDF or its text to hosted AI (analyze step, PDF Q&A chat, manual upload / watch-folder flows).
ATTACH_TDM_SEALED_EXIT = 3


# A publisher copy whose first two pages say "All rights reserved" with no open-licence statement is licensed
# content, whatever the licence metadata says. Found 2026-11-09: OpenAlex + Unpaywall called 10.1029/2026JB034130
# (JGR Solid Earth) cc-by, while its Crossref deposit (Wiley terms + TDM licence) and the PDF itself
# ("(c) 2026 American Geophysical Union. All rights reserved") say it is a subscription article.
_RIGHTS_RESERVED = re.compile(r"all\s+rights\s+reserved", re.I)


_OPEN_STATEMENT = re.compile(
    r"creativecommons|creative\s+commons|open\s+access\s+article|this\s+is\s+an\s+open\s+access|"
    r"open\s+access\s+this\s+article|©\s*\d{4}\.?\s*the\s+authors?\b|\bthe\s+author\(s\)\s*\d{4}", re.I)


def pdf_says_rights_reserved(hit) -> bool:
    """True for a publisher copy (not a repository / preprint copy) whose first two pages say 'All rights
    reserved' and carry no open-licence statement, or whose text cannot be read."""
    if getattr(hit, "kind", "") == "open_copy":
        return False
    try:
        import fitz  # PyMuPDF; the harvester already uses it to verify every PDF

        with fitz.open(stream=hit.data, filetype="pdf") as doc:
            text = " ".join(doc[i].get_text() for i in range(min(2, doc.page_count)))
    except Exception:
        return True  # cannot confirm the licence -> keep it out of the app
    return bool(_RIGHTS_RESERVED.search(text)) and not _OPEN_STATEMENT.search(text)


def keep_non_open_in_bundle(fb, out) -> bool:
    """Last line of the seal: only an OPEN copy is ever attached, whatever patched the harvester and whatever
    the licence metadata claims.

    A non-OPEN copy, or a publisher copy whose PDF says 'All rights reserved' without an open-licence statement
    (re-tiered to TDM), moves to ``held_hit`` (bundle only) and the outcome becomes ``held_tdm_only``.
    Returns True if it acted.
    """
    hit = out.app_hit
    if hit is None:
        return False
    if hit.tier == fb.TIER_OPEN:
        if not pdf_says_rights_reserved(hit):
            return False
        hit.tier = fb.TIER_TDM
        hit.license = f"publisher-licensed (pdf: all rights reserved; metadata said {hit.license or 'open'})"
    if out.held_hit is None:
        out.held_hit = hit
    out.app_hit = None
    out.status = fb.HELD_TDM_ONLY
    out.reason = (f"{hit.channel} copy is {hit.tier} ({hit.license}); kept in bundle only "
                  "(sealed: TDM content never goes to open_pdfs/ or to hosted AI)")
    return True


def suggestion(fb, out) -> str:
    reasons = " ".join(a.reason for a in out.pdf_attempts)
    outcomes = {a.outcome for a in out.pdf_attempts}
    if out.doi.lower().startswith("10.1016/") and "elsevier" in reasons.lower():
        return ("Elsevier full text (XML) needs an institutional network: on an institutional network / VPN run "
                "paper-pdf-harvest harvest --out-dir <pack> --retry-failed ; the API never serves "
                "subscribed PDFs, so a readable PDF needs a browser on the institutional network")
    if fb.NO_PDF_BUT_HTML in outcomes:
        return ("an open copy exists but its host serves scripts an HTML page (e.g. PMC): open open_url in a "
                "browser, save the PDF, then paper-pdf-harvest triage")
    if fb.CAPTCHA_OR_BOT_BLOCK in outcomes:
        return ("publisher blocks scripts: download in a browser (Zotero Connector, institutional network), then "
                "paper-pdf-harvest triage matches them by DOI / title")
    if out.status == fb.NO_OA_COPY:
        return ("no open copy known (OpenAlex / arXiv / repositories): browser download, author page or "
                "repository, then paper-pdf-harvest triage")
    return "see attempts in the run report; retry later with --retry-failed"


def short(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"
