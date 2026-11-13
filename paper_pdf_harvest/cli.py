"""paper-pdf-harvest command line.

Commands
  harvest     DOIs / arXiv IDs / URLs / citations / a .bib export  ->  a pack folder
  triage      PDFs you downloaded in a browser or with Zotero      ->  the same pack, sorted by licence
  status      summarise a pack (or SeismoHub's paper_bundles/) from report metadata only
  keys        which keys and settings are configured (never their values)
  render-xml  turn Elsevier XML-only bundles into PDFs for local reading (still licensed: local only)

A pack folder holds:
  open_pdfs/            OPEN_CC_BY_OR_PREPRINT copies only (shareable; may go to hosted AI)
  tdm_bundles/          LICENSED_TDM_ONLY copies (publisher PDFs or Elsevier XML + figures): local use only
  open_bundles/         extras of open papers (supplements, review files, code/data links), when any were found
  harvest_report.jsonl  one JSON line per paper per run: status, reason, copies found, every attempt
  harvest_summary.tsv   current state, one row per paper
  pending_zotero.csv    papers still without full text: the browser / Zotero checklist
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import __version__
from . import citations, licence_triage, matching, report_summary, seal
from . import fullbundle_harvest as fb

REPORT_FILE = "harvest_report.jsonl"
SUMMARY_FILE = "harvest_summary.tsv"
PENDING_FILE = "pending_zotero.csv"
OPEN_DIR = "open_pdfs"
TDM_DIR = "tdm_bundles"
OPEN_BUNDLE_DIR = "open_bundles"
CACHE_FILE = "_metadata_cache.sqlite"
KEY_VARS = ("WILEY_TDM_TOKEN", "ELSEVIER_API_KEY", "ELSEVIER_INSTTOKEN", "OPENALEX_API_KEY")
SUMMARY_FIELDS = ["key", "query", "year", "first_author", "journal", "doi", "title", "status", "channel",
                  "open_pdf", "tdm_bundle", "open_bundle"]
PENDING_FIELDS = ["year", "first_author", "journal", "doi", "open_url", "title", "status", "suggestion"]
TOOL = f"paper-pdf-harvest/{__version__}"


# ---------------------------------------------------------------------------------------------------------------
# Settings and engine
# ---------------------------------------------------------------------------------------------------------------

def load_settings(env_file: str = "") -> Optional[Path]:
    """Load ``.env`` (default: ./.env) without overriding variables that are already set. Returns its path."""
    path = Path(env_file).expanduser() if env_file else Path.cwd() / ".env"
    if not path.is_file():
        if env_file:
            raise SystemExit(f"--env-file not found: {path}")
        return None
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - python-dotenv is a dependency
        return None
    load_dotenv(path, override=False)
    # An empty line copied from .env.example ("WILEY_TDM_TOKEN=") must not shadow the real value in keys.env:
    # load_harvest_keys never overrides a variable that already exists.
    for name in KEY_VARS + ("SEISMO_HARVEST_UA", "SEISMO_HARVEST_KEYS_FILE", "SEISMO_HARVEST_MAX_BYTES"):
        if name in os.environ and not os.environ[name].strip():
            del os.environ[name]
    return path


def install_upgrades(cache_path: Optional[Path], readonly: bool, keys_file: str = "") -> None:
    """Install SeismoHub's upgrade layer. It loads the keys files as it installs, in the order of docs/KEYS.md
    ($SEISMO_HARVEST_KEYS_FILE, ``keys_file``, ~/.config/seismo_harvester/keys.env), and a loaded key is never
    overridden later, so ``keys_file`` must be given here rather than only to ``key_presence``."""
    from . import upgrades

    upgrades.install_harvester_upgrades(fb, cache_path=cache_path, readonly=readonly,
                                        keys_files=[keys_file] if keys_file else [])


def build_harvester(*, cache_path: Optional[Path], readonly: bool, channels: Optional[Sequence[str]] = None,
                    download_code: bool = False, http: Any = None, keys_file: str = "") -> "fb.FullBundleHarvester":
    """The harvester with SeismoHub's upgrade layer installed (the same engine SeismoHub runs)."""
    install_upgrades(cache_path, readonly, keys_file)
    return fb.FullBundleHarvester(http, channels=channels, attach_tdm=False, download_code=download_code)


def key_presence(keys_file: str = "") -> Dict[str, bool]:
    """Load keys from the keys files (never overriding the environment); report which are set, never values."""
    fb.load_harvest_keys([keys_file] if keys_file else [])
    return {name: bool((os.environ.get(name) or "").strip()) for name in KEY_VARS}


# ---------------------------------------------------------------------------------------------------------------
# Reading lists
# ---------------------------------------------------------------------------------------------------------------

_HEADER_WORDS = re.compile(r"\b(?:doi|title|authors?|year|journal|url|arxiv)\b", re.I)
_NEW_ARXIV = re.compile(r"(\d{4}\.\d{4,6})(?:v\d+)?$")


