# Synced from SeismoHub (tests/test_harvest_pdfs_seal.py; github.com/WANGYuhan2002/seismohub). Do not edit it here:
# change it upstream and re-sync (CONTRIBUTING.md).
"""The licence seal (extracted from SeismoHub's tests/test_harvest_pdfs_seal.py).

A non-OPEN copy is never handed out as the open copy, and a publisher copy whose PDF says "All rights reserved"
without an open-licence statement is kept in the bundle whatever the licence metadata says.
"""
from __future__ import annotations

import pytest

fitz = pytest.importorskip("fitz")

from paper_pdf_harvest import fullbundle_harvest as fb  # noqa: E402
from paper_pdf_harvest import seal  # noqa: E402


def _load_cli():
    return seal  # SeismoHub tests the same functions through its CLI module


# --- from SeismoHub tests/test_harvest_pdfs_seal.py ---

def _pdf(*lines: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    for index, line in enumerate(lines):
        page.insert_text((36, 40 + 14 * index), line, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def _hit(data: bytes, *, tier: str = fb.TIER_OPEN, kind: str = "tdm_vor", channel: str = "wiley_tdm",
         license_: str = "cc-by") -> fb.PdfHit:
    return fb.PdfHit(channel=channel, url="https://x.org/a.pdf", data=data, pages=1, chars=100, kind=kind,
                     version="publishedVersion", license=license_, tier=tier, identity="title(1.00)")


def _outcome(hit: fb.PdfHit) -> fb.HarvestOutcome:
    return fb.HarvestOutcome(ref=fb.PaperRef("p1", doi="10.1029/x"), app_hit=hit, status=fb.SUCCESS)


RIGHTS_RESERVED = ("Seismic velocity changes after a large earthquake",
                   "(c) 2026 American Geophysical Union. All rights reserved, including rights for text and data mining.")


OPEN_ACCESS = ("Seismic velocity changes after a large earthquake",
               "This is an open access article under the terms of the Creative Commons Attribution License.")


def test_tdm_app_copy_is_kept_in_the_bundle_only():
    cli = _load_cli()
    out = _outcome(_hit(_pdf(*OPEN_ACCESS), tier=fb.TIER_TDM, license_="tdm-licence"))
    assert cli.keep_non_open_in_bundle(fb, out) is True
    assert out.app_hit is None
    assert out.held_hit.tier == fb.TIER_TDM
    assert out.status == fb.HELD_TDM_ONLY


def test_publisher_copy_saying_all_rights_reserved_is_kept_in_the_bundle():
    cli = _load_cli()
    out = _outcome(_hit(_pdf(*RIGHTS_RESERVED)))  # metadata said cc-by, the PDF says otherwise
    assert cli.keep_non_open_in_bundle(fb, out) is True
    assert out.app_hit is None and out.status == fb.HELD_TDM_ONLY
    assert out.held_hit.tier == fb.TIER_TDM
    assert out.held_hit.describe()["hosted_ai_upload_allowed"] is False
    assert "all rights reserved" in out.held_hit.license


def test_open_access_publisher_copy_is_attached():
    cli = _load_cli()
    hit = _hit(_pdf(*OPEN_ACCESS))
    out = _outcome(hit)
    assert cli.keep_non_open_in_bundle(fb, out) is False
    assert out.app_hit is hit and out.status == fb.SUCCESS and hit.tier == fb.TIER_OPEN


def test_repository_or_preprint_copy_is_not_held_for_a_copyright_line():
    cli = _load_cli()
    hit = _hit(_pdf(*RIGHTS_RESERVED), kind="open_copy", channel="arxiv", license_="repository-or-preprint")
    out = _outcome(hit)
    assert cli.keep_non_open_in_bundle(fb, out) is False
    assert out.app_hit is hit


def test_unreadable_publisher_copy_is_kept_out_of_the_app():
    cli = _load_cli()
    assert cli.pdf_says_rights_reserved(_hit(b"not a pdf")) is True
