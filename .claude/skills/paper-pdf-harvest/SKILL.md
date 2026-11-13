---
name: paper-pdf-harvest
description: >-
  Fetch and verify full-text PDFs for a reading list with paper-pdf-harvest: DOIs, arXiv IDs, URLs, free-form
  citations or a .bib export go into a pack folder, with open copies separated from licensed (TDM) copies. Use it to
  download the full text of a list of papers, to import PDFs downloaded in a browser or with Zotero with licence
  triage, to summarise a pack, to check which keys are configured, or to explain why a paper has no PDF. Trigger on
  requests such as "fetch / download / harvest the PDFs for these DOIs", "get the full text of this reading list",
  "why is there no PDF for ...", "抓取 PDF", "下载全文", "把这些文献的 PDF 拿下来", "为什么这篇没有 PDF". The skill
  enforces the licence rules: TDM-licensed copies stay local and are never read into a hosted AI, and bot-protected
  sites are never bypassed.
---

# paper-pdf-harvest / 全文 PDF 抓取

Run the `paper-pdf-harvest` command (installed with `pip install -e .` from the repository root; without
installing, use `python -m paper_pdf_harvest`). The full guide is `docs/GUIDE.md` (中文 `docs/GUIDE_zh.md`); keys
are explained in `docs/KEYS.md`.

## Ground rules (non-negotiable)

1. **Licensed full text never leaves the machine, and you are a hosted AI.** Never open, read, extract, render to
   text or summarise anything in a pack's `tdm_bundles/` folder, any file whose `bundle_manifest.json` says
   `LICENSED_TDM_ONLY` or `"hosted_ai_upload_allowed": false`, or a SeismoHub `paper_bundles/` bundle marked that
   way. Work from report metadata only: `paper-pdf-harvest status` shows status, channel, tier and page counts and
   never opens a PDF. Copies in `open_pdfs/` are open (CC licence or preprint) and may be read.
2. **`--attach-tdm` is sealed** (exit code 3). Never move, copy or link files from `tdm_bundles/` into
   `open_pdfs/`, and never edit a manifest's tier.
3. **No bypassing.** Do not write browser automation (Playwright, Selenium, CDP), do not imitate a browser's
   User-Agent, do not edit `BOT_WALLED_HOSTS` or the per-host intervals, and never solve CAPTCHAs or work around
   logins. Papers on bot-protected sites go to the user as a browser-download checklist.
4. **Dry run first** for a new or large list: `--dry-run` downloads and verifies but writes nothing. Show the user
   what would happen, then run for real.
5. **Keys are presence-only.** `paper-pdf-harvest keys` prints set / not set. Never print, cat or grep `.env` or
   `keys.env`, and never put a key on a command line.
6. **Be polite.** One harvest per pack at a time. Start big lists with `--limit`, run long ones in the background,
   and ask before an unlimited run over thousands of entries (the per-host intervals make it take hours).

## Step 0: orient

```bash
paper-pdf-harvest --version
paper-pdf-harvest keys                      # which keys and settings are configured (never their values)
```

No key is fine: arXiv, EarthArXiv, Copernicus/EGU, Seismica, open Nature/Springer articles, PMC, Zenodo, HAL,
OSTI, institutional repositories and every other OpenAlex open location need none. Wiley and Elsevier channels
switch on with their keys; OpenAlex cached PDFs with an OpenAlex key.

## Workflow A: harvest a reading list

```bash
paper-pdf-harvest harvest --input-file reading_list.txt --out-dir ~/pack --dry-run
paper-pdf-harvest harvest --input-file reading_list.txt --out-dir ~/pack
paper-pdf-harvest harvest --doi 10.1029/JB082i020p02981 --query "Aki 1957 space and time spectra" --out-dir ~/pack
paper-pdf-harvest status ~/pack --pending
```