def spec_key(spec: str) -> str:
    """Stable key of a reading-list entry: ``doi:<doi>``, ``arxiv:<id>`` or ``q:<hash of the citation>``."""
    text = (spec or "").strip()
    m = citations._DOI_EXTRACT_RE.search(text)
    if m:
        doi = fb.normalize_doi(m.group(1).rstrip(".,;]")).lower()
        if doi.startswith(fb.ARXIV_DOI_PREFIX):
            return "arxiv:" + re.sub(r"v\d+$", "", doi[len(fb.ARXIV_DOI_PREFIX):])
        return "doi:" + doi
    m = citations._ARXIV_EXTRACT_RE.search(text) or _NEW_ARXIV.match(text)
    if m:
        return "arxiv:" + m.group(1).lower()
    return "q:" + hashlib.sha1(" ".join(text.lower().split()).encode("utf-8")).hexdigest()[:12]


def _looks_like_header(line: str) -> bool:
    return (not citations._DOI_EXTRACT_RE.search(line) and not citations._ARXIV_EXTRACT_RE.search(line)
            and any(sep in line for sep in (",", "\t", ";")) and bool(_HEADER_WORDS.search(line)))


def load_specs(dois: Iterable[str], queries: Iterable[str], input_files: Iterable[str]) -> List[str]:
    """Reading-list entries in order, de-duplicated by key. ``.bib`` files are read entry by entry."""
    specs: List[str] = [v.strip() for v in list(dois) + list(queries) if v and v.strip()]
    for name in input_files:
        path = Path(name).expanduser()
        if not path.is_file():
            raise SystemExit(f"input file not found: {path}")
        if path.suffix.lower() == ".bib":
            for entry in matching.parse_bib(path):
                if entry.get("doi"):
                    specs.append(entry["doi"])
                elif entry.get("arxiv_id"):
                    specs.append(f"arXiv:{entry['arxiv_id']}")
                elif entry.get("title"):
                    first = (entry.get("authors") or "").split(" and ")[0].split(",")[0].strip()
                    specs.append(" ".join(x for x in (entry["title"], first, entry.get("year") or "") if x))
            continue
        first_content = True
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if first_content and _looks_like_header(line):
                first_content = False
                continue
            first_content = False
            specs.append(line)
    seen: set = set()
    out: List[str] = []
    for spec in specs:
        key = spec_key(spec)
        if key not in seen:
            seen.add(key)
            out.append(spec)
    return out


def resolve_citation(http: Any, citation: str) -> Dict[str, Any]:
    """Free-form citation -> the first Crossref record that agrees with it (``citations.citation_agrees``: most
    of the citation's words in its title, authors, year and journal), else nothing."""
    unresolved = {"doi": "", "arxiv_id": "", "title": "", "journal": "", "year": "", "authors": [], "link": ""}
    res = http.get("https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query.bibliographic": citation, "rows": "5"}), headers={"Accept": "application/json"})
    if not res.ok:
        return unresolved
    try:
        items = ((res.json() or {}).get("message") or {}).get("items") or []
    except ValueError:
        return unresolved
    for item in items:
        if item.get("type") in ("component", "dataset", "peer-review", "journal-issue"):
            continue
        meta = citations._meta_from_crossref_msg(item)
        if meta.get("doi") and meta.get("title") and citations.citation_agrees(citation, meta):
            return meta
    return unresolved


def resolve_spec(http: Any, spec: str) -> Dict[str, Any]:
    key = spec_key(spec)
    if key.startswith("arxiv:"):  # title from the arXiv API: the identity check (gate 4) compares it with the PDF
        return citations.arxiv_metadata(http, key[len("arxiv:"):])
    if key.startswith("doi:"):
        return citations.resolve_citation_to_metadata(http, spec)
    return resolve_citation(http, spec)


# ---------------------------------------------------------------------------------------------------------------
# Pack state
# ---------------------------------------------------------------------------------------------------------------

def row_key(row: Dict[str, Any]) -> str:
    return str(row.get("key") or row.get("paper_id") or row.get("doi") or "")


def read_rows(path: Path) -> List[Dict[str, Any]]:
    return report_summary.read_jsonl(path) if path.is_file() else []


