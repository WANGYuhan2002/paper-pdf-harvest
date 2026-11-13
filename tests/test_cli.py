"""End-to-end tests of the standalone command line, fully offline (fake HTTP, generated PDFs)."""
from __future__ import annotations

import builtins
import csv
import json
import os
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

from helpers import FakeHttp, arxiv_atom, crossref_message, make_pdf, openalex_work  # noqa: E402
from paper_pdf_harvest import cli  # noqa: E402
from paper_pdf_harvest import fullbundle_harvest as fb  # noqa: E402

TOKEN = "test-wiley-token-value-7f3a"

ARXIV_ID = "2401.00001"
ARXIV_TITLE = "Ambient Noise Tomography of the Alpine Crust from Dense Nodal Arrays"
WILEY_DOI = "10.1029/2026JB000001"
WILEY_TITLE = "Fault Zone Healing Revealed by Repeating Earthquakes in Southern Iceland"
GSW_DOI = "10.1785/0120260001"
GSW_TITLE = "Ground Motion Amplification in Sedimentary Basins of the Rhine Graben"
SCIENCE_DOI = "10.1126/science.1108339"
SCIENCE_TITLE = "High-Resolution Surface-Wave Tomography from Ambient Seismic Noise"
CITATION = "Shapiro Campillo 2005 ambient noise surface wave tomography"


def routes() -> dict:
    wiley_pdf = make_pdf(WILEY_TITLE, doi=WILEY_DOI, lines=(
        "(c) 2026 American Geophysical Union. All rights reserved.",))
    return {
        # arXiv: metadata from the API, PDF from the export mirror
        "https://export.arxiv.org/api/query?": (200, arxiv_atom(ARXIV_TITLE, ["Ana Lopez", "Ben Kim"], 2024)),
        f"https://export.arxiv.org/pdf/{ARXIV_ID}": (200, make_pdf(ARXIV_TITLE)),
        # Wiley / AGU subscription article: the TDM API serves the publisher PDF -> licensed, held
        f"https://api.crossref.org/works/{WILEY_DOI}": (200, crossref_message(
            WILEY_DOI, WILEY_TITLE, journal="JGR Solid Earth", year=2026, authors=["Kari Olsen", "Jon Arason"])),
        f"https://api.openalex.org/works/doi:{WILEY_DOI}": (200, openalex_work(WILEY_TITLE)),
        "https://api.wiley.com/onlinelibrary/tdm/v1/articles/": (200, wiley_pdf),
        # GeoScienceWorld: the only copy sits on a bot-walled host -> never requested, pending
        f"https://api.crossref.org/works/{GSW_DOI}": (200, crossref_message(
            GSW_DOI, GSW_TITLE, journal="BSSA", year=2026, authors=["Lea Weber"])),
        f"https://api.openalex.org/works/doi:{GSW_DOI}": (200, openalex_work(GSW_TITLE, [{
            "pdf_url": "https://pubs.geoscienceworld.org/ssa/bssa/article-pdf/116/1/1/x.pdf",
            "version": "publishedVersion", "license": None,
            "source": {"type": "journal", "display_name": "BSSA"}}])),
        # a citation resolved through Crossref, open copy in a repository
        "https://api.crossref.org/works?query.bibliographic=": (200, {"message": {"items": [
            dict(crossref_message(SCIENCE_DOI, SCIENCE_TITLE, journal="Science", year=2005,
                                  authors=["Nikolai Shapiro", "Michel Campillo"])["message"])]}}),
        f"https://api.crossref.org/works/{SCIENCE_DOI}": (200, crossref_message(
            SCIENCE_DOI, SCIENCE_TITLE, journal="Science", year=2005, authors=["Nikolai Shapiro", "Michel Campillo"])),
        f"https://api.openalex.org/works/doi:{SCIENCE_DOI}": (200, openalex_work(SCIENCE_TITLE, [{
            "pdf_url": "https://repository.example.edu/bitstream/shapiro2005.pdf", "version": "acceptedVersion",
            "license": None, "source": {"type": "repository", "display_name": "Example Repository"}}])),
        "https://repository.example.edu/bitstream/shapiro2005.pdf": (200, make_pdf(SCIENCE_TITLE)),
    }


def reading_list(tmp_path: Path) -> Path:
    path = tmp_path / "reading_list.txt"
    path.write_text("\n".join([
        "# my reading list", f"arXiv:{ARXIV_ID}", WILEY_DOI, f"https://doi.org/{GSW_DOI}", CITATION,
        "zzzz qqqq unfindable citation", ""]), encoding="utf-8")
    return path