The input is one DOI, arXiv ID, URL or citation per line (`#` comments allowed), a CSV/TSV with a DOI in each
line, or a Zotero/BibTeX `.bib` export. Each output line is one paper: `OPEN` (verified open copy saved in
`open_pdfs/`), `TDM-PDF` / `TDM-XML` (licensed copy kept in `tdm_bundles/`, rule 1), `PENDING` (no usable copy),
`DUPLICATE` (the same PDF as another entry). Re-running on the same `--out-dir` resumes: finished papers are
skipped, failed ones are retried after a day (timeouts) or 30 days (everything else). `--retry-failed` retries
failed and held papers now (for example Elsevier XML once the user is on the institutional network, or Wiley HTTP
500s a few days later). `--channels openalex,arxiv` restricts channels; `--no-extras` skips supplements, XML,
open reviews and code/data links.

## Workflow B: PDFs the user downloads in a browser

1. Give the user the checklist: `<pack>/pending_zotero.csv` (or `paper-pdf-harvest status <pack> --pending`).
   Each row has a link and a suggestion.
2. The user downloads the PDFs themselves (Zotero Connector works well), from a network with access.
3. Import with licence triage, dry run first:
   ```bash
   paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack            # prints OPEN->PACK vs TDM->BUNDLE
   paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack --commit   # after the user agrees
   ```
   A Zotero "Export -> files" folder (with its `.bib`) works the same way; the `.bib` DOI is trusted first.

## Workflow C: "why is there no PDF for X?"

```bash
paper-pdf-harvest status ~/pack --doi 10.xxxx/yyyy --attempts
```

| Status | Meaning | Next step |
|---|---|---|
| `success` / `open_pdf` | Open copy verified and saved | none |
| `held_tdm_only` | Licensed copy kept local (rule 1) | local reading only; `--retry-failed` later for an open copy |
| `captcha_or_bot_block` | Only copies on script-blocking sites (OUP/GJI, GeoScienceWorld/BSSA-SRL-TSR, ESSOAr, Wiley web, ScienceDirect, Science, PNAS, MDPI) | browser download -> Workflow B |
| `no_pdf_but_html` | Host served an HTML page (often PMC, nature.com) | open the link in a browser, save the PDF |
| `auth_required` | Login wall / 401 / 403 / 1-page preview | browser download from an entitled network |
| `no_oa_copy` | No channel returned a copy | browser download; author page or repository |
| `transient_error` | Timeout, HTTP 5xx (e.g. Wiley TDM 500) | rerun later or `--retry-failed` |
| `unresolved_citation` | No Crossref record agrees with the citation | add the DOI to the list |
| `unsupported`, `unsupported_content_type` | Not a paper (dataset, software), wrong file, or the identity check failed | usually skip |

The four acceptance checks are: a `%PDF-` header; the size cap; at least 3 pages and 5,000 characters of text; the
title (or the DOI plus a looser title match) on the first two pages. The tier comes from the copy actually
downloaded: `OPEN_CC_BY_OR_PREPRINT` goes to `open_pdfs/`, `LICENSED_TDM_ONLY` stays in `tdm_bundles/`. A publisher
PDF that says "All rights reserved" with no open-licence statement is held, whatever the metadata says.

## Inside SeismoHub

SeismoHub (github.com/WANGYuhan2002/seismohub) runs the same engine against its library database with
`python scripts/harvest_pdfs.py` and ships its own skill (`.claude/skills/seismohub-pdf-harvest/`). Use that one
when the user wants missing PDFs attached to SeismoHub papers. `paper-pdf-harvest status <seismohub>/paper_bundles`
also summarises SeismoHub's reports.

## Reporting back

Tell the user, briefly and in their language: papers processed; open copies by channel; licensed copies held
(local only); papers still without full text, grouped by journal and reason; the path of `pending_zotero.csv`; and
the next action (browser downloads, `--retry-failed` later, or adding a key). Say plainly if a run was a dry run,
was interrupted, or skipped channels for missing keys. Never paste key values or text from held licensed copies.
