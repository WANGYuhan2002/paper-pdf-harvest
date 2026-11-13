# paper-pdf-harvest

**English** · [中文](README_zh.md)

[![ci](https://github.com/WANGYuhan2002/paper-pdf-harvest/actions/workflows/ci.yml/badge.svg)](https://github.com/WANGYuhan2002/paper-pdf-harvest/actions/workflows/ci.yml)

Fetch verified full-text PDFs for a reading list, without breaking licences.

You give it DOIs, arXiv IDs, URLs, free-form citations or a Zotero/BibTeX export. It looks for the full text in
about twenty open channels (OpenAlex locations, publisher open access, arXiv, EarthArXiv, PMC, Zenodo, HAL,
institutional and national repositories, ...) and, if you have the keys, through the Wiley and Elsevier
text-and-data-mining (TDM) APIs.

- Every PDF passes four checks before it is kept: a real PDF, within the size cap, at least 3 pages and 5,000
  characters of text, and the right paper.
- The licence tier is decided from the copy actually downloaded. Open copies go to `open_pdfs/`. Licensed copies
  stay in `tdm_bundles/` on your machine and are never handed to a hosted AI service.
- Sites that block scripts are skipped, never bypassed. Those papers go to a checklist for a browser or Zotero
  download, and `triage` brings the files back, sorted by licence.

This is the PDF engine of [SeismoHub](https://github.com/WANGYuhan2002/seismohub), a literature app for seismology,
packaged to run on its own. The tuning is seismological, but the channels are organised by publisher and open
infrastructure, not by journal, so it carries over to geoscience and other fields (see
[docs/OTHER_FIELDS.md](docs/OTHER_FIELDS.md)).

## Quick start

```bash
git clone https://github.com/WANGYuhan2002/paper-pdf-harvest
cd paper-pdf-harvest
python3 -m venv .venv && source .venv/bin/activate      # Python 3.10 or newer
pip install -e .

paper-pdf-harvest keys                                   # which keys are configured (none is fine)
paper-pdf-harvest harvest --input-file examples/reading_list.txt --out-dir ~/pack --dry-run
paper-pdf-harvest harvest --input-file examples/reading_list.txt --out-dir ~/pack
paper-pdf-harvest status ~/pack --pending                # what is still missing, with links
```

The papers it could not fetch are listed in `~/pack/pending_zotero.csv`. Download them in your browser (Zotero
Connector works well), then bring them in:

```bash
paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack            # dry run: shows OPEN->PACK / TDM->BUNDLE
paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack --commit
```

Run `harvest` again on the same `--out-dir` at any time: finished papers are skipped, and failed ones are retried
when they are due. `--retry-failed` retries them now.

## The pack folder

| Path | Contents |
|---|---|
| `open_pdfs/` | Open copies only (`OPEN_CC_BY_OR_PREPRINT`): CC-licensed versions of record, preprints, repository copies. Shareable |
| `tdm_bundles/PaperBundle_<DOI>/` | Licensed copies (`LICENSED_TDM_ONLY`): publisher PDFs from TDM APIs or subscription downloads, Elsevier full-text XML with figures. **Local use only** |
| `open_bundles/PaperBundle_<DOI>/` | Extras of open papers: full-text XML, supplements, open peer review, code and data links |
| `harvest_report.jsonl` | One line per paper per run: status, reason, the copies found, every attempt |
| `harvest_summary.tsv` | Current state, one row per paper |
| `pending_zotero.csv` | Papers still without full text: link, status and what to do next |

Every bundle has a `bundle_manifest.json` that records the tier, `hosted_ai_upload_allowed`, SHA-256, page count
and every attempt.

## Two modes

- **Reading-list mode** is this repository: any list, any folder, no database.
- **Library mode** runs inside SeismoHub. `python scripts/harvest_pdfs.py` fills in missing PDFs for the papers
  in a SeismoHub library with the same engine, backs up the database first, and attaches open copies to the paper
  rows. See [docs/GUIDE.md § SeismoHub](docs/GUIDE.md#12-plugging-into-seismohub).

## Keys

None is required. With keys you get more:

| Variable | Unlocks | Cost |
|---|---|---|
| `SEISMO_HARVEST_UA` | Your contact address in the User-Agent: Crossref polite pool, higher DataCite limit | free |
| `WILEY_TDM_TOKEN` | Wiley / AGU versions of record through the Wiley TDM API (subscriptions: institutional network) | free for subscribers' non-commercial research |
| `ELSEVIER_API_KEY` (+ `ELSEVIER_INSTTOKEN`) | Elsevier open-access PDFs; subscribed full text as XML from an entitled network | free for non-commercial academic use |
| `OPENALEX_API_KEY` | Cached PDFs from `content.openalex.org` | free key, $1/day allowance (about 100 PDFs) |

Put them in `~/.config/seismo_harvester/keys.env`, outside every repository. Sign-up pages, terms and limits are
in [docs/KEYS.md](docs/KEYS.md). The variable names carry SeismoHub's prefix, so one keys file serves both tools.

## How well it works

In 18 SeismoHub library runs (8 to 10 November 2026; 2,445 seismology and geophysics papers; Wiley, Elsevier and
OpenAlex keys; partly on an institutional network), it found:

- an open copy for 1,562 papers (64%);
- a licensed copy, kept local, for 205 (8%);
- a duplicate of another paper's PDF for 41 (2%);
- nothing for 637 (26%).

Most of the misses fall into three groups:

- subscription journals with no TDM route and few open copies: the Seismological Society of America journals on
  GeoScienceWorld, SEG, and OUP's GJI before its switch to open access;
- ESSOAr preprints, whose server blocks scripts;
- Zenodo DOIs that are datasets rather than papers.

Coverage by publisher and channel, and the weaknesses, are in [docs/RESULTS.md](docs/RESULTS.md).

## Licence rules

- Licensed (TDM) copies stay on your machine. They are never written to `open_pdfs/` and never sent to a hosted AI
  service. `--attach-tdm` is sealed: it exits with code 3 and does nothing.
- A publisher PDF whose first pages say "All rights reserved" without an open-licence statement is treated as
  licensed, whatever the metadata claims.
- Bot protection, CAPTCHAs and logins are never bypassed. There is no browser automation and no User-Agent
  spoofing, and every host has a minimum interval between requests.
- Use the TDM keys only within your institution's licence, as described in [docs/KEYS.md](docs/KEYS.md).

## Agent skill (Claude Code)

[`.claude/skills/paper-pdf-harvest/SKILL.md`](.claude/skills/paper-pdf-harvest/SKILL.md) teaches an agent the
workflow and the rules, for example "never read a licensed copy" and "dry run first". Claude Code picks it up when
you open this repository. To have it everywhere, copy or symlink the folder to `~/.claude/skills/`.

## Documentation

| Document | Contents |
|---|---|
| [docs/GUIDE.md](docs/GUIDE.md) | Full guide: channels and their order, the four checks, licence tiers, outputs, statuses, filling the gaps, commands, Python API, SeismoHub |
| [docs/KEYS.md](docs/KEYS.md) | Which accounts and keys to register, what they cost and unlock, and the terms to respect |
| [docs/RESULTS.md](docs/RESULTS.md) | Measured coverage by publisher, channel and status; strengths and weaknesses |
| [docs/OTHER_FIELDS.md](docs/OTHER_FIELDS.md) | Using it outside seismology: what works as is and what to tune |
| [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [CHANGELOG.md](CHANGELOG.md) | Development, reporting vulnerabilities, versions |

Each document has a Chinese version (`*_zh.md`).

## Relation to SeismoHub

The engine (`fullbundle_harvest.py`, `upgrades.py` and the resolver modules) is generated from SeismoHub's
open-source tree; those files start with a "Synced from SeismoHub" banner. The command line, tests and
documentation belong to this repository. Engine fixes land in SeismoHub first and are synced here, so both tools
behave the same.

## Licence

MIT. See [LICENSE](LICENSE). The licence covers the code, not the papers you download: each paper keeps its own
licence.
