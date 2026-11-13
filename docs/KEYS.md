# Accounts and keys

**English** · [中文](KEYS_zh.md)

No key is required: every open channel works without one. Keys add the publisher TDM APIs and OpenAlex's cached
PDFs. This page lists every setting the code reads, where to get it, what it costs, what it unlocks and the terms to
respect. Facts about the services were checked on their own pages on 2026-11-13 (sources linked); prices and
limits change, so check them again before you rely on them.

## Where to put keys

```bash
mkdir -p ~/.config/seismo_harvester && chmod 700 ~/.config/seismo_harvester
cat > ~/.config/seismo_harvester/keys.env <<'EOF'
export ELSEVIER_API_KEY="..."
export WILEY_TDM_TOKEN="..."
export OPENALEX_API_KEY="..."
EOF
chmod 600 ~/.config/seismo_harvester/keys.env
paper-pdf-harvest keys          # shows set / not set, never the values
```

`load_harvest_keys()` reads `$SEISMO_HARVEST_KEYS_FILE`, then `--keys-file`, then
`~/.config/seismo_harvester/keys.env`. It imports only `WILEY_TDM_TOKEN`, `ELSEVIER_API_KEY`,
`ELSEVIER_INSTTOKEN` and `OPENALEX_API_KEY`, and never overrides a variable already set in the environment. A
`.env` in the folder you run from (see [`.env.example`](../.env.example)) is read too. Keep keys outside any
repository or shared folder; `.gitignore` excludes `.env` and `*.env`.

## Summary

| Variable | Service | Unlocks | Cost | Network |
|---|---|---|---|---|
| `SEISMO_HARVEST_UA` | Crossref, DataCite (contact address) | Crossref polite pool; DataCite limit 1,000 instead of 500 requests per 5 minutes | free | any |
| `WILEY_TDM_TOKEN` | Wiley TDM API | Wiley and AGU versions of record (`10.1002`, `10.1111`, `10.1029`) | no extra cost for subscribers' non-commercial research (see below) | your institution's network for subscription content |
| `ELSEVIER_API_KEY` | Elsevier APIs | Elsevier open-access PDFs; full-text XML of subscribed articles (`10.1016`) | free for non-commercial academic use | open access: any; subscribed: institution's network, or with `ELSEVIER_INSTTOKEN` |
| `ELSEVIER_INSTTOKEN` | Elsevier APIs | Subscribed full text when you are not on the institution's network | free, issued to customers on request | any |
| `OPENALEX_API_KEY` | OpenAlex | Cached PDFs from `content.openalex.org` (used for gold-OA works and ESSOAr preprints) | free key: $1/day allowance (about 100 PDFs) | any |

## Contact address: `SEISMO_HARVEST_UA`

Set a User-Agent that names the tool and gives your address:

```bash
export SEISMO_HARVEST_UA="paper-pdf-harvest/1.0 (mailto:you@example.org)"
```

