# Using it outside seismology

**English** · [中文](OTHER_FIELDS_zh.md)

paper-pdf-harvest grew up on a seismology library, but very little of it is about seismology.

## Why it carries over

The channels are organised by **publisher and open infrastructure, not by journal**:

- The licensed routes key on DOI prefixes: `10.1016` is all of Elsevier, and `10.1002`, `10.1111` and `10.1029`
  are all of Wiley. A handful of publisher groups (Elsevier, Wiley, Springer Nature, Taylor & Francis, SAGE, OUP,
  ACS, IOP, IEEE, ...) publish most journals in every field. A key that covers Wiley covers Wiley's chemistry,
  ecology and economics journals as well as AGU's.
- The open routes are field-neutral: OpenAlex locations, Crossref `link[]`, arXiv, PMC, Zenodo, HAL, DataCite and
  university repositories.
- The four checks and the licence tiers do not depend on the subject at all.

So a reading list from geoscience (AGU, EGU, Elsevier, GSA, ...) works as it is. For other fields the same engine
runs; what changes is which journals are open, which hosts block scripts, and which repositories are worth asking.

## Works as is in any field

- the four acceptance checks and the licence tiers;
- `openalex` and `openalex_repo` (every OpenAlex location, any field);
- `crossref_link`, `arxiv`, `zenodo`, `hal_api`, `pmc_oa_s3` (biomedicine benefits most from PMC);
- `wiley_tdm` and `elsevier_tdm` (all journals of those publishers);
- `nature`, `nature_aap` and `springer_link` (all of Springer Nature);
- `openalex_content`;
- the triage of browser downloads, the reports and the checklist.

## What to tune

All of these are plain lists in the engine files:

| What | Where | Seismology setting | For another field |
|---|---|---|---|
| Gold-OA journals (helps tier publisher copies as open) | `GOLD_OA_ISSNS`, `GOLD_OA_DOI_PATTERNS` in `pmc_oa_and_whitelist_channel.py` | Seismica, GJI 2024+, AGU Advances, Earth and Space Science, Earth Planets Space, ... | Add your field's fully open-access journals: ISSN, licence, first OA year |
| Journals whose web site blocks scripts (triggers the green-OA search) | `WALLED_JOURNAL_PREFIXES` in `upgrades.py` | AGU, Wiley, Elsevier, SSA, OUP, SEG, AAAS, PNAS, GSA, JASA, MDPI, Springer | Add the DOI prefixes of your subscription publishers |
| Hosts that block scripts | `BOT_WALLED_HOSTS` in `fullbundle_harvest.py` | OUP, GeoScienceWorld, MDPI, ESSOAr, AGU and Wiley web, ScienceDirect, Science, PNAS | Add hosts that answer with a challenge. Never remove one to force access |
| Prefixes worth a PMC lookup | `pmc_prefixes` in `upgrades.py` | Science Advances, PNAS, MDPI, PLOS, Frontiers | Add biomedical publishers |
| Repositories by affiliation | `resolve_unified_green_oa` in `deep_oa_and_vor_resolvers.py` | US national labs and DOE (OSTI), USGS, GFZ Potsdam, Caltech | Swap in the national or institutional repositories of your field |
| Preprint servers | `eartharxiv`, `researchsquare`, ESSOAr mapping | EarthArXiv, ESSOAr, EGUsphere, Research Square | bioRxiv / medRxiv, SSRN, PsyArXiv, ChemRxiv, ... (open locations already come through OpenAlex) |
| Code and data links | `CODE_DATA_URL_RE` in `fullbundle_harvest.py` | GitHub, GitLab, Zenodo, figshare, OSF, IRIS, EarthScope | Add your field's data centres (GenBank, PDB, ICPSR, ...) |
| Open-review files | `EGU_REVIEW_PDF_RE` | EGU interactive discussion | Other open-review platforms |

## Adding a publisher API

A licensed channel is a candidate with `kind="tdm_vor"`: a URL, the key in a header, and that header named in
`sensitive_headers` so it is dropped on redirects to other domains. Copy the `wiley_tdm` block in
`FullBundleHarvester.build_candidates`. The tiering, the Crossref second opinion, the seal and the bundles then
apply unchanged. Springer Nature's TDM API, for example, would fit this pattern
([KEYS.md](KEYS.md#not-used)). Check the publisher's TDM terms first.

## Two caveats

- The licence markers that the triage and the "All rights reserved" re-check look for are English phrases. A
  journal that prints its licence only in another language may be held as licensed (safe, but a miss).
- The engine files are synced from SeismoHub (their first lines say so). For your own fork, edit them freely. For
  a change you want here, open an issue or pull request: it is ported to SeismoHub and synced back, so both tools
  stay the same.
