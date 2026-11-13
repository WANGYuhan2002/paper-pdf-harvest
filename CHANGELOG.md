# Changelog

## Unreleased

- `harvest --keys-file` and `keys --keys-file` now take precedence over `~/.config/seismo_harvester/keys.env`, as
  [docs/KEYS.md](docs/KEYS.md) says. A key set in both files used to come from the default file.
- The command line uses the synced `citations.arxiv_metadata` and `citations.citation_agrees` instead of its own
  copies. The only difference: an arXiv ID that the arXiv API rejects no longer gets the title "Error".

## 1.0.0 (2026-11-13)

First standalone release of SeismoHub's full-text PDF harvesting.

- Engine synced from SeismoHub: Full-Bundle harvester `2026-11-08.2` with the v2.3 upgrade layer (about twenty
  open channels plus the Wiley and Elsevier TDM APIs, four acceptance checks, licence tiers from the downloaded
  copy, the "All rights reserved" re-check and the seal), the Elsevier XML renderer, licence triage and the PDF
  matcher.
- Command line `paper-pdf-harvest` with `harvest`, `triage`, `status`, `keys` and `render-xml`.
- Differences from SeismoHub's reading-list script:
  - resumable packs with retry dates, `--retry-failed`, `--force` and `--limit`;
  - a per-paper report with every attempt (`harvest_report.jsonl`);
  - arXiv entries resolved through the arXiv API, so the identity check can pass;
  - free-form citations accepted only when the Crossref record agrees with them;
  - `.bib` input;
  - `open_bundles/` for extras of open papers;
  - manifests without absolute paths;
  - triage against a pack instead of a database.
- Bilingual documentation (English and Chinese), an agent skill for Claude Code, offline tests and CI with a
  repository hygiene check.