- **Crossref** needs no key. A `mailto` puts you in the "polite" pool. Since 21 July 2026 the limits are 5 requests
  per second for single records (10 polite) and 1 per second for searches (3 polite), with 1 concurrent request
  (5 polite), and they are enforced per address
  ([access and authentication](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/),
  [rate-limit update](https://community.crossref.org/t/refining-rest-api-limits-for-improved-stability-and-reliability/16137)).
  Metadata Plus is a paid, optional service that this tool does not need.
- **DataCite** allows 500 requests per 5 minutes per IP, and 1,000 with an e-mail address in the User-Agent
  ([rate limit](https://support.datacite.org/docs/rate-limit)).
- **OpenAlex** retired its `mailto` polite pool and has ignored `mailto` since February 2026; it uses API keys
  instead ([authentication](https://help.openalex.org/api/authentication/)).

Without the variable the tool sends `paper-pdf-harvest/1.0 (academic-research)`, which carries no personal data.

## Wiley TDM token: `WILEY_TDM_TOKEN`

- **Get it** on Wiley's text-and-data-mining page,
  <https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining>, while logged in to a Wiley Online
  Library account. Wiley's own client documentation describes this:
  [WileyLabs/tdm-client](https://github.com/WileyLabs/tdm-client). The page has you accept Wiley's TDM licence.
  Wiley's site blocked automated checks, so read the licence there when you request the token.
- **Cost:** no extra cost for subscribers' non-commercial research, as Wiley describes it. Check your institution's
  agreement with Wiley first.
- **Unlocks** the version-of-record PDF of Wiley journals, including AGU's (`10.1002`, `10.1111`, `10.1029`),
  through `api.wiley.com/onlinelibrary/tdm/v1/articles/<DOI>`.
  - For a gold or hybrid open-access article (CC licence) the copy is **open** and goes to `open_pdfs/`. The AGU
    and Wiley web sites block scripts, so this API is the only automatic route to those PDFs.
  - For a subscription article the copy is **licensed** and stays in `tdm_bundles/`.
- **Network:** access to subscription content is decided by your public IP address. It works on the institution's
  network or VPN, not off-campus, through single sign-on, or from cloud machines (per the client documentation).
- **Limits:** up to 3 articles per second and 60 requests per 10 minutes. The tool waits 10 s between Wiley
  requests. Wiley TDM regularly answers HTTP 500 for a while: those papers get `transient_error`; rerun later.
- **Terms:** non-commercial research only. Do not redistribute the PDFs, and keep licensed copies local.

## Elsevier API key: `ELSEVIER_API_KEY` (and `ELSEVIER_INSTTOKEN`)

- **Get it** at <https://dev.elsevier.com/apikey/manage> (Elsevier ID sign-in). The key is personal: do not share
  it.
- **Cost:** most Elsevier APIs are free for non-commercial use by academic, public-sector and non-profit
  researchers; commercial use needs a paid licence
  ([ScienceDirect APIs](https://www.elsevier.support/sciencedirect/answer/sciencedirect-apis)). A key alone gives
  no access to content.
- **Unlocks** `10.1016` articles through `api.elsevier.com/content/article/doi/<DOI>`:
  - open-access PDFs, from any network (copy is **open**);
  - for subscribed articles, the full-text XML (FULL view) from an entitled network, plus `mmc` supplements and
    high-resolution figures (copy is **licensed**, kept in `tdm_bundles/`). The PDF endpoint returns only a 1-page
    preview for those, even on the institution's network; the tool rejects it (check 3) and switches to XML.
    `render-xml` turns the XML into a PDF for local reading.
- **Network:** full text is returned only if your IP belongs to an entitled institution, or with an institutional
  token ([authentication](https://dev.elsevier.com/tecdoc_api_authentication.html)).
- **Institutional token** (`ELSEVIER_INSTTOKEN`, sent as `X-ELS-Insttoken`): a secret Elsevier issues only to
  customers, on request through the
  [research products API support hub](https://service.elsevier.com/app/contact/supporthub/researchproductsapis/).
  It must stay on your machine, is sent only over HTTPS, and can be revoked. Most users do not need one; use the
  institution's network or VPN instead.
- **Limits:** the article retrieval API allows 50,000 requests per week and 10 per second
  ([API key settings](https://dev.elsevier.com/api_key_settings.html)). The tool waits 0.5 s between requests. It
  stops asking for subscribed PDFs after three 1-page previews in a row, and for XML after three answers without
  full text, so an unentitled network does not burn the quota.
- **Terms**
  ([TDM policy](https://www.elsevier.com/about/policies-and-standards/text-and-data-mining),
  [API service agreement](https://dev.elsevier.com/api_service_agreement.html)):
  - non-commercial research on subscribed content, through the API only (no scraping);
  - no redistribution of the corpus (share DOI lists instead);
  - quoted snippets of at most 200 characters with a DOI link;
  - outputs must not replace Elsevier products;
  - no training of outside AI models, and AI systems may not store or redistribute the content;
  - delete the content when your access ends.

  Keeping licensed copies in `tdm_bundles/` and away from hosted AI is how this tool follows the AI rules.

## OpenAlex API key: `OPENALEX_API_KEY`

- **Get it:** create an account at <https://openalex.org/signup> and copy the key from
  <https://openalex.org/settings/api-key>.
- **Cost** ([example costs](https://help.openalex.org/access/example-costs/),
  [rate limits](https://help.openalex.org/how-to-use-the-api/rate-limits-and-authentication)):
  - a key is optional for basic use and free;
  - the daily allowance is $0.10 without a key and $1 with a free key, reset at 00:00 UTC;
  - single-work lookups (which the tool uses for metadata) are free;
  - a cached PDF from `content.openalex.org` costs $0.01, so about 100 PDFs a day with a free key;
  - accounts created since 3 November 2026 spend their first $1 at no more than $0.10 per 5 minutes;
  - 10 requests per second without a key, 30 with one.
- **Unlocks** the `openalex_content` channel: OpenAlex's cached PDF of a work, used when the work is gold open
  access and has no other usable open copy (for example GJI since its 2024 switch to open access), and for
  ESSOAr preprints. When the allowance is used up, the channel is skipped for the rest of the run.
- **How the tool sends it:** only to `content.openalex.org` and to free single-work lookups, never to paid list or
  search endpoints. It is removed from every URL in reports and manifests.
- **Terms:** [openalex.org/terms](https://openalex.org/terms). Metadata is CC0. Cached PDFs keep their original
  copyright and OpenAlex grants no extra rights, which is why the tool uses them only for open-access works.

## What needs no key

| Service | Used for | Limits to respect (published) | Tool's interval |
|---|---|---|---|
| arXiv (`export.arxiv.org`) | Metadata and PDFs | 1 request every 3 s, one connection ([API terms](https://info.arxiv.org/help/api/tou.html)); harvest from `export.arxiv.org` | 3 s |
| Crossref | Metadata, licences, `link[]`, citation search | See above | 0.25 s |
| OpenAlex (`api.openalex.org`) | Work records and locations | 10 requests/s without a key | 0.15 s |
| PMC on AWS (`pmc-oa-opendata`) | PMC open-access PDFs, licence per article | No account needed ([PMC on AWS](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)) | 1 s |
| Europe PMC, NCBI E-utilities | DOI to PMCID | Europe PMC 10/s; E-utilities 3/s without a key | 1 s |
| Zenodo | Record files | Guests 60/min, 2,000/h ([developers](https://developers.zenodo.org/)) | 0.6 s |
| DataCite | Repository search, code and data relations | See above | 0.3 s |
| HAL, OSTI, USGS Publications Warehouse, GFZ PubMan, CaltechAUTHORS, EarthArXiv, Research Square, ETH Research Collection, Copernicus, Nature, Springer | Open copies | No key; CaltechAUTHORS answered with a 50/min limit; the ETH Research Collection asks for 10 s between requests | 0.4–1 s; ETH 10 s |
| GitHub | `--download-code` tarballs | 60 requests per hour without a token | 1 s |

## Not used

- **Unpaywall.** Since late 2025 it runs on the OpenAlex database
  ([OpenAlex help](https://help.openalex.org/access/unpaywall/)), so it would add no copies after OpenAlex, and its
  API needs your e-mail address in every request URL. It is switched off (`ENABLE_UNPAYWALL_FALLBACK = False`).
- **Semantic Scholar.** A resolver exists (`resolve_s2_open_copy`) but is not wired into the candidate list.
- **Springer Nature API.** Springer Nature offers keyed APIs: Meta and Open Access on a free plan, and TDM on an
  institutional plan ([subscription plans](https://dev.springernature.com/subscription/)). The tool does not use
  them: open Springer PDFs come straight from `link.springer.com`, and licensed ones are held. A `springer_tdm`
  channel would be a natural addition (see [OTHER_FIELDS.md](OTHER_FIELDS.md)).
- **NCBI API key** and **GitHub token.** Not sent; the tool stays within the keyless limits.

## Terms that apply to every key

- Use TDM keys only for non-commercial research and within your institution's licence.
- Keys are personal. Do not commit them, paste them into chats or issues, or put them on a command line.
- Licensed copies (`LICENSED_TDM_ONLY`) stay on your machine. Do not upload them to hosted AI services, share them
  or redistribute them. Share DOI lists instead.
- Respect the rate limits. Never edit the per-host intervals or the bot-wall list to force requests.

If a key leaks, revoke it at the provider first, then remove it from any repository history (see
[SECURITY.md](../SECURITY.md)).