def harvest(tmp_path: Path, http: FakeHttp, *extra: str) -> int:
    return cli.main(["harvest", "--input-file", str(reading_list(tmp_path)), "--out-dir", str(tmp_path / "pack"),
                     "--no-extras", *extra], http=http)


def summary(pack: Path) -> dict:
    """harvest_summary.tsv rows by DOI (lower case), or by key for entries without one."""
    with open(pack / cli.SUMMARY_FILE, encoding="utf-8") as fh:
        return {(row["doi"].lower() or row["key"]): row for row in csv.DictReader(fh, delimiter="\t")}


@pytest.fixture()
def harvested(tmp_path, monkeypatch):
    monkeypatch.setenv("WILEY_TDM_TOKEN", TOKEN)
    http = FakeHttp(routes())
    assert harvest(tmp_path, http) == 0
    return tmp_path / "pack", http


def test_harvest_sorts_copies_by_licence(harvested):
    pack, http = harvested
    rows = summary(pack)
    assert rows[f"10.48550/arxiv.{ARXIV_ID}"]["status"] == "open_pdf"
    assert rows[f"10.48550/arxiv.{ARXIV_ID}"]["key"] == f"arxiv:{ARXIV_ID}"
    assert rows[SCIENCE_DOI]["status"] == "open_pdf"  # citation resolved through Crossref
    assert rows[SCIENCE_DOI]["query"] == CITATION
    assert rows[WILEY_DOI.lower()]["status"] == "held_tdm_only"
    assert rows[GSW_DOI]["status"] == fb.CAPTCHA_OR_BOT_BLOCK
    unresolved = [r for r in rows.values() if r["status"] == "unresolved_citation"]
    assert [r["query"] for r in unresolved] == ["zzzz qqqq unfindable citation"]  # not matched to a random paper

    # only OPEN copies are in open_pdfs/; the licensed one is in its bundle, marked as such
    assert len(list((pack / cli.OPEN_DIR).glob("*.pdf"))) == 2
    bundle = pack / cli.TDM_DIR / "PaperBundle_10.1029_2026JB000001"
    manifest = json.loads((bundle / "bundle_manifest.json").read_text(encoding="utf-8"))
    assert manifest["main_manuscript"]["license_tier"] == fb.TIER_TDM
    assert manifest["main_manuscript"]["hosted_ai_upload_allowed"] is False
    assert (bundle / "main_manuscript.pdf").is_file()
    assert not Path(manifest["app_attached"]["pdf_path"] or "rel").is_absolute()  # no home path in manifests

    # bot-walled host never requested; the key went out as a header but is written nowhere
    assert not any("geoscienceworld" in url for url in http.calls)
    assert any(h.get("Wiley-TDM-Client-Token") == TOKEN for h in http.headers)
    for path in pack.rglob("*"):
        if path.is_file():
            assert TOKEN.encode() not in path.read_bytes(), path

    with open(pack / cli.PENDING_FILE, encoding="utf-8-sig") as fh:
        pending = {r["doi"] or r["title"]: r for r in csv.DictReader(fh)}
    assert pending[GSW_DOI]["status"] == fb.CAPTCHA_OR_BOT_BLOCK
    assert "browser" in pending[GSW_DOI]["suggestion"] and pending[GSW_DOI]["open_url"].endswith(GSW_DOI)
    assert len(pending) == 2  # the bot-walled paper and the unresolved citation


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("WILEY_TDM_TOKEN", TOKEN)
    assert harvest(tmp_path, FakeHttp(routes()), "--dry-run") == 0
    assert not (tmp_path / "pack").exists()


def test_rerun_resumes_and_retry_failed_retries(harvested, tmp_path):
    pack, _ = harvested
    lines_before = (pack / cli.REPORT_FILE).read_text(encoding="utf-8").count("\n")
    again = FakeHttp(routes())
    assert harvest(tmp_path, again) == 0
    assert again.calls == []  # finished, held and not-yet-due papers are skipped without any request
    assert (pack / cli.REPORT_FILE).read_text(encoding="utf-8").count("\n") == lines_before

    retry = FakeHttp(routes())
    assert harvest(tmp_path, retry, "--retry-failed") == 0
    assert any(GSW_DOI in url for url in retry.calls)
    assert not any(ARXIV_ID in url for url in retry.calls)  # finished papers stay skipped
    assert len(list((pack / cli.OPEN_DIR).glob("*.pdf"))) == 2  # nothing duplicated


