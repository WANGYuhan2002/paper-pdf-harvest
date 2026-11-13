# 用到地震学以外

[English](OTHER_FIELDS.md) · **中文**

paper-pdf-harvest 是在一个地震学文献库上成长起来的，但其中真正与地震学有关的部分很少。

## 为什么能平移

渠道是**按出版商和开放基础设施组织的，而不是按期刊**：

- 许可渠道按 DOI 前缀匹配：`10.1016` 就是整个 Elsevier，`10.1002`、`10.1111`、`10.1029` 就是整个 Wiley。各学科的
  期刊大多出自少数几大出版集团（Elsevier、Wiley、Springer Nature、Taylor & Francis、SAGE、OUP、ACS、IOP、IEEE 等）。
  一个能覆盖 Wiley 的密钥，覆盖的不只是 AGU，还有 Wiley 的化学、生态学、经济学期刊。
- 开放渠道与学科无关：OpenAlex 的副本位置、Crossref `link[]`、arXiv、PMC、Zenodo、HAL、DataCite 和大学知识库。
- 四道校验和许可层级与学科完全无关。

所以地学的阅读清单（AGU、EGU、Elsevier、GSA 等）可以直接用。换到其他学科，引擎照样运行；变的只是哪些期刊开放、
哪些站点屏蔽脚本、哪些知识库值得去问。

## 任何学科都直接可用

- 四道校验和许可层级；
- `openalex` 与 `openalex_repo`（OpenAlex 的所有位置信息，覆盖所有学科）；
- `crossref_link`、`arxiv`、`zenodo`、`hal_api`、`pmc_oa_s3`（生物医学从 PMC 受益最大）；
- `wiley_tdm` 与 `elsevier_tdm`（这两家出版商的全部期刊）；
- `nature`、`nature_aap` 与 `springer_link`（整个 Springer Nature）；
- `openalex_content`；
- 浏览器下载的许可分流、报告和下载清单。

## 需要调整的地方

下面这些都是引擎文件里的普通列表：

| 内容 | 位置 | 地震学的设置 | 换到其他学科 |
|---|---|---|---|
| 金色开放获取期刊（帮助把出版商副本判为开放） | `pmc_oa_and_whitelist_channel.py` 中的 `GOLD_OA_ISSNS`、`GOLD_OA_DOI_PATTERNS` | Seismica、2024 年起的 GJI、AGU Advances、Earth and Space Science、Earth Planets Space 等 | 加上你所在学科的全开放获取期刊：ISSN、许可、开始开放的年份 |
| 网站屏蔽脚本的期刊（触发绿色开放获取检索） | `upgrades.py` 中的 `WALLED_JOURNAL_PREFIXES` | AGU、Wiley、Elsevier、SSA、OUP、SEG、AAAS、PNAS、GSA、JASA、MDPI、Springer | 加上你所在学科订阅出版商的 DOI 前缀 |
| 屏蔽脚本的站点 | `fullbundle_harvest.py` 中的 `BOT_WALLED_HOSTS` | OUP、GeoScienceWorld、MDPI、ESSOAr、AGU 与 Wiley 网站、ScienceDirect、Science、PNAS | 加上返回质询的站点；绝不要为了强行访问而删掉条目 |
| 值得查 PMC 的前缀 | `upgrades.py` 中的 `pmc_prefixes` | Science Advances、PNAS、MDPI、PLOS、Frontiers | 加上生物医学出版商 |
| 按作者单位询问的知识库 | `deep_oa_and_vor_resolvers.py` 中的 `resolve_unified_green_oa` | 美国国家实验室与能源部（OSTI）、USGS、GFZ Potsdam、Caltech | 换成你所在学科的国家或机构知识库 |
| 预印本服务器 | `eartharxiv`、`researchsquare`、ESSOAr 映射 | EarthArXiv、ESSOAr、EGUsphere、Research Square | bioRxiv / medRxiv、SSRN、PsyArXiv、ChemRxiv 等（它们的开放位置已经通过 OpenAlex 进来了） |
| 代码与数据链接 | `fullbundle_harvest.py` 中的 `CODE_DATA_URL_RE` | GitHub、GitLab、Zenodo、figshare、OSF、IRIS、EarthScope | 加上你所在学科的数据中心（GenBank、PDB、ICPSR 等） |
| 公开评审文件 | `EGU_REVIEW_PDF_RE` | EGU 的交互式讨论 | 其他公开评审平台 |

## 新增一个出版商接口

一个许可渠道就是一个 `kind="tdm_vor"` 的候选：一个 URL、放在请求头里的密钥，再把这个请求头写进
`sensitive_headers`，这样重定向到其他域名时它会被丢弃。照着 `FullBundleHarvester.build_candidates` 里 `wiley_tdm`
那一段写就行。之后的层级判定、Crossref 第二意见、封印和 bundle 都原样适用。比如 Springer Nature 的 TDM 接口就可以
这样接（见 [KEYS_zh.md](KEYS_zh.md#不使用的服务)）。动手前先读该出版商的 TDM 条款。

## 两点提醒

- 分流和 "All rights reserved" 复查所寻找的许可标志都是英文短语。如果某本期刊只用其他语言印许可信息，它的副本可能被
  当作许可副本扣下（安全，但会漏掉）。
- 引擎文件是从 SeismoHub 同步来的（文件第一行有说明）。自己的分支里可以随意改；希望改进进入本仓库的话，请开 issue
  或 pull request，改动会先移植到 SeismoHub 再同步回来，保证两个工具一致。