def merge_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Best outcome per paper; on a tie the later row wins (the same rule as SeismoHub's harvest_status)."""
    merged: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        key = row_key(row) or f"row{index}"
        previous = merged.get(key)
        if previous is None or (report_summary.RANK[report_summary.outcome(row)]
                                >= report_summary.RANK[report_summary.outcome(previous)]):
            merged[key] = row
    return merged


def _parse_iso(value: Any) -> Optional[dt.datetime]:
    try:
        return dt.datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def resume_decision(previous: Optional[Dict[str, Any]], now: dt.datetime, *, retry_failed: bool, force: bool) -> str:
    """``run``, or why a paper of an earlier run is skipped: ``done``, ``held`` or ``not_due``.

    Same policy as SeismoHub's library mode: a failed paper is retried after a day (transient errors) or 30 days
    (everything else); ``--retry-failed`` retries failed and held papers at once; ``--force`` redoes everything.
    """
    if previous is None or force:
        return "run"
    outcome = report_summary.outcome(previous)
    if outcome in ("attached", "already_had_pdf", "duplicate"):
        return "done"
    if outcome == "held":
        return "run" if retry_failed else "held"
    if retry_failed:
        return "run"
    when = _parse_iso(previous.get("harvested_at"))
    wait = fb._retry_after(str(previous.get("status") or "")) or dt.timedelta(days=30)
    return "run" if when is None or now >= when + wait else "not_due"


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def unique_pdf_path(folder: Path, name: str, sha256: str) -> Path:
    """``name``, or ``name-2.pdf`` ... when another file already uses it; an identical file is reused."""
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    for n in [None] + list(range(2, 1000)):
        candidate = folder / (f"{stem}-{n}.pdf" if n else f"{stem}.pdf")
        if not candidate.exists():
            return candidate
        if hashlib.sha256(candidate.read_bytes()).hexdigest() == sha256:
            return candidate
    raise RuntimeError(f"no free file name for {name}")


def pdf_file_name(year: str, first_author: str, title: str) -> str:
    return (f"{year or '0000'}_{citations._clean_slug(first_author, 20)}_"
            f"{citations._clean_slug(title, 55)}.pdf")


def summary_row(row: Dict[str, Any]) -> Dict[str, str]:
    held = bool(row.get("held_copy") or row.get("held_xml"))
    bundle = str(row.get("bundle") or "")
    if row.get("open_pdf"):
        status = "open_pdf"
    elif held:
        status = "held_tdm_only"
    elif report_summary.outcome(row) == "duplicate":
        status = "duplicate"
    else:
        status = str(row.get("status") or "")
    return {
        "key": row_key(row), "query": str(row.get("query") or ""), "year": str(row.get("year") or ""),
        "first_author": str(row.get("first_author") or ""), "journal": str(row.get("journal") or ""),
        "doi": str(row.get("doi") or ""), "title": str(row.get("title") or ""), "status": status,
        "channel": report_summary.outcome_channel(row), "open_pdf": str(row.get("open_pdf") or ""),
        "tdm_bundle": bundle if bundle.startswith(TDM_DIR + "/") else "",
        "open_bundle": bundle if bundle.startswith(OPEN_BUNDLE_DIR + "/") else "",
    }


def write_state_files(out_dir: Path) -> Tuple[int, int]:
    """Rewrite harvest_summary.tsv and pending_zotero.csv from all report rows of the pack."""
    merged = merge_rows(read_rows(out_dir / REPORT_FILE))
    rows = [summary_row(r) for r in merged.values()]
    pending = [{k: str(r.get(k) or "") for k in PENDING_FIELDS} for r in merged.values()
               if report_summary.outcome(r) == "no_full_text"]
    with open(out_dir / f".{SUMMARY_FILE}.part", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(out_dir / f".{SUMMARY_FILE}.part", out_dir / SUMMARY_FILE)
    pending_path = out_dir / PENDING_FILE
    if pending:
        with open(out_dir / f".{PENDING_FILE}.part", "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=PENDING_FIELDS)
            writer.writeheader()
            writer.writerows(pending)
        os.replace(out_dir / f".{PENDING_FILE}.part", pending_path)
    elif pending_path.is_file():
        pending_path.unlink()
    return len(rows), len(pending)


def append_rows(out_dir: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with open(out_dir / REPORT_FILE, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rel(path: Optional[Path], root: Path) -> str:
    return path.relative_to(root).as_posix() if path else ""


def _relativize_manifest(bundle: Optional[Path], pack: Path) -> None:
    """Store the open copy's path relative to the pack, so a manifest never carries a home-directory path."""
    manifest = (bundle / "bundle_manifest.json") if bundle else None
    if manifest is None or not manifest.is_file():
        return
    data = json.loads(manifest.read_text(encoding="utf-8"))
    attached = data.get("app_attached") or {}
    path = attached.get("pdf_path")
    if path and Path(path).is_absolute():
        try:
            attached["pdf_path"] = Path(path).resolve().relative_to(pack.resolve()).as_posix()
        except ValueError:
            attached["pdf_path"] = Path(path).name
        manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _code_report_has_content(report: Dict[str, Any]) -> bool:
    return any(report.get(k) for k in ("datacite_relations", "pdf_extracted_urls", "downloaded"))


def _short(text: str, n: int) -> str:
    return seal.short(text, n)


# ---------------------------------------------------------------------------------------------------------------
# harvest
# ---------------------------------------------------------------------------------------------------------------

def harvest_one(harvester: Any, key: str, spec: str, *, out_dir: Path, dry_run: bool, extras: bool,
                sha_owner: Dict[str, str]) -> Dict[str, Any]:
    meta = resolve_spec(harvester.http, spec)
    doi = meta.get("doi") or ""
    arxiv_id = meta.get("arxiv_id") or ""
    title = meta.get("title") or ""
    authors = list(meta.get("authors") or [])
    first_author = authors[0].split()[-1] if authors and authors[0].split() else "Unknown"
    row: Dict[str, Any] = {
        "key": key, "paper_id": key, "query": spec, "doi": doi, "arxiv_id": arxiv_id, "title": title,
        "journal": meta.get("journal") or "", "year": meta.get("year") or "", "first_author": first_author,
        "status": "", "reason": "", "attached": False, "attach_reason": "", "open_pdf": "", "bundle": "",
        "app_copy": None, "held_copy": None, "held_xml": None, "attempts": [], "open_url": "",
        "suggestion": "", "harvested_at": fb._now_iso(), "tool": TOOL,
    }
    if not doi and not arxiv_id:
        row.update(status="unresolved_citation",
                   reason="no DOI or arXiv ID found: no Crossref record agrees with this citation",
                   suggestion="add the DOI or the arXiv ID to the reading list", open_url=meta.get("link") or "")
        return row

    ref = fb.PaperRef(paper_id=key, doi=doi, title=title, journal=row["journal"], link=meta.get("link") or "",
                      source="paper-pdf-harvest", arxiv_id=arxiv_id)
    setattr(ref, "authors", json.dumps(authors, ensure_ascii=False))
    out = harvester.harvest(ref)
    seal.keep_non_open_in_bundle(fb, out)  # last line of the seal: only OPEN copies reach open_pdfs/
    row.update(doi=out.doi or doi, arxiv_id=out.arxiv_id or arxiv_id, title=out.title or title,
               status=out.status, reason=out.reason, attempts=[a.as_dict() for a in out.attempts],
               app_copy=out.app_hit.describe() if out.app_hit else None,
               held_copy=out.held_hit.describe() if out.held_hit else None,
               held_xml=out.held_xml.describe() if out.held_xml else None)
    if out.app_hit is None and out.held_hit is None and out.held_xml is None:
        html_copy = next((a.url for a in out.pdf_attempts if a.outcome == fb.NO_PDF_BUT_HTML and a.url), "")
        row["open_url"] = html_copy or (f"https://doi.org/{row['doi']}" if row["doi"] else meta.get("link") or "")
        row["suggestion"] = seal.suggestion(fb, out)
    if dry_run:
        return row

    open_path: Optional[Path] = None
    if out.app_hit is not None:
        sha = out.app_hit.sha256
        owner = sha_owner.get(sha)
        if owner and owner != key:
            row["attach_reason"] = f"same_pdf_already_attached_to:{owner}"
        else:
            open_path = unique_pdf_path(out_dir / OPEN_DIR, pdf_file_name(row["year"], first_author, row["title"]), sha)
            if not open_path.exists():
                _write_atomic(open_path, out.app_hit.data)
            sha_owner[sha] = key
            row.update(attached=True, attach_reason="standalone_open_pdf", open_pdf=_rel(open_path, out_dir))

    held = out.held_hit is not None or out.held_xml is not None
    if held or (out.app_hit is not None and extras):
        root = out_dir / (TDM_DIR if held else OPEN_BUNDLE_DIR)
        bundle_dir = root / fb.safe_bundle_name(row["doi"], row["arxiv_id"], key)
        saved: List[str] = []
        code: Dict[str, Any] = {}
        if extras:
            bundle_dir.mkdir(parents=True, exist_ok=True)
            saved, code = harvester.collect_extras(out, bundle_dir)
        if held or saved or _code_report_has_content(code):
            reason = row["attach_reason"] or ("tdm_held_local_only" if held else "")
            written = fb.write_bundle(out, root, attached_pdf_path=str(open_path) if open_path else "",
                                      attach_reason=reason, extras=saved, code_report=code)
            _relativize_manifest(written, out_dir)
            row["bundle"] = _rel(written, out_dir)
        elif bundle_dir.is_dir() and not any(bundle_dir.iterdir()):
            bundle_dir.rmdir()
    return row


def _badge(row: Dict[str, Any], dry_run: bool) -> str:
    app, held, xml = row.get("app_copy"), row.get("held_copy"), row.get("held_xml")
    if app and str(row.get("attach_reason") or "").startswith("same_pdf_already_attached_to"):
        return f"DUPLICATE {app['channel']:<18} same PDF as {row['attach_reason'].split(':', 1)[1]}"
    if app:
        return f"{'DRY-OPEN' if dry_run else 'OPEN':<9} {app['channel']:<18} {app['pages']:>3}p"
    if held:
        return f"{'TDM-PDF':<9} {held['channel']:<18} {held['pages']:>3}p"
    if xml:
        return f"{'TDM-XML':<9} {xml['channel']:<18} xml "
    return f"{'PENDING':<9} {row.get('status', ''):<23}"


def cmd_harvest(args: argparse.Namespace, http: Any = None) -> int:
    if args.attach_tdm:  # sealed: refuse before touching the environment, the network or any file
        print(seal.ATTACH_TDM_SEALED_MESSAGE, file=sys.stderr)
        return seal.ATTACH_TDM_SEALED_EXIT
    specs = load_specs(args.doi, args.query, args.input_file)
    if not specs:
        print("nothing to do: give --doi, --query or --input-file", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir).expanduser().resolve()
    dry_run = bool(args.dry_run)
    load_settings(args.env_file)
    if not dry_run:
        (out_dir / OPEN_DIR).mkdir(parents=True, exist_ok=True)
        (out_dir / TDM_DIR).mkdir(parents=True, exist_ok=True)
    channels = [c.strip() for c in args.channels.split(",") if c.strip()] or None
    try:
        harvester = build_harvester(cache_path=out_dir / CACHE_FILE, readonly=dry_run, channels=channels,
                                    download_code=args.download_code, http=http, keys_file=args.keys_file)
    except ValueError as exc:  # unknown channel name
        print(f"error: {exc}", file=sys.stderr)
        return 2
    keys = key_presence(args.keys_file)

    previous = merge_rows(read_rows(out_dir / REPORT_FILE))
    now = dt.datetime.now(dt.timezone.utc)
    todo: List[Tuple[str, str]] = []
    skipped: Counter = Counter()
    for spec in specs:
        key = spec_key(spec)
        decision = resume_decision(previous.get(key), now, retry_failed=args.retry_failed, force=args.force)
        if decision == "run":
            todo.append((key, spec))
        else:
            skipped[decision] += 1
    if args.limit:
        todo = todo[: args.limit]

    mode = "DRY-RUN (nothing is written)" if dry_run else f"WRITE -> {out_dir}"
    print(f"paper-pdf-harvest {__version__} | {mode}")
    print("  keys: " + " ".join(f"{name}={'yes' if keys[k] else 'no'}" for name, k in (
        ("wiley", "WILEY_TDM_TOKEN"), ("elsevier", "ELSEVIER_API_KEY"), ("elsevier_insttoken", "ELSEVIER_INSTTOKEN"),
        ("openalex", "OPENALEX_API_KEY"))) + f" | channels: {','.join(channels) if channels else 'all'}")
    print(f"  entries: {len(specs)} | to harvest now: {len(todo)}"
          + (" | skipped: " + ", ".join(f"{k}={v}" for k, v in sorted(skipped.items())) if skipped else ""))

    sha_owner: Dict[str, str] = {}
    for key, row in previous.items():
        copy = row.get("app_copy") or {}
        if row.get("open_pdf") and copy.get("sha256"):
            sha_owner.setdefault(str(copy["sha256"]), key)

    counts: Counter = Counter()
    width = len(str(len(todo))) if todo else 1
    try:
        for index, (key, spec) in enumerate(todo, 1):
            try:
                row = harvest_one(harvester, key, spec, out_dir=out_dir, dry_run=dry_run,
                                  extras=not args.no_extras, sha_owner=sha_owner)
            except Exception as exc:  # one paper must never kill the run
                print(f"[{index:>{width}}/{len(todo)}] ERROR     {_short(spec, 60)}: {type(exc).__name__}: {exc}")
                counts["error"] += 1
                continue
            counts[report_summary.outcome(row) if not dry_run else
                   ("would_save_open" if row.get("app_copy") else
                    "would_hold_tdm" if (row.get("held_copy") or row.get("held_xml")) else
                    f"pending:{row.get('status')}")] += 1
            print(f"[{index:>{width}}/{len(todo)}] {_badge(row, dry_run)}  {_short(row.get('year') or '', 4):<4} "
                  f"{_short(row.get('first_author') or '', 14):<14} {_short(row.get('doi') or key, 30):<30} "
                  f"{_short(row.get('title') or spec, 48)}", flush=True)
            if not dry_run:
                append_rows(out_dir, [row])
    except KeyboardInterrupt:
        print("\ninterrupted - summarising what was done so far")
    finally:
        if not dry_run and (out_dir / REPORT_FILE).is_file():
            n_rows, n_pending = write_state_files(out_dir)
        else:
            n_rows = n_pending = 0

    print("\n== summary ==")
    for key, value in sorted(counts.items()):
        print(f"  {key:<34} {value}")
    if harvester.elsevier_disabled_reason:
        print(f"  elsevier pdf: {harvester.elsevier_disabled_reason}")
    if harvester.elsevier_xml_disabled_reason:
        print(f"  elsevier xml: {harvester.elsevier_xml_disabled_reason}")
    if not dry_run:
        print(f"pack:    {out_dir} ({n_rows} papers)")
        print(f"  {OPEN_DIR}/     open copies only (shareable)")
        print(f"  {TDM_DIR}/   licensed copies: local use only, never upload them to a hosted AI service")
        if n_pending:
            print(f"  {PENDING_FILE}  {n_pending} papers for a browser / Zotero download, then "
                  f"`paper-pdf-harvest triage <folder> --pack {out_dir}`")
    return 0


# ---------------------------------------------------------------------------------------------------------------
# triage
# ---------------------------------------------------------------------------------------------------------------

def _library_rows(merged: Dict[str, Dict[str, Any]], pack: Path) -> List[SimpleNamespace]:
    rows = []
    for key, row in merged.items():
        copy = row.get("app_copy") or {}
        open_pdf = str(row.get("open_pdf") or "")
        arxiv_id = str(row.get("arxiv_id") or "")
        rows.append(SimpleNamespace(
            id=key, title=str(row.get("title") or ""), doi=(str(row.get("doi") or "") or None),
            link=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            pdf_path=str(pack / open_pdf) if open_pdf else None,
            pdf_sha256=(str(copy.get("sha256") or "") or None) if open_pdf else None,
            authors=str(row.get("first_author") or ""), published_date=str(row.get("year") or "")))
    return rows


def cmd_triage(args: argparse.Namespace, http: Any = None) -> int:
    from . import pmc_oa_and_whitelist_channel as pw

    pack = Path(args.pack).expanduser().resolve()
    merged = merge_rows(read_rows(pack / REPORT_FILE))
    if not merged:
        print(f"no {REPORT_FILE} in {pack}: run `paper-pdf-harvest harvest --out-dir {pack} ...` first",
              file=sys.stderr)
        return 2
    load_settings(args.env_file)
    items = licence_triage.discover_input_pdfs(Path(p) for p in args.inputs)
    mode = "COMMIT (open -> open_pdfs/, licensed -> tdm_bundles/)" if args.commit else "DRY-RUN (writes nothing)"
    print(f"paper-pdf-harvest triage | {mode}")
    print(f"  pack: {pack} ({len(merged)} papers) | PDF files found: {len(items)}")
    if not items:
        return 0

    lib = matching.LibraryIndex(rows=_library_rows(merged, pack))
    cache = pw.MetadataFallbackCache(pack / CACHE_FILE, readonly=not args.commit)
    if args.online_license_check and http is None:
        http = fb.PoliteSession()
    held_keys = {k for k, r in merged.items() if r.get("held_copy") or r.get("held_xml")}
    counts: Counter = Counter()
    new_rows: List[Dict[str, Any]] = []
    width = len(str(len(items)))
    for index, (pdf_path, bib_entry) in enumerate(items, 1):
        tag = f"[{index:>{width}}/{len(items)}]"
        data = pdf_path.read_bytes()
        gate = fb.inspect_pdf(data)
        if not gate.ok:
            counts[f"rejected:{gate.reason}"] += 1
            print(f"{tag} REJECT      {gate.reason:<26} {pdf_path.name}")
            continue
        sig = matching.extract_match_signals(data, pdf_path.name)
        res = matching.match_signals(sig, lib, bib_entry=bib_entry)
        if res.action in ("already_attached", "conflict"):
            counts["already_in_pack"] += 1
            print(f"{tag} HAVE        open copy already in the pack   {pdf_path.name}")
            continue
        if res.action != "attach" or not res.paper_id:
            counts[f"match_{res.action}"] += 1
            print(f"{tag} {'REVIEW' if res.action == 'needs_review' else 'NO MATCH':<11} "
                  f"{(res.method or '-'):<14} {pdf_path.name}")
            for cand in res.candidates[:3] if res.action == "needs_review" else []:
                print(f"              candidate {cand['score']:.2f}  {cand['paper_id']}  {_short(cand['title'], 60)}")
            continue
        row = merged[res.paper_id]
        doi = fb.normalize_doi(str(row.get("doi") or (bib_entry or {}).get("doi") or (sig.dois[0] if sig.dois else "")))
        work = cache.get("openalex", doi, max_age_days=365.0) if doi else None
        cr_licence = ""
        if work is None and http is not None and doi and not doi.lower().startswith(fb.ARXIV_DOI_PREFIX):
            r_oa = http.get(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/')}",
                            headers={"Accept": "application/json"})
            if r_oa.ok:
                try:
                    work = r_oa.json()
                    cache.put("openalex", doi, work)
                except ValueError:
                    work = None
            r_cr = http.get(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}",
                            headers={"Accept": "application/json"})
            if r_cr.ok:
                try:
                    cr_licence = fb.crossref_vor_cc_license((r_cr.json() or {}).get("message") or {})
                except ValueError:
                    cr_licence = ""
        tier, kind, licence, why = licence_triage.classify_pdf_compliance(
            data, doi=doi, journal=str(row.get("journal") or ""), openalex_work=work, crossref_vor_cc=cr_licence)
        if tier != fb.TIER_OPEN and res.paper_id in held_keys:
            counts["licensed_copy_already_held"] += 1
            print(f"{tag} HELD        licensed copy already in tdm_bundles/   {pdf_path.name}")
            continue
        hit = fb.PdfHit(channel="browser_import", url=f"local://browser/{pdf_path.name}", data=data,
                        pages=gate.pages, chars=gate.chars, kind=kind,
                        version="publishedVersion" if kind != "open_copy" else "submittedVersion",
                        license=licence, tier=tier, identity=f"{res.method}({res.score:.2f})")
        badge = "OPEN->PACK " if tier == fb.TIER_OPEN else "TDM->BUNDLE"
        counts[("open_to_pack" if tier == fb.TIER_OPEN else "tdm_to_bundle") if args.commit else
               ("would_save_open" if tier == fb.TIER_OPEN else "would_hold_tdm")] += 1
        print(f"{tag} {badge} {_short(licence, 24):<24} {_short(doi or res.paper_id, 30):<30} "
              f"{_short(str(row.get('title') or ''), 44)}")
        if not args.commit:
            continue

        attempt = fb.Attempt("browser_import", hit.url, fb.SUCCESS, reason=why, bytes=len(data), started_at=fb._now_iso())
        new = {k: row.get(k) for k in ("key", "paper_id", "query", "doi", "arxiv_id", "title", "journal", "year",
                                       "first_author")}
        new.update(key=res.paper_id, paper_id=res.paper_id, doi=doi or row.get("doi") or "", attempts=[attempt.as_dict()],
                   app_copy=None, held_copy=None, held_xml=None, open_pdf="", bundle="", attached=False,
                   attach_reason="", open_url="", suggestion="", harvested_at=fb._now_iso(), tool=TOOL)
        ref = fb.PaperRef(paper_id=res.paper_id, doi=new["doi"], title=str(row.get("title") or ""),
                          journal=str(row.get("journal") or ""))
        if tier == fb.TIER_OPEN:
            target = unique_pdf_path(pack / OPEN_DIR, pdf_file_name(str(row.get("year") or ""),
                                     str(row.get("first_author") or "Unknown"), str(row.get("title") or "")), hit.sha256)
            if not target.exists():
                _write_atomic(target, data)
            lib.register_attached(lib.by_id[res.paper_id], hit.sha256)
            new.update(status=fb.SUCCESS, reason=f"browser_import:{tier}({why})", attached=True,
                       attach_reason="browser_import", open_pdf=_rel(target, pack), app_copy=hit.describe())
        else:
            out = fb.HarvestOutcome(ref=ref, doi=new["doi"], title=ref.title, held_hit=hit, status=fb.HELD_TDM_ONLY,
                                    reason=f"browser_import:{tier}({why}); kept in tdm_bundles/ only",
                                    attempts=[attempt])
            written = fb.write_bundle(out, pack / TDM_DIR, attach_reason="browser_import_tdm_held_local_only")
            held_keys.add(res.paper_id)
            new.update(status=fb.HELD_TDM_ONLY, reason=out.reason, held_copy=hit.describe(),
                       bundle=_rel(written, pack))
        new_rows.append(new)

    if args.commit and new_rows:
        append_rows(pack, new_rows)
        write_state_files(pack)
    print("\n== triage summary ==")
    for key, value in sorted(counts.items()):
        print(f"  {key:<34} {value}")
    if not args.commit:
        print("dry run: add --commit to write")
    return 0


# ---------------------------------------------------------------------------------------------------------------
# status, keys, render-xml
# ---------------------------------------------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()
    pending_path: Optional[Path] = None
    delimiter = ","
    if (root / REPORT_FILE).is_file():
        rows = read_rows(root / REPORT_FILE)
        label = str(root / REPORT_FILE)
        pending_path = root / PENDING_FILE
    elif (root / "_reports").is_dir() and list((root / "_reports").glob("harvest_*.jsonl")):
        reports = sorted((root / "_reports").glob("harvest_*.jsonl"), key=lambda p: p.name)  # SeismoHub library
        chosen = reports if args.all_reports else reports[-1:]
        rows = [r for p in chosen for r in read_rows(p)]
        label = str(chosen[0]) if len(chosen) == 1 else f"{len(chosen)} reports in {root / '_reports'}"
        pending_path = root / "_reports" / f"pending_browser_fetch_{chosen[-1].stem.replace('harvest_', '', 1)}.tsv"
        delimiter = "\t"
    elif (root / SUMMARY_FILE).is_file():  # a pack written by SeismoHub's harvest_literature_list.py
        with open(root / SUMMARY_FILE, encoding="utf-8") as fh:
            table = list(csv.DictReader(fh, delimiter="\t"))
        status = Counter(r.get("status") or "unknown" for r in table)
        channels = Counter(r.get("channel") or "-" for r in table if r.get("status") == "open_pdf")
        result = {"pack": str(root), "papers": len(table), "status": dict(status.most_common()),
                  "open_by_channel": dict(channels.most_common())}
        print(json.dumps(result, ensure_ascii=False, indent=1) if args.json else
              f"{root / SUMMARY_FILE}  ({len(table)} papers)\n" + "\n".join(f"  {k:<26} {v:>5}" for k, v in status.most_common())
              + ("\nopen PDFs by channel: " + ", ".join(f"{k}={v}" for k, v in channels.most_common()) if channels else ""))
        return 0
    else:
        print(f"no {REPORT_FILE}, _reports/harvest_*.jsonl or {SUMMARY_FILE} in {root}", file=sys.stderr)
        return 2

    selected = [r for r in merge_rows(rows).values() if report_summary.matches(r, args)]
    summary = report_summary.summarise(selected)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    else:
        report_summary.print_summary(label, summary)
        if args.attempts:
            report_summary.print_attempts(selected)
    if args.pending:
        if pending_path is not None and pending_path.is_file():
            with open(pending_path, encoding="utf-8-sig") as fh:
                pend = [r for r in csv.DictReader(fh, delimiter=delimiter) if report_summary.matches(r, args)]
            print(f"\npending browser downloads: {pending_path} ({len(pend)} rows)")
            for r in pend:
                print(f"  {r.get('status', ''):<22} {r.get('doi') or r.get('paper_id', ''):<34} "
                      f"{(r.get('journal') or '')[:24]:<24} {r.get('open_url', '')}")
        else:
            print("\nno pending list (nothing is waiting for a browser download)")
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    env_path = load_settings(args.env_file)
    install_upgrades(None, True, args.keys_file)  # registers OPENALEX_API_KEY as a key name and loads the keys
    present = key_presence(args.keys_file)
    files = [Path(p).expanduser() for p in ((os.environ.get("SEISMO_HARVEST_KEYS_FILE") or "").strip(),
                                            args.keys_file) if p] + [fb.DEFAULT_KEYS_FILE]
    print(f".env loaded: {env_path if env_path else 'none'}")
    for path in files:
        print(f"keys file:   {path} ({'found' if path.is_file() else 'not found'})")
    print("keys (values are never shown):")
    for name in KEY_VARS:
        print(f"  {name:<20} {'set' if present[name] else 'not set'}")
    ua = os.environ.get("SEISMO_HARVEST_UA") or ""
    print(f"  {'SEISMO_HARVEST_UA':<20} " + (("set, with a mailto: contact" if "mailto:" in ua else "set")
                                              if ua else "not set (default User-Agent, no contact address)"))
    print("channels that depend on a key:")
    print(f"  wiley_tdm         {'on' if present['WILEY_TDM_TOKEN'] else 'off (needs WILEY_TDM_TOKEN)'}")
    print(f"  elsevier_tdm      {'on' if present['ELSEVIER_API_KEY'] else 'off (needs ELSEVIER_API_KEY)'}"
          + (" + institutional token" if present["ELSEVIER_INSTTOKEN"] else ""))
    print(f"  openalex_content  {'on' if present['OPENALEX_API_KEY'] else 'off (needs OPENALEX_API_KEY)'}")
    print("  every other channel needs no key")
    return 0


def cmd_render_xml(args: argparse.Namespace) -> int:
    from . import xml_render

    root = Path(args.path).expanduser()
    if (root / TDM_DIR).is_dir():
        root = root / TDM_DIR
    result = xml_render.batch_compile_all_elsevier_xml_bundles(root, overwrite=args.overwrite)
    print(f"rendered {result['compiled_count']}, kept {result['skipped_existing_count']} existing, "
          f"{result['error_count']} errors in {root}")
    for error in result["errors"]:
        print(f"  error: {error}")
    print("The rendered PDFs are LICENSED_TDM_ONLY: read them locally, never upload them to a hosted AI service.")
    return 1 if result["error_count"] else 0


# ---------------------------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="paper-pdf-harvest", description="Verified, licence-aware full-text PDF "
                                "harvesting for reading lists. Guide: docs/GUIDE.md")
    p.add_argument("--version", action="version", version=f"paper-pdf-harvest {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    h = sub.add_parser("harvest", help="fetch a reading list into a pack folder")
    h.add_argument("--doi", action="append", default=[], metavar="ID", help="DOI or arXiv ID (repeatable)")
    h.add_argument("--query", action="append", default=[], metavar="CITATION",
                   help="free-form citation, e.g. 'Aki 1957 space and time spectra' (repeatable)")
    h.add_argument("--input-file", action="append", default=[], metavar="FILE",
                   help="text / CSV / TSV file with one DOI, arXiv ID, URL or citation per line, or a .bib export "
                        "(repeatable)")
    h.add_argument("--out-dir", required=True, metavar="DIR", help="the pack folder (created if missing)")
    h.add_argument("--channels", default="", metavar="LIST",
                   help="comma list of channels to use (default: all; see docs/GUIDE.md)")
    h.add_argument("--no-extras", action="store_true", help="skip XML, supplements, open reviews, code/data links")
    h.add_argument("--download-code", action="store_true", help="also download GitHub tarballs cited as code (<=50 MB)")
    h.add_argument("--retry-failed", action="store_true", help="retry failed and held papers of earlier runs now")
    h.add_argument("--force", action="store_true", help="redo every entry, including finished ones")
    h.add_argument("--limit", type=int, default=0, help="harvest at most N entries this run")
    h.add_argument("--dry-run", action="store_true", help="download and verify, but write nothing")
    h.add_argument("--keys-file", default="", metavar="FILE", help="another env-style keys file")
    h.add_argument("--env-file", default="", metavar="FILE", help="settings file to load (default: ./.env)")
    h.add_argument("--attach-tdm", action="store_true",
                   help="SEALED: refuses to run (exit 3). Licensed copies never go to open_pdfs/")

    t = sub.add_parser("triage", help="sort browser / Zotero PDFs into a pack by licence")
    t.add_argument("inputs", nargs="+", help="Zotero storage folder, Zotero 'Export -> files' folder, or PDFs")
    t.add_argument("--pack", required=True, metavar="DIR", help="pack folder written by `harvest`")
    t.add_argument("--commit", action="store_true", help="write (default: dry run)")
    t.add_argument("--online-license-check", action="store_true",
                   help="ask OpenAlex / Crossref when the pack's metadata cache has no licence information")
    t.add_argument("--env-file", default="", metavar="FILE", help="settings file to load (default: ./.env)")

    s = sub.add_parser("status", help="summarise a pack or SeismoHub's paper_bundles/ (metadata only)")
    s.add_argument("path", help="pack folder, or SeismoHub's paper_bundles/ folder")
    s.add_argument("--doi", action="append", default=[], help="only this DOI (repeatable)")
    s.add_argument("--paper-id", action="append", default=[], help="only this key / paper id (repeatable)")
    s.add_argument("--journal", action="append", default=[], help="only journals containing this text")
    s.add_argument("--attempts", action="store_true", help="list every attempt of the selected papers")
    s.add_argument("--pending", action="store_true", help="print the browser-download checklist")
    s.add_argument("--all-reports", action="store_true", help="SeismoHub: merge all reports (default: latest)")
    s.add_argument("--json", action="store_true", help="machine-readable output")

    k = sub.add_parser("keys", help="show which keys and settings are configured (never their values)")
    k.add_argument("--keys-file", default="", metavar="FILE", help="another env-style keys file")
    k.add_argument("--env-file", default="", metavar="FILE", help="settings file to load (default: ./.env)")

    r = sub.add_parser("render-xml", help="render Elsevier XML-only bundles to PDFs for local reading")
    r.add_argument("path", help="pack folder or a tdm_bundles/ (or SeismoHub paper_bundles/) folder")
    r.add_argument("--overwrite", action="store_true", help="re-render existing main_manuscript.pdf files")
    return p


def main(argv: Optional[Sequence[str]] = None, *, http: Any = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "harvest":
        return cmd_harvest(args, http=http)
    if args.command == "triage":
        return cmd_triage(args, http=http)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "keys":
        return cmd_keys(args)
    return cmd_render_xml(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
