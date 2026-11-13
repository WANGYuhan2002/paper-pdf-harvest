# Measured coverage, strengths and weaknesses

**English** · [中文](RESULTS_zh.md)

## Where the numbers come from

These are aggregate numbers from the harvest reports of a SeismoHub library: 18 library-mode runs between
8 and 10 November 2026, covering 2,445 distinct papers (4,845 paper-runs). They were computed from report metadata
only (status, channel, tier, DOI prefix, journal); no PDF or licensed copy was opened.

The context matters:

- **Field:** seismology and geophysics. Mostly 2025–2026 papers, plus classics and preprints.
- **Keys:** a Wiley TDM token, an Elsevier API key and an OpenAlex key were configured.
- **Network:** some runs were on an institutional network, which Elsevier subscription XML needs.
- **Engine versions:** the runs span three days of development. Some channel names in older reports (`gfz_repo`,
  `hal_api`, `datacite_repo`, `crossref_preprint`) are separate steps that the current `green_oa_cascade` runs as
  one; `s2_oa` (Semantic Scholar) has since been dropped.

A paper's result is its best outcome over all runs (an open copy beats a licensed copy, which beats nothing).

## Outcome per paper

| Outcome | Papers | Share |
|---|---:|---:|
| Open copy found, verified and attached | 1,562 | 63.9% |
| Licensed copy found and kept local (`LICENSED_TDM_ONLY`) | 205 | 8.4% |
| Same PDF as another paper (duplicate, usually a preprint and its journal DOI) | 41 | 1.7% |
| No full text | 637 | 26.1% |
| **Total** | **2,445** | |

The 205 licensed copies include 26 that an early run attached before the 9 November seal; they were detached and
are held like the others.

Of the 1,562 open copies, 865 are the published version, 22 an accepted manuscript, 599 a submitted version or
preprint, and 76 of unknown version. 437 of them came through a licensed TDM channel (Wiley 286, Elsevier 148,
ESSOAr mapped to Wiley 3) because the version of record itself is CC-licensed. Without the Wiley token most of the
286 would need another route, since the AGU and Wiley web sites block scripts.

Papers without full text, by status: `no_oa_copy` 547, `captcha_or_bot_block` 47, `transient_error` 17,
`unsupported` 9, `auth_required` 9, `unsupported_content_type` 8.

For comparison, the library as a whole (2,503 papers, including PDFs uploaded by hand) has a PDF attached for
1,556 papers (62%).

## By publisher (DOI prefix)

| Prefix | Publisher / source | Papers | Open | Licensed (local) | None |
|---|---|---:|---:|---:|---:|
| `10.1029` | AGU (Wiley) | 394 | 313 (79%) | 78 | 3 |
| no DOI | mostly arXiv preprints | 382 | 364 (95%) | 0 | 5 |
| `10.1016` | Elsevier | 264 | 162 (61%) | 102 (XML) | 0 |
| `10.1785` | Seismological Society of America (BSSA, SRL, TSR) | 251 | 35 (14%) | 2 | 214 |
| `10.1038` | Nature Portfolio | 224 | 210 (94%) | 3 | 7 |
| `10.22541` | ESSOAr preprints | 180 | 28 (16%) | 1 | 146 |
| `10.1093` | Oxford University Press (GJI) | 168 | 102 (61%) | 1 | 65 |
| `10.31223` | EarthArXiv | 126 | 123 (98%) | 0 | 0 |
| `10.5281` | Zenodo (mostly datasets and software) | 109 | 7 (6%) | 0 | 96 |
| `10.1190` | SEG (Geophysics, The Leading Edge) | 55 | 3 (5%) | 1 | 51 |
| `10.26443` | Seismica | 44 | 44 (100%) | 0 | 0 |
| `10.3929` | ETH Research Collection | 42 | 41 (98%) | 0 | 1 |
| `10.1126` | AAAS (Science, Science Advances) | 41 | 29 (71%) | 0 | 12 |
| `10.3390` | MDPI | 36 | 35 (97%) | 0 | 1 |
| `10.5194` | Copernicus / EGU (incl. General Assembly abstracts) | 35 | 20 (57%) | 0 | 14 |
| `10.48550` | arXiv DOIs | 19 | 12 (63%) | 0 | 0 |
| `10.1111` | Wiley (incl. GJI before 2013) | 18 | 6 (33%) | 12 | 0 |
| `10.1073` | PNAS | 10 | 5 (50%) | 0 | 5 |

Rows can add up to less than the paper count: the rest are duplicates.

## Open copies by channel

| Channel | Papers | | Channel | Papers |
|---|---:|---|---|---:|
| `arxiv` | 378 | | `pmc_oa_s3` | 64 |
| `wiley_tdm` (CC-licensed VoR) | 286 | | `nature` | 27 |
| `openalex` | 226 | | `crossref_link` | 16 |
| `elsevier_tdm` (open access) | 148 | | `nature_aap`, `copernicus`, `datacite_repo` | 8 each |
| `openalex_repo` | 111 | | `zenodo`, `osti_gov` | 7 each |
| `eartharxiv` | 107 | | `essoar_vor(wiley_tdm)` | 3 |
| `openalex_content` | 85 | | `gfz_repo` | 2 |
| `ethrc` | 69 | | `hal_api`, `crossref_preprint` | 1 each |

Licensed copies were held from `elsevier_tdm_xml` (102), `wiley_tdm` (68 plus the 26 detached ones),
`springer_link` (5) and `openalex_content` (4). The last two are publisher PDFs that said "All rights reserved".