def test_attach_tdm_is_sealed(tmp_path, capsys):
    assert cli.main(["harvest", "--doi", WILEY_DOI, "--out-dir", str(tmp_path / "pack"), "--attach-tdm"]) == 3
    assert "sealed" in capsys.readouterr().err
    assert not (tmp_path / "pack").exists()


def test_keys_reports_presence_never_values(tmp_path, monkeypatch, capsys):
    keys = tmp_path / "keys.env"
    keys.write_text(f'export ELSEVIER_API_KEY="{TOKEN}-els"\n', encoding="utf-8")
    monkeypatch.setenv("WILEY_TDM_TOKEN", TOKEN)
    assert cli.main(["keys", "--keys-file", str(keys)]) == 0
    out = capsys.readouterr().out
    assert TOKEN not in out
    assert "WILEY_TDM_TOKEN      set" in out and "ELSEVIER_API_KEY     set" in out
    assert "OPENALEX_API_KEY     not set" in out


@pytest.fixture()
def keys_file_and_default(tmp_path, monkeypatch):
    """WILEY_TDM_TOKEN in the default keys file and in a --keys-file, with different values."""
    default = tmp_path / "default_keys.env"
    default.write_text(f'export WILEY_TDM_TOKEN="{TOKEN}-default"\n', encoding="utf-8")
    monkeypatch.setattr(fb, "DEFAULT_KEYS_FILE", default)
    keys = tmp_path / "keys.env"
    keys.write_text(f'export WILEY_TDM_TOKEN="{TOKEN}-keys-file"\n', encoding="utf-8")
    return keys


def test_keys_file_beats_the_default_keys_file(keys_file_and_default, tmp_path, capsys):
    """docs/KEYS.md: $SEISMO_HARVEST_KEYS_FILE, then --keys-file, then ~/.config/seismo_harvester/keys.env. The
    upgrade layer loads the keys files when it is installed, and a loaded key is never overridden, so --keys-file
    has to reach it."""
    http = FakeHttp(routes())
    assert cli.main(["harvest", "--doi", WILEY_DOI, "--out-dir", str(tmp_path / "pack"), "--dry-run",
                     "--keys-file", str(keys_file_and_default)], http=http) == 0
    sent = {h["Wiley-TDM-Client-Token"] for h in http.headers if "Wiley-TDM-Client-Token" in h}
    assert sent == {f"{TOKEN}-keys-file"}
    captured = capsys.readouterr()
    assert TOKEN not in captured.out + captured.err


def test_keys_command_reads_the_keys_file_first(keys_file_and_default, capsys):
    assert cli.main(["keys", "--keys-file", str(keys_file_and_default)]) == 0
    assert os.environ["WILEY_TDM_TOKEN"] == f"{TOKEN}-keys-file"
    assert TOKEN not in capsys.readouterr().out


