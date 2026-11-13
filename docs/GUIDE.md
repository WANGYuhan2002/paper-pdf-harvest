# paper-pdf-harvest guide

**English** · [中文](GUIDE_zh.md)

1. [Install](#1-install)
2. [Quick start](#2-quick-start)
3. [How a PDF is obtained](#3-how-a-pdf-is-obtained)
4. [Outputs, reports and statuses](#4-outputs-reports-and-statuses)
5. [Re-running and `--retry-failed`](#5-re-running-and---retry-failed)
6. [What can be obtained](#6-what-can-be-obtained)
7. [What cannot be obtained automatically](#7-what-cannot-be-obtained-automatically)
8. [Filling the gaps](#8-filling-the-gaps)
9. [Command reference](#9-command-reference)
10. [Python API](#10-python-api)
11. [Agent skill for Claude Code](#11-agent-skill-for-claude-code)
12. [Plugging into SeismoHub](#12-plugging-into-seismohub)
13. [Differences from SeismoHub's reading-list script](#13-differences-from-seismohubs-reading-list-script)

---

## 1. Install

Python 3.10 or newer. The runtime dependencies are `requests`, `PyMuPDF` (PDF checks and rendering) and
`python-dotenv`.

```bash
git clone https://github.com/WANGYuhan2002/paper-pdf-harvest
cd paper-pdf-harvest
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # installs the `paper-pdf-harvest` command
pip install -e ".[test]"    # plus pytest, for the offline test suite
```

Without installing: `pip install -r requirements.txt`, then `python -m paper_pdf_harvest ...` from the repository
root.

Keys are optional (see [KEYS.md](KEYS.md)). Put them in `~/.config/seismo_harvester/keys.env`, outside every
repository, or in a `.env` in the folder you run from. `paper-pdf-harvest keys` shows which ones it found, never
their values.

## 2. Quick start

### 2.1 Reading-list mode (this tool)

```bash
paper-pdf-harvest harvest --input-file reading_list.txt --out-dir ~/pack --dry-run   # verify, write nothing
paper-pdf-harvest harvest --input-file reading_list.txt --out-dir ~/pack
paper-pdf-harvest harvest --doi 10.1029/JB082i020p02981 --doi arXiv:1803.03211 --out-dir ~/pack
paper-pdf-harvest harvest --query "Shapiro Campillo 2005 surface-wave tomography ambient noise" --out-dir ~/pack
paper-pdf-harvest status ~/pack --pending
```

A reading list has one entry per line: a DOI, a DOI link, an arXiv ID or URL, or a free-form citation; lines that
start with `#` are comments. CSV or TSV lines work when they contain a DOI. A `.bib` export (Zotero, JabRef, ...)
is read entry by entry: the DOI if there is one, else the arXiv ID, else title, first author and year.

### 2.2 Library mode (SeismoHub)

If you use [SeismoHub](https://github.com/WANGYuhan2002/seismohub), the same engine fills in missing PDFs for your
library:

```bash
cd seismohub
python scripts/harvest_pdfs.py --dry-run --limit 20     # preview, writes nothing
python scripts/harvest_pdfs.py --limit 200              # backs up the DB, attaches open copies
```

See [section 12](#12-plugging-into-seismohub).

## 3. How a PDF is obtained

For each entry the tool:

1. resolves it to a DOI and/or arXiv ID with its title, authors and year. A DOI is looked up in Crossref, an arXiv
   ID in the arXiv API, and a citation in a Crossref bibliographic search, keeping only a record that agrees with
   the citation;
2. reads the work's OpenAlex record, which gives the copies OpenAlex knows and the licence of the version of
   record (VoR);
3. builds an ordered list of candidate copies (3.1) and tries them one by one;
4. downloads each candidate politely (3.6) and checks it (3.2);
5. assigns the licence tier of the copy it actually got (3.3);
6. stops at the first open copy. A licensed copy found earlier is kept, but the search goes on for an open one;
7. optionally collects extras (3.5), then writes the pack (section 4).

### 3.1 Channels and their order

The candidates come in three groups. Within a group they are tried in the order listed. The base engine
(`fullbundle_harvest.py`) defines the groups; the upgrade layer (`upgrades.py`, from SeismoHub v2.3) adds
channels to each group and is always installed by the command line.

**Group 0: open version of record** (the best copy: final text, free to use)

| Channel | When | What |
|---|---|---|
| `openalex` | OpenAlex location with a `pdf_url`, published version, CC licence | Publisher OA PDF (Copernicus, Seismica, Nature OA, Frontiers, ...) |
| `copernicus` | DOI `10.5194/...` | Deterministic PDF URL: the final paper, or the discussion preprint |
| `nature` | DOI `10.1038/...` with a CC licence | Nature Portfolio open-access PDF |
| `ethrc` | DOI `10.3929/...`, or the paper is in the ETH Research Collection | Repository PDF. Only robots.txt-allowed paths, 10 s between requests |
| `nature_aap` | Nature gold-OA article in press | The accelerated-preview `_reference.pdf` when the `.pdf` URL serves HTML |
| `springer_link` | DOI `10.1007/...` with a CC licence | `link.springer.com/content/pdf/...` |
| `crossref_link` | Seismica, or a gold-OA DOI with no other usable open copy | The text-mining PDF link the publisher registered in Crossref, on a host that does not block scripts |
| `pmc_oa_s3` | PMCID known, or DOI prefix `10.1126/sciadv.`, `10.1073/pnas.`, `10.3390/`, `10.1371/`, `10.3389/` | PMC open-access PDF from NCBI's open-data bucket on AWS, with its per-article licence |
| `openalex_content` | `OPENALEX_API_KEY` set, OpenAlex holds a cached PDF, gold-OA licence, no other usable open copy | `content.openalex.org` cached PDF |
| `osti_gov` | DOI `10.2172/...` | US DOE report PDF (public domain) |
| `hal_api` | HAL link without a DOI | The HAL record's main file |

**Group 1: licensed version of record** (the tier depends on the VoR licence)

| Channel | When | What |
|---|---|---|
| `wiley_tdm` | DOI `10.1002/`, `10.1111/`, `10.1029/` (AGU) and `WILEY_TDM_TOKEN` | Publisher PDF from the Wiley TDM API |
| `elsevier_tdm` | DOI `10.1016/` and `ELSEVIER_API_KEY` | PDF from the Elsevier API. For a subscribed article it serves a 1-page preview; the tool then asks for the full-text XML (`elsevier_tdm_xml`, FULL view), which an entitled network does serve |
| `nature` | DOI `10.1038/` without a CC licence | Publisher copy |
| `nature_aap`, `springer_link` | Same publishers, no CC licence | Publisher copy |

**Group 2: other open copies** (accepted manuscripts, preprints, repositories)

| Channel | When | What |
|---|---|---|
| `openalex_repo` | OpenAlex repository location with a `pdf_url` | University and subject repositories, HAL, ... |
| `arxiv` | arXiv ID from the DOI, link or OpenAlex | `export.arxiv.org/pdf/<id>`, 3 s between requests |
| `eartharxiv` | DOI `10.31223/...`, or an EarthArXiv landing page | EarthArXiv download link |
| `zenodo` | DOI `10.5281/zenodo....` | The record's main PDF (not supplements, posters or read-me files) |
| `openalex` | Any remaining OpenAlex `pdf_url` (bronze, no licence) | Publisher or repository copy |
| `researchsquare` | DOI `10.21203/...` or a Research Square link | CC-BY preprint PDF |
| `openalex_content` | ESSOAr preprint with an OpenAlex cached PDF and a key | Cached preprint PDF |
| `green_oa_cascade` | Paper in a journal whose site blocks scripts (prefixes `10.1029`, `10.1002`, `10.1111`, `10.1016`, `10.1785`, `10.1093`, `10.1190`, `10.1126`, `10.1073`, `10.1130`, `10.1121`, `10.3390`, `10.1007`) or an ESSOAr preprint | One resolver that asks, in order and stopping at the first verified hit: OSTI, USGS Publications Warehouse, GFZ PubMan, CaltechAUTHORS (each only when the affiliations suggest it), HAL, DataCite repositories, Crossref "posted-content" preprints (EarthArXiv, EGUsphere, Research Square). Title and author must match |

The upgrade layer also:

- rewrites repository URLs from OpenAlex into direct downloads (PMC article pages to the PMC open-data bucket,
  arXiv DOI links to `export.arxiv.org`, HAL pages to `/document`, DSpace 7 `/bitstreams/<uuid>/download` to the
  REST `content` endpoint);
- infers a DOI from a `nature.com/articles/...` link when the entry has none;
- maps an ESSOAr preprint (`10.22541/essoar...`) without a copy to its published version, through Crossref
  `is-preprint-of` or a strict title and author search, and harvests that DOI (channels show as
  `essoar_vor(...)`);
- re-checks a publisher copy after download: if its first pages say "All rights reserved" without an open-licence
  statement, it becomes licensed and the remaining open-copy candidates are tried.

`--channels` limits a run to some channels (comma list). Some names in the list exist only for SeismoHub
compatibility: `datacite_repo`, `gfz_repo`, `usgs_pubs`, `crossref_preprint` run inside `green_oa_cascade`.

### 3.2 The four acceptance checks

| # | Check | Rejects | Status when it fails |
|---|---|---|---|
| 1 | `%PDF-` in the first 1 KB | HTML landing pages, login pages, error pages | `no_pdf_but_html` or `unsupported_content_type` |
| 2 | Size: at least 40 KB, at most the cap (160 MB, `SEISMO_HARVEST_MAX_BYTES`); not encrypted | Stubs, oversized files | `unsupported_content_type` |
| 3 | At least 3 pages and 5,000 characters of text (PyMuPDF is required; nothing is accepted unchecked) | 1–2 page previews, login stubs, scans without a text layer | `auth_required` (too few pages) or `unsupported_content_type` |
| 4 | Identity: at least 70% of the title's content words on the first two pages, or the DOI there plus 35% | Wrong papers, papers that cite this DOI | `unsupported_content_type` (`identity_mismatch`) |

Check 4 has two refinements from the upgrade layer:

- an EGU General Assembly abstract printed under the same title as a journal paper is rejected;
- a preprint whose title changed for publication is accepted at 35–70% title overlap only if the paper has at
  least three authors whose surnames are on the page. All of them must match, or at least 85% of them when there
  are four or more, and always the first and the last.

### 3.3 Licence tiers

The tier comes from **the copy actually downloaded**, not from the paper's open-access status:

| Tier | Given when | Goes to |
|---|---|---|
| `OPEN_CC_BY_OR_PREPRINT` | A repository or preprint copy; or the copy carries a CC or public-domain licence; or it came through a licensed channel but the VoR itself is CC-licensed (OpenAlex, or the publisher's Crossref licence deposit when OpenAlex has none) | `open_pdfs/` |
| `LICENSED_TDM_ONLY` | A publisher version obtained through an institutional licence (Wiley or Elsevier TDM, subscription downloads), Elsevier full-text XML, or a publisher copy whose PDF says "All rights reserved" without an open statement | `tdm_bundles/`, local use only |

The manifest records `"hosted_ai_upload_allowed": false` for every licensed copy. Before anything is written,
`seal.keep_non_open_in_bundle` checks once more that only an open copy can reach `open_pdfs/`. `--attach-tdm` is
sealed: it exits with code 3 before touching the network or a file.

### 3.4 What is saved and what is held back

- An open copy is saved to `open_pdfs/` (`<year>_<first author>_<title>.pdf`).
- A licensed copy is kept as `tdm_bundles/PaperBundle_<DOI>/main_manuscript.pdf`, or `main_manuscript.xml` for
  Elsevier XML. If an open copy was also found, the bundle links it as `app_attached_copy.pdf`.
- Once a licensed version of record is held, other licensed or publisher candidates are skipped; only an open copy
  can still improve the result.
- When two entries resolve to the same PDF (same SHA-256), the second is reported as a duplicate and no second file
  is written.

### 3.5 Bundle extras

Unless `--no-extras` is given:

- **Copernicus / EGU:** full-text XML, supplement PDF and ZIP, the discussion page and its open-review PDFs
  (referee and author comments, editor reports).
- **Elsevier:** FULL-view XML and `mmc` supplements. For XML-only bundles, the high-resolution figures too (at most
  40).
- **Nature:** electronic supplementary material, at most 12 files.
- **Code and data:** DataCite relations that point to the DOI, plus links found in the PDF's data-availability
  section, last pages and link annotations (GitHub, GitLab, Zenodo, figshare, OSF, IRIS/EarthScope, ...). They are
  written to `companion_code_data/code_and_data_links.json`. `--download-code` also fetches up to three GitHub
  tarballs of at most 50 MB each.

Videos are skipped, and every supplement is capped at 50 MB. Extras of open papers go to `open_bundles/`.

### 3.6 Politeness

- Minimum interval per host: arXiv 3 s; Wiley TDM 10 s (Wiley allows 60 requests per 10 minutes); ETH Research
  Collection 10 s (its robots.txt crawl delay); Zenodo, OSTI and GFZ 0.6 s; Elsevier, USGS and
  `content.openalex.org` 0.5 s; HAL 0.4 s; DataCite 0.3 s; Crossref 0.25 s; OpenAlex 0.15 s; any other host 1 s.
  One request at a time: papers are processed one after another.
- An honest User-Agent that names the tool. Set `SEISMO_HARVEST_UA` to add your own `mailto:` address.
- HTTP 429/502/503/504 are retried once, honouring `Retry-After` up to 30 s. When `content.openalex.org` reports its
  daily allowance used up, it is not asked again for the rest of the run.
- Redirects are followed by hand. A key header is dropped as soon as a redirect leaves the publisher's domain, and
  key-bearing URLs never reach reports or manifests.
- Elsevier circuit breakers: after 3 consecutive 1-page previews of subscribed articles, their PDF requests are
  skipped; after 3 consecutive XML responses without full text (not entitled from this network), XML requests are
  skipped. Open-access Elsevier PDFs are always tried.
- Bot-walled hosts (section 7) are never requested.

## 4. Outputs, reports and statuses

### 4.1 Pack layout

```
<out-dir>/
  open_pdfs/                       open copies only
  tdm_bundles/PaperBundle_<DOI>/   licensed copies (local only)
     bundle_manifest.json
     main_manuscript.pdf | main_manuscript.xml
     app_attached_copy.pdf         the open copy, when the main manuscript is licensed
     fulltext_structured.xml  supplements/  figures/  peer_review_rc_ac/  companion_code_data/
  open_bundles/PaperBundle_<DOI>/  extras of open papers (same layout)
  harvest_report.jsonl             one line per paper per run
  harvest_summary.tsv              current state, one row per paper
  pending_zotero.csv               the browser / Zotero checklist
  _metadata_cache.sqlite           OpenAlex metadata cache (7 days)
```

### 4.2 `harvest_report.jsonl`

One JSON object per paper per run. The main fields are:

- `key` (`doi:...`, `arxiv:...` or `q:<hash>` for a citation), `query`, `doi`, `arxiv_id`, `title`, `journal`,
  `year`, `first_author`;
- `status`, `reason`, `attached` / `attach_reason`, `open_pdf`, `bundle`;
- `app_copy`, `held_copy` and `held_xml`, each with channel, source URL, kind, version, licence, tier,
  `hosted_ai_upload_allowed`, pages, identity, bytes and SHA-256;
- `attempts[]`: every request, with channel, URL, outcome, reason, HTTP status, bytes, time and duration;
- `open_url`, `suggestion`, `harvested_at`, `tool`.

The format matches SeismoHub's library reports, so `paper-pdf-harvest status` reads both.

### 4.3 `bundle_manifest.json`

It records the harvester version and time, the identifiers, title and journal, and the OpenAlex summary
(`oa_status`, the VoR licence). It then describes `main_manuscript`, `app_attached` and `held_back_tdm_copy`, each
with its tier and `hosted_ai_upload_allowed`. It ends with the files written, the extras, the code and data links,
and every attempt. SeismoHub's licence guards read exactly these fields.

### 4.4 Statuses

| Status | Meaning | What to do |
|---|---|---|
| `success` (`open_pdf` in the summary) | Open copy verified and saved | Nothing |
| `held_tdm_only` | Licensed copy kept in `tdm_bundles/` | Read it locally; `--retry-failed` later may find an open copy |
| `captcha_or_bot_block` | The only copies are on sites that block scripts | Browser download, then `triage` |
| `no_pdf_but_html` | The host served an HTML page (often PMC, nature.com) | Open `open_url` in a browser and save the PDF |
| `auth_required` | Login wall, 401/402/403, or a 1–2 page preview | Browser download from a network with access |
| `no_oa_copy` | No channel returned a copy | Browser download; author page or repository |
| `transient_error` | Timeout, HTTP 5xx (for example Wiley TDM 500s), quota | Retried automatically after a day; or `--retry-failed` |
| `unresolved_citation` | No Crossref record agrees with the citation | Put the DOI in the list |
| `duplicate` | Same PDF as another entry | Usually a preprint DOI and its journal DOI; nothing to do |
| `unsupported`, `unsupported_content_type` | Not a paper (dataset, software, review comment), a wrong file, or a failed identity check | Usually skip; check `--attempts` |

When several channels fail, the paper's status is the most telling failure, in this order: `transient_error`,
`captcha_or_bot_block`, `auth_required`, `no_pdf_but_html`, `unsupported_content_type`, `no_oa_copy`,
`unsupported`.

## 5. Re-running and `--retry-failed`

Running `harvest` again with the same `--out-dir` resumes the pack:

| Earlier result | Default | `--retry-failed` | `--force` |
|---|---|---|---|
| Open copy saved, or duplicate | skipped | skipped | redone |
| Licensed copy held | skipped | retried (looking for an open copy) | redone |
| `transient_error` | retried once a day has passed | retried | redone |
| Any other failure | retried once 30 days have passed | retried | redone |

That is the same policy as SeismoHub's library mode. Typical uses:

- after Wiley TDM returned HTTP 500s, rerun a few days later;
- after connecting to the institutional network or VPN, rerun with `--retry-failed` to get Elsevier XML;
- weeks later, rerun to pick up new open-access copies and preprints.

## 6. What can be obtained

| Source | Key needed | Typical result |
|---|---|---|
| arXiv, EarthArXiv, Research Square, EGUsphere preprints | no | Preprint (open) |
| Copernicus / EGU journals, Seismica, Frontiers, PLOS, MDPI (through PMC), Science Advances (through PMC), PNAS open articles (through PMC) | no | Published version (open) |
| Nature Portfolio open access (Nature Communications, Scientific Reports, Communications Earth & Environment, ...) | no | Published version (open) |
| Springer open-access articles | no | Published version (open) |
| Institutional and national repositories known to OpenAlex or DataCite (HAL, ETH Research Collection, CaltechAUTHORS, GFZ, OSTI, USGS, KITopen, ...) | no | Accepted manuscript or published version (open) |
| Zenodo records that contain a paper | no | Usually a preprint (open) |
| Wiley / AGU gold and hybrid OA (CC-licensed VoR) | `WILEY_TDM_TOKEN` (the publisher site blocks scripts) | Published version (open) |
| Wiley / AGU subscription articles | `WILEY_TDM_TOKEN`, institutional network | Published version (licensed, local) |
| Elsevier open access | `ELSEVIER_API_KEY` | Published version (open) |
| Elsevier subscription articles | `ELSEVIER_API_KEY`, entitled network or `ELSEVIER_INSTTOKEN` | Full-text XML with figures (licensed, local). The API serves no full PDF |
| OpenAlex cached PDFs (gold OA, for example GJI since 2024) | `OPENALEX_API_KEY` | Published version (open), within the daily allowance |

## 7. What cannot be obtained automatically

- **Sites that block scripts.** These hosts answered a plain scripted request with a Cloudflare challenge when they
  were probed. They are listed in `BOT_WALLED_HOSTS` and never requested:

  | Host | Journals |
  |---|---|
  | `academic.oup.com` | GJI and other OUP journals |
  | `pubs.geoscienceworld.org` | BSSA, SRL and TSR (SSA), GSA journals, ... |
  | `essopenarchive.org` | ESSOAr preprints |
  | `agupubs.onlinelibrary.wiley.com`, `onlinelibrary.wiley.com` | AGU / Wiley web (use the TDM API instead) |
  | `www.sciencedirect.com` | Elsevier web (use the API instead) |
  | `www.science.org`, `www.pnas.org`, `www.mdpi.com` | Science, PNAS, MDPI web |

  If the only copy lives there, the status is `captcha_or_bot_block`.
- **Login walls and subscriptions** without a TDM route: `auth_required`, or a 1–2 page preview rejected by
  check 3.
- **No open copy anywhere:** `no_oa_copy`. Common for older papers and for journals with few preprints.
- **Hosts that serve only HTML to scripts** (some PMC and nature.com pages): `no_pdf_but_html`.
- **Elsevier subscription PDFs:** the API serves a 1-page preview, even on an entitled network. You get the
  full-text XML instead (licensed, local); `render-xml` turns it into a PDF for local reading.
- **Non-papers:** dataset, software and review-comment DOIs have no paper PDF (`unsupported`).

The tool will not solve CAPTCHAs, imitate a browser, drive a browser, or reuse your browser cookies. That is a
design rule, not a missing feature.

## 8. Filling the gaps

1. **Checklist.** `pending_zotero.csv` lists every paper still without full text. Each row has its `open_url` (the
   DOI link, or the HTML copy that was found) and a `suggestion`. `paper-pdf-harvest status <pack> --pending`
   prints it.
2. **Browser download.** Open the links in your browser, on a network with access (campus or VPN), and save the
   PDFs. The Zotero Connector saves a PDF and its metadata in one click, and the Zotero `.bib` export later gives
   the triage an authoritative DOI.
3. **Licence triage.**
   ```bash
   paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack            # dry run
   paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack --commit
   ```
   Each PDF must pass checks 1–3 and is matched to a paper of the pack: the `.bib` DOI first, then a DOI printed on
   the PDF (only if the PDF's title agrees), then the arXiv ID, then the exact title, then a fuzzy title (at least
   0.92 and unique; otherwise listed for review). The tier is then decided, failing closed:
   - **open** if it is a preprint DOI, or the PDF carries an open-access or Creative Commons statement, or
     OpenAlex/Crossref record a CC licence for the VoR and the PDF has neither "All rights reserved" nor an
     institution download stamp;
   - **licensed** otherwise, including any PDF with "All rights reserved" or a stamp such as "Downloaded from ... by
     \<Institution\> user on \<date\>".

   Open PDFs go to `open_pdfs/`, licensed ones to `tdm_bundles/` with `hosted_ai_upload_allowed: false`.
   `--online-license-check` asks OpenAlex and Crossref when the pack's cache has no licence information.
4. **Zotero "Export → files" folder.** Pass the folder; its `.bib` is read and its DOIs are trusted first. This is
   the standalone counterpart of SeismoHub's `match_zotero_export.py`.
5. **Retry later.** `harvest --retry-failed` retries failed and held papers now. Without it, failures are retried
   when due (section 5). New preprints and repository copies appear over time.
6. **Author pages and repositories.** Many authors post accepted manuscripts on their homepage or in their
   institution's repository. A repository that OpenAlex or DataCite knows is already searched (channels
   `openalex_repo` and `green_oa_cascade`). For anything else, download the copy and run `triage`. Triage fails
   closed: a copy with an open-access or CC statement is saved as open, but one that only repeats the journal's
   "All rights reserved" line is kept as licensed, because triage cannot tell an author's posting from a
   publisher download. If you know the posting is open, read it locally anyway; just don't upload it.

The triage recognises common markers, but it cannot recognise every subscription PDF. Do not upload PDFs to a
hosted AI service unless you know their licence allows it.

## 9. Command reference

```
paper-pdf-harvest harvest  [--doi ID]... [--query CITATION]... [--input-file FILE]... --out-dir DIR
                           [--channels LIST] [--no-extras] [--download-code] [--dry-run]
                           [--retry-failed] [--force] [--limit N] [--keys-file FILE] [--env-file FILE]
paper-pdf-harvest triage   INPUT... --pack DIR [--commit] [--online-license-check] [--env-file FILE]
paper-pdf-harvest status   PATH [--doi D]... [--paper-id KEY]... [--journal TEXT]... [--attempts] [--pending]
                           [--all-reports] [--json]
paper-pdf-harvest keys     [--keys-file FILE] [--env-file FILE]
paper-pdf-harvest render-xml PATH [--overwrite]
```

- `harvest --dry-run` downloads and verifies but writes nothing: no folder, no cache, no report.
- `status` accepts a pack, a SeismoHub `paper_bundles/` folder (latest report; `--all-reports` merges them), or a
  folder written by SeismoHub's reading-list script. It reads report metadata only and never opens a PDF or an XML
  file.
- `render-xml` turns Elsevier XML-only bundles into PDFs with figures, for local reading. The result is still
  licensed: every page carries a "LICENSED TDM COPY ... DO NOT UPLOAD TO HOSTED AI" banner, and the manifest says
  `hosted_ai_upload_allowed: false`.

Settings (environment, `.env` or the keys file):

| Variable | Purpose |
|---|---|
| `SEISMO_HARVEST_UA` | User-Agent; add `mailto:` with your address |
| `WILEY_TDM_TOKEN`, `ELSEVIER_API_KEY`, `ELSEVIER_INSTTOKEN`, `OPENALEX_API_KEY` | Keys ([KEYS.md](KEYS.md)) |
| `SEISMO_HARVEST_KEYS_FILE` | An extra keys file to read (searched before `~/.config/seismo_harvester/keys.env`) |
| `SEISMO_HARVEST_MAX_BYTES` | Size cap per download (default 160 MB) |

Keys files use `export NAME="value"` or `NAME=value` lines. Only the key names above are read from them, and a
variable already set in the environment is never overridden.

## 10. Python API

```python
from pathlib import Path
from paper_pdf_harvest import fullbundle_harvest as fb
from paper_pdf_harvest.cli import build_harvester, key_presence
from paper_pdf_harvest.seal import keep_non_open_in_bundle

harvester = build_harvester(cache_path=Path("pack/_metadata_cache.sqlite"), readonly=False)
key_presence()                                    # load keys files; returns booleans only
out = harvester.harvest(fb.PaperRef("p1", doi="10.5194/se-17-825-2026", title="..."))
keep_non_open_in_bundle(fb, out)                  # the seal: only OPEN copies stay in out.app_hit
if out.app_hit:
    Path("paper.pdf").write_bytes(out.app_hit.data)        # OPEN tier
elif out.held_hit or out.held_xml:
    fb.write_bundle(out, Path("tdm_bundles"))              # licensed: keep local
print(out.status, out.reason, [a.as_dict() for a in out.attempts])
```

`build_harvester` installs the upgrade layer into the `fullbundle_harvest` module, as SeismoHub does. The network
and verification core needs only `requests` and PyMuPDF, so it also runs on a cluster or a server.

## 11. Agent skill for Claude Code

[`.claude/skills/paper-pdf-harvest/SKILL.md`](../.claude/skills/paper-pdf-harvest/SKILL.md) gives an agent the
workflows and the non-negotiable rules:

- never read a licensed copy;
- `--attach-tdm` is sealed;
- no bypassing;
- dry run first;
- keys are reported as present or absent only;
- be polite.

Claude Code discovers project skills when you open the repository. To use the skill everywhere:

```bash
mkdir -p ~/.claude/skills && ln -s "$PWD/.claude/skills/paper-pdf-harvest" ~/.claude/skills/paper-pdf-harvest
```

Then ask, for example, "fetch the PDFs for the DOIs in reading_list.txt" or "为什么这篇没有 PDF". The agent works
from report metadata and gives you the browser checklist for what it cannot fetch.

## 12. Plugging into SeismoHub

- **Same engine.** SeismoHub's `services/fullbundle_harvest.py` and `scripts/seismohub_upgrade_runner.py` are the
  source of this repository's engine. Library mode lives there:
  `python scripts/harvest_pdfs.py [--dry-run] [--limit N] [--retry-failed] ...`. It backs up the database, never
  overwrites a PDF and attaches open copies only. Reading-list mode there is `scripts/harvest_literature_list.py`.
- **Same keys.** Both tools read `~/.config/seismo_harvester/keys.env` and the same variable names.
- **Same reports.** `paper-pdf-harvest status <seismohub>/paper_bundles --all-reports` summarises SeismoHub's
  library reports.
- **Bringing a pack into SeismoHub.** Drag the files of `<pack>/open_pdfs/` onto **Upload missing PDFs** in the
  app; they are matched to library papers by DOI and title. Or run
  `python scripts/zotero_triage_import.py <pack>/open_pdfs` (dry run, then `--commit`), which adds licence triage.
  That triage fails closed too, so a preprint without a licence statement may be kept as licensed. Licensed copies
  stay in the pack. If you need them in SeismoHub, its library mode can fetch them again; it keeps them in
  `paper_bundles/`, and its licence guards keep them away from the AI analysis and the PDF Q&A.
- **Same manifest format.** SeismoHub's guards read the tiers and `hosted_ai_upload_allowed` from
  `bundle_manifest.json`, the format both tools write.

## 13. Differences from SeismoHub's reading-list script

This command line replaces `scripts/harvest_literature_list.py` for standalone use. It runs the same engine,
upgrade layer and seal, plus:

- resumable packs with retry dates, `--retry-failed`, `--force` and `--limit`;
- a full per-paper report (`harvest_report.jsonl`) with every attempt;
- arXiv entries resolved through the arXiv API (title and authors), so the identity check can pass. Bare October
  IDs such as `2310.01234` are recognised as arXiv IDs;
- free-form citations accepted only when the Crossref record agrees with them (otherwise `unresolved_citation`),
  so an unknown citation never fetches an unrelated paper;
- `.bib` input; CSV header lines skipped;
- extras of open papers in `open_bundles/`, so `tdm_bundles/` holds licensed copies only;
- manifests store the open copy's path relative to the pack;
- `triage` against the pack (no database), `status` for packs and SeismoHub, and `keys`.