## Success rate per attempt

Every request in every run. A low rate is not always bad: some channels are cheap last resorts.

| Channel | Verified / attempts | Main failure |
|---|---:|---|
| `arxiv` | 716 / 717 | none |
| `eartharxiv` | 187 / 193 | wrong file type (6) |
| `copernicus` | 16 / 16 | none |
| `elsevier_tdm_xml` | 111 / 111 | none (only tried from an entitled network) |
| `ethrc` | 115 / 131 | no PDF in the record (15) |
| `openalex_repo` | 210 / 251 | bot-walled hosts (17) |
| `openalex_content` | 93 / 130 | daily allowance used up (32) |
| `wiley_tdm` | 494 / 827 | HTTP 500 / timeouts (329) |
| `nature` | 50 / 89 | HTML instead of PDF (24), login (12) |
| `pmc_oa_s3` | 143 / 284 | not in the PMC open-access subset (139) |
| `openalex` | 390 / 1,286 | skipped bot-walled host (837) |
| `elsevier_tdm` | 148 / 523 | 1-page preview of a subscribed PDF (375) |
| `zenodo` | 21 / 217 | record has no paper PDF (187) |
| `crossref_link` | 20 / 214 | no usable link registered (191) |
| `osti_gov`, `hal_api`, `gfz_repo`, `datacite_repo`, `usgs_pubs`, `s2_oa`, `crossref_preprint` | 20 / 316 in total | nothing found |

## Strengths

- **Correct copies.** Four checks per PDF, including an identity check against the title and DOI, keep previews,
  login pages, conference abstracts and wrong papers out. The arXiv channel verified 716 of 717 downloads.
- **Licence-correct by construction.** The tier comes from the copy actually downloaded, with a second opinion from
  Crossref and a re-check of the PDF's own text. Licensed copies are held, never handed out, and the seal holds
  even if the engine is patched.
- **High coverage where the infrastructure is open:** EarthArXiv, Seismica, MDPI, Nature Portfolio, arXiv and the
  ETH Research Collection were all at 94–100%. AGU reached 99% with the Wiley token (79% open, 20% licensed),
  and Elsevier 100% from an entitled network (61% open, 39% licensed XML).
- **Polite and transparent.** Per-host intervals, circuit breakers and no bypassing. Every attempt is recorded
  with its URL, HTTP status and reason, so a missing paper can always be explained.
- **The gaps are handled, not hidden.** Every missing paper gets a checklist row with a link and a next step, and
  `triage` brings browser downloads back with the same licence rules.
- **Bundles, not just PDFs.** EGU XML and open reviews, Elsevier XML with figures and supplements, Nature
  supplements, and code and data links.

## Weaknesses

- **Script-blocking publishers.** GeoScienceWorld (SSA journals: 14% open), OUP (GJI before 2024), ESSOAr (16%),
  Science, PNAS and the AGU, Wiley and ScienceDirect web sites block scripted downloads. Without a TDM API or an
  open copy elsewhere, these papers need a browser. The tool will not work around this.
- **Subscription journals without a TDM route** (SEG at 5%, SSA) depend on open copies elsewhere, which are rare
  for those journals.
- **Elsevier subscribed articles come as XML, not PDF**, and only from an entitled network. `render-xml` makes a
  readable PDF, but not the publisher's layout.
- **Wiley TDM is unreliable at times.** 329 attempts ended in HTTP 500 or timeouts; reruns days later succeeded.
  The 10 s interval also makes large Wiley batches slow.
- **The OpenAlex cache is rationed:** about 100 PDFs a day with a free key.
- **The green-OA cascade has a low yield.** 20 hits in 316 attempts. It is a cheap last resort, not a main
  channel.
- **Zenodo DOIs are mostly datasets and software.** 96 of the 109 had no paper PDF, which is correct but shows as a
  miss.
- **The identity check is a heuristic.** A retitled preprint with fewer than three authors is rejected (a false
  miss). A generic title shared by two papers could in principle pass (a false hit), which the DOI and co-author
  rules make unlikely.
- **The licence triage of browser downloads relies on markers** (CC statements, "All rights reserved",
  institution download stamps), most of them English. It fails closed, but it cannot recognise every
  subscription PDF.
- **Tuned for geoscience:** the gold-OA journal list, the walled-journal prefixes, the affiliation hints of the
  cascade (US national labs, USGS, GFZ, Caltech) and the data-repository patterns (IRIS, EarthScope). See
  [OTHER_FIELDS.md](OTHER_FIELDS.md).
- **Sequential.** One paper at a time, with per-host intervals. Two full library runs took 81 and 90 minutes for
  1,818 and 2,092 papers (about 2.6 s per paper). A Wiley retry of 73 papers took 15 minutes, because Wiley
  requests are 10 s apart.
- **Etiquette gaps.** The Crossref interval (0.25 s) does not distinguish search requests, which have a public
  limit of 1 per second. In practice they are interleaved with other hosts, but large citation lists should set
  `SEISMO_HARVEST_UA` with a `mailto`. The NCBI E-utilities fallback sends no `tool`/`email` parameters.
- **Partial channels.** The `ethrc` channel serves one institution's repository; other DSpace repositories are
  reached only through OpenAlex locations and the URL rewriter. (`s2_oa`, Semantic Scholar, has been dropped: its 27
  attempts in these runs found no copy, and the current engine never called it.)