def test_status_reads_metadata_only(harvested, monkeypatch, capsys):
    pack, _ = harvested
    real_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        if str(file).lower().endswith((".pdf", ".xml")):
            raise AssertionError(f"status opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(fitz, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fitz.open")))
    assert cli.main(["status", str(pack), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["papers"] == 5
    assert data["outcomes"]["attached"] == 2 and data["outcomes"]["held"] == 1
    assert data["attached_by_channel"] == {"arxiv": 1, "openalex_repo": 1}
    assert cli.main(["status", str(pack), "--pending", "--attempts"]) == 0
    text = capsys.readouterr().out
    assert "pending browser downloads" in text and TOKEN not in text


def test_triage_routes_browser_downloads_by_licence(harvested, tmp_path):
    pack, _ = harvested
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "gsw.pdf").write_bytes(make_pdf(GSW_TITLE, doi=GSW_DOI, lines=(
        "Downloaded from https://pubs.geoscienceworld.org/ssa/bssa/article-pdf/116/1/1/x.pdf "
        "by Example University user on 11 November 2026",)))
    (downloads / "author_copy.pdf").write_bytes(make_pdf(WILEY_TITLE, doi=WILEY_DOI, lines=(
        "This is an open access article under the terms of the Creative Commons Attribution License.",)))
    (downloads / "unrelated.pdf").write_bytes(make_pdf("Glacier Calving Dynamics on Svalbard Tidewater Fronts"))
    (downloads / "stub.pdf").write_bytes(make_pdf(GSW_TITLE, pages=1))
    report_lines = (pack / cli.REPORT_FILE).read_text(encoding="utf-8").count("\n")
    open_before = sorted(p.name for p in (pack / cli.OPEN_DIR).iterdir())

    assert cli.main(["triage", str(downloads), "--pack", str(pack)]) == 0  # dry run
    assert (pack / cli.REPORT_FILE).read_text(encoding="utf-8").count("\n") == report_lines
    assert sorted(p.name for p in (pack / cli.OPEN_DIR).iterdir()) == open_before
    assert not (pack / cli.TDM_DIR / "PaperBundle_10.1785_0120260001").exists()

    assert cli.main(["triage", str(downloads), "--pack", str(pack), "--commit"]) == 0
    rows = summary(pack)
    assert rows[GSW_DOI]["status"] == "held_tdm_only"  # institution download stamp -> licensed
    assert rows[WILEY_DOI.lower()]["status"] == "open_pdf"  # CC statement on the PDF -> open
    manifest = json.loads((pack / cli.TDM_DIR / "PaperBundle_10.1785_0120260001" / "bundle_manifest.json")
                          .read_text(encoding="utf-8"))
    assert manifest["main_manuscript"]["hosted_ai_upload_allowed"] is False
    assert len(list((pack / cli.OPEN_DIR).glob("*.pdf"))) == 3
    with open(pack / cli.PENDING_FILE, encoding="utf-8-sig") as fh:
        assert [r["status"] for r in csv.DictReader(fh)] == ["unresolved_citation"]


def test_triage_needs_a_pack(tmp_path, capsys):
    (tmp_path / "empty_pack").mkdir()
    assert cli.main(["triage", str(tmp_path), "--pack", str(tmp_path / "empty_pack")]) == 2
    assert "run `paper-pdf-harvest harvest" in capsys.readouterr().err


def test_render_xml_keeps_the_copy_licensed(tmp_path):
    bundle = tmp_path / "pack" / cli.TDM_DIR / "PaperBundle_10.1016_j.epsl.2026.000001"
    bundle.mkdir(parents=True)
    paragraphs = "".join(f"<ce:para>Paragraph {i} about crustal seismic velocity changes after the earthquake, "
                         f"observed with ambient noise interferometry over several years.</ce:para>" for i in range(80))
    (bundle / "main_manuscript.xml").write_text(
        "<full-text-retrieval-response><prism:doi>10.1016/j.epsl.2026.000001</prism:doi>"
        "<ce:title>Velocity Changes After a Large Earthquake</ce:title>"
        f"<ce:sections><ce:section-title>Introduction</ce:section-title>{paragraphs}</ce:sections>"
        "</full-text-retrieval-response>", encoding="utf-8")
    (bundle / "bundle_manifest.json").write_text(json.dumps(
        {"doi": "10.1016/j.epsl.2026.000001", "main_manuscript": {"license_tier": fb.TIER_TDM}}), encoding="utf-8")
    assert cli.main(["render-xml", str(tmp_path / "pack")]) == 0
    with fitz.open(str(bundle / "main_manuscript.pdf")) as doc:
        assert "LICENSED TDM COPY" in doc[0].get_text()
    manifest = json.loads((bundle / "bundle_manifest.json").read_text(encoding="utf-8"))
    assert manifest["rendered_tdm_pdf"]["hosted_ai_upload_allowed"] is False


def test_reading_list_parsing(tmp_path):
    bib = tmp_path / "export.bib"
    bib.write_text("@article{k1, title={A Paper}, doi={10.5194/se-17-1-2026},\n}\n"
                   "@article{k2, title={No Doi Paper About Slow Slip Events},\n author={Smith, Jane and Doe, J},\n"
                   " date={2025},\n}\n", encoding="utf-8")
    table = tmp_path / "list.csv"
    table.write_text("doi,title\n10.5194/se-17-1-2026,A Paper\nhttps://arxiv.org/abs/2310.01234v2,x\n",
                     encoding="utf-8")
    specs = cli.load_specs(["10.48550/arXiv.2310.01234"], [], [str(bib), str(table)])
    assert [cli.spec_key(s) for s in specs] == [
        "arxiv:2310.01234", "doi:10.5194/se-17-1-2026", cli.spec_key("No Doi Paper About Slow Slip Events Smith 2025")]
    assert cli.spec_key("2310.01234") == "arxiv:2310.01234"  # October IDs are arXiv IDs, not DOIs
