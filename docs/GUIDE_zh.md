# paper-pdf-harvest 使用指南

[English](GUIDE.md) · **中文**

1. [安装](#1-安装)
2. [快速上手](#2-快速上手)
3. [PDF 是怎么拿到的](#3-pdf-是怎么拿到的)
4. [输出、报告与状态](#4-输出报告与状态)
5. [重复运行与 `--retry-failed`](#5-重复运行与---retry-failed)
6. [能拿到什么](#6-能拿到什么)
7. [哪些拿不到，为什么](#7-哪些拿不到为什么)
8. [怎么补缺口](#8-怎么补缺口)
9. [命令参考](#9-命令参考)
10. [Python 接口](#10-python-接口)
11. [Claude Code 的 Agent 技能](#11-claude-code-的-agent-技能)
12. [接入 SeismoHub](#12-接入-seismohub)
13. [与 SeismoHub 阅读清单脚本的区别](#13-与-seismohub-阅读清单脚本的区别)

---

## 1. 安装

需要 Python 3.10 或更新版本。运行时依赖为 `requests`、`PyMuPDF`（PDF 校验和渲染）和 `python-dotenv`。

```bash
git clone https://github.com/WANGYuhan2002/paper-pdf-harvest
cd paper-pdf-harvest
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # 安装 `paper-pdf-harvest` 命令
pip install -e ".[test]"    # 另装 pytest，用于离线测试
```

不安装也可以：`pip install -r requirements.txt`，然后在仓库根目录运行 `python -m paper_pdf_harvest ...`。

密钥是可选的（见 [KEYS_zh.md](KEYS_zh.md)）。放在 `~/.config/seismo_harvester/keys.env`（任何仓库之外），或运行目录下
的 `.env`。`paper-pdf-harvest keys` 会显示找到了哪些，但从不显示值。

## 2. 快速上手

### 2.1 阅读清单模式（本工具）

```bash
paper-pdf-harvest harvest --input-file reading_list.txt --out-dir ~/pack --dry-run   # 只校验，不写任何东西
paper-pdf-harvest harvest --input-file reading_list.txt --out-dir ~/pack
paper-pdf-harvest harvest --doi 10.1029/JB082i020p02981 --doi arXiv:1803.03211 --out-dir ~/pack
paper-pdf-harvest harvest --query "Shapiro Campillo 2005 surface-wave tomography ambient noise" --out-dir ~/pack
paper-pdf-harvest status ~/pack --pending
```

阅读清单每行一条：DOI、DOI 链接、arXiv ID 或 URL、自由格式的引文；以 `#` 开头的行是注释。CSV / TSV 只要每行带有
DOI 也行。`.bib` 导出文件（Zotero、JabRef 等）会逐条读取：有 DOI 用 DOI，没有就用 arXiv ID，再没有就用"标题 +
第一作者 + 年份"。

### 2.2 文献库模式（SeismoHub）

如果你用 [SeismoHub](https://github.com/WANGYuhan2002/seismohub)，同一个引擎可以为文献库补齐缺失的 PDF：

```bash
cd seismohub
python scripts/harvest_pdfs.py --dry-run --limit 20     # 预览，不写入
python scripts/harvest_pdfs.py --limit 200              # 先备份数据库，再挂上开放副本
```

见[第 12 节](#12-接入-seismohub)。

## 3. PDF 是怎么拿到的

对每一条，工具依次：

1. 把它解析成 DOI 和/或 arXiv ID，并取得标题、作者、年份。DOI 查 Crossref，arXiv ID 查 arXiv API，引文用 Crossref
   书目检索，并且只接受与引文相符的记录；
2. 读取这篇论文的 OpenAlex 记录，从中得到 OpenAlex 知道的各个副本，以及正式版（VoR）的许可；
3. 排出一个有序的候选副本列表（3.1），逐个尝试；
4. 礼貌地下载每个候选（3.6），并做校验（3.2）；
5. 按实际拿到的副本判定许可层级（3.3）；
6. 找到第一个开放副本就停。如果先遇到许可副本，会先留着，但继续找开放副本；
7. 视需要收集附加材料（3.5），然后写入输出目录（第 4 节）。

### 3.1 渠道及其顺序

候选分三组，组内按表中顺序尝试。基础引擎（`fullbundle_harvest.py`）定义这三组；升级层（`upgrades.py`，来自
SeismoHub v2.3）为每组增加渠道，命令行总会装上它。

**第 0 组：开放的正式版**（最好的副本：最终文本，可以自由使用）

| 渠道 | 何时使用 | 拿到什么 |
|---|---|---|
| `openalex` | OpenAlex 位置带 `pdf_url`、是正式版、CC 许可 | 出版商开放获取 PDF（Copernicus、Seismica、Nature OA、Frontiers 等） |
| `copernicus` | DOI 为 `10.5194/...` | 按规则构造的 PDF 地址：正式论文或讨论稿预印本 |
| `nature` | DOI 为 `10.1038/...` 且为 CC 许可 | Nature 旗下开放获取 PDF |
| `ethrc` | DOI 为 `10.3929/...`，或论文收录于 ETH Research Collection | 知识库 PDF；只走 robots.txt 允许的路径，请求间隔 10 秒 |
| `nature_aap` | Nature 金色开放获取的待刊文章 | `.pdf` 地址返回 HTML 时，改取加速预览版 `_reference.pdf` |
| `springer_link` | DOI 为 `10.1007/...` 且为 CC 许可 | `link.springer.com/content/pdf/...` |
| `crossref_link` | Seismica，或金色开放获取但没有其他可用开放副本的 DOI | 出版商登记在 Crossref 里的文本挖掘 PDF 链接，且所在站点不屏蔽脚本 |
| `pmc_oa_s3` | 已知 PMCID，或 DOI 前缀为 `10.1126/sciadv.`、`10.1073/pnas.`、`10.3390/`、`10.1371/`、`10.3389/` | NCBI 在 AWS 开放数据桶中的 PMC 开放获取 PDF，附逐篇许可 |
| `openalex_content` | 设置了 `OPENALEX_API_KEY`、OpenAlex 有缓存 PDF、金色开放获取许可、没有其他可用开放副本 | `content.openalex.org` 缓存的 PDF |
| `osti_gov` | DOI 为 `10.2172/...` | 美国能源部报告 PDF（公有领域） |
| `hal_api` | 没有 DOI 的 HAL 链接 | 该 HAL 记录的主文件 |

**第 1 组：许可的正式版**（层级取决于正式版的许可）

| 渠道 | 何时使用 | 拿到什么 |
|---|---|---|
| `wiley_tdm` | DOI 为 `10.1002/`、`10.1111/`、`10.1029/`（AGU），且设置了 `WILEY_TDM_TOKEN` | Wiley TDM 接口提供的出版商 PDF |
| `elsevier_tdm` | DOI 为 `10.1016/`，且设置了 `ELSEVIER_API_KEY` | Elsevier 接口的 PDF。订阅文章只返回 1 页预览，此时工具改取全文 XML（`elsevier_tdm_xml`，FULL 视图），有权限的网络确实会返回 |
| `nature` | DOI 为 `10.1038/` 且不是 CC 许可 | 出版商副本 |
| `nature_aap`、`springer_link` | 同上两家出版商，不是 CC 许可 | 出版商副本 |

**第 2 组：其他开放副本**（录用稿、预印本、知识库）

| 渠道 | 何时使用 | 拿到什么 |
|---|---|---|
| `openalex_repo` | OpenAlex 的知识库位置带 `pdf_url` | 大学和学科知识库、HAL 等 |
| `arxiv` | 从 DOI、链接或 OpenAlex 得到 arXiv ID | `export.arxiv.org/pdf/<id>`，请求间隔 3 秒 |
| `eartharxiv` | DOI 为 `10.31223/...`，或 EarthArXiv 着陆页 | EarthArXiv 下载链接 |
| `zenodo` | DOI 为 `10.5281/zenodo....` | 记录里的正文 PDF（不取补充材料、海报或说明文件） |
| `openalex` | 其余的 OpenAlex `pdf_url`（铜色开放获取、无许可） | 出版商或知识库副本 |
| `researchsquare` | DOI 为 `10.21203/...`，或 Research Square 链接 | CC-BY 预印本 PDF |
| `openalex_content` | 有 OpenAlex 缓存 PDF 的 ESSOAr 预印本，且设置了密钥 | 缓存的预印本 PDF |
| `green_oa_cascade` | 期刊网站屏蔽脚本的论文（前缀 `10.1029`、`10.1002`、`10.1111`、`10.1016`、`10.1785`、`10.1093`、`10.1190`、`10.1126`、`10.1073`、`10.1130`、`10.1121`、`10.3390`、`10.1007`），或 ESSOAr 预印本 | 一个 resolver 依次询问，遇到第一个通过校验的结果就停：OSTI、USGS Publications Warehouse、GFZ PubMan、CaltechAUTHORS（这四个只在作者单位提示相关时才问），然后是 HAL、DataCite 知识库、Crossref "posted-content" 预印本（EarthArXiv、EGUsphere、Research Square）。标题和作者都必须吻合 |

升级层还会：

- 把 OpenAlex 给出的知识库地址改写成直接下载地址：PMC 文章页改写到 PMC 开放数据桶，arXiv DOI 链接改写到
  `export.arxiv.org`，HAL 页面改写到 `/document`，DSpace 7 的 `/bitstreams/<uuid>/download` 改写到 REST 的
  `content` 端点；
- 条目没有 DOI 时，从 `nature.com/articles/...` 链接推断 DOI；
- 对没有副本的 ESSOAr 预印本（`10.22541/essoar...`），通过 Crossref 的 `is-preprint-of` 或严格的标题加作者检索，
  映射到已发表的正式版，再抓取那个 DOI（渠道显示为 `essoar_vor(...)`）；
- 出版商副本下载后再查一遍：如果前两页写着 "All rights reserved" 而没有开放许可声明，就改按许可副本处理，并继续
  尝试剩下的开放副本候选。

`--channels` 可以把一次运行限定在部分渠道（逗号分隔）。列表里有几个名字只是为了与 SeismoHub 兼容：`s2_oa` 的
resolver 还没有接入候选列表；`datacite_repo`、`gfz_repo`、`usgs_pubs`、`crossref_preprint` 都在
`green_oa_cascade` 内部运行。

### 3.2 四道校验

| # | 校验 | 拦下什么 | 失败时的状态 |
|---|---|---|---|
| 1 | 前 1 KB 里有 `%PDF-` | HTML 着陆页、登录页、错误页 | `no_pdf_but_html` 或 `unsupported_content_type` |
| 2 | 大小：至少 40 KB，不超过上限（160 MB，`SEISMO_HARVEST_MAX_BYTES`）；未加密 | 残缺文件、超大文件 | `unsupported_content_type` |
| 3 | 至少 3 页、5000 字符以上的文字（必须有 PyMuPDF，从不放行未校验的文件） | 1–2 页的预览、登录占位页、没有文字层的扫描件 | `auth_required`（页数太少）或 `unsupported_content_type` |
| 4 | 身份：前两页上至少出现标题中 70% 的实词，或者出现 DOI 且实词达到 35% | 下错的论文、只是引用了这个 DOI 的论文 | `unsupported_content_type`（`identity_mismatch`） |

第 4 道校验有两处来自升级层的补充：

- 用同一标题印出的 EGU 大会摘要，不算期刊论文，会被拒绝；
- 发表时改了标题的预印本，标题重合度在 35%–70% 之间时，只有当论文至少有三位作者、且他们的姓氏都出现在页面上时才
  接受。要求全部吻合；四位及以上作者时至少吻合 85%；第一作者和最后一位作者必须吻合。

### 3.3 许可层级

层级按**实际下载到的副本**判定，而不是按论文的开放获取状态：

| 层级 | 何时给出 | 去向 |
|---|---|---|
| `OPEN_CC_BY_OR_PREPRINT` | 知识库或预印本副本；或副本本身带 CC / 公有领域许可；或经许可渠道拿到，但正式版本身是 CC 许可（依据 OpenAlex；OpenAlex 没有时依据出版商在 Crossref 的许可登记） | `open_pdfs/` |
| `LICENSED_TDM_ONLY` | 经机构许可获得的出版商版本（Wiley / Elsevier TDM、订阅下载）、Elsevier 全文 XML，或 PDF 上写着 "All rights reserved" 而没有开放声明的出版商副本 | `tdm_bundles/`，仅限本地 |

每个许可副本的清单里都记录 `"hosted_ai_upload_allowed": false`。写入任何东西之前，`seal.keep_non_open_in_bundle`
会再检查一遍，确保只有开放副本能进入 `open_pdfs/`。`--attach-tdm` 已封住：在接触网络或任何文件之前就以退出码 3 退出。

### 3.4 什么会保存，什么会扣下

- 开放副本保存到 `open_pdfs/`（`<年份>_<第一作者>_<标题>.pdf`）。
- 许可副本保存为 `tdm_bundles/PaperBundle_<DOI>/main_manuscript.pdf`；Elsevier XML 则为 `main_manuscript.xml`。如果
  同时找到了开放副本，bundle 里会以 `app_attached_copy.pdf` 链接它。
- 一旦扣下了许可的正式版，其余的许可或出版商候选都会跳过，只有开放副本还能改进结果。
- 两条清单项解析到同一个 PDF（SHA-256 相同）时，第二条记为重复，不会再写一份文件。

### 3.5 bundle 的附加材料

除非加了 `--no-extras`：

- **Copernicus / EGU：**全文 XML、补充材料 PDF 与 ZIP、讨论页及其公开评审 PDF（审稿意见、作者回复、编辑报告）。
- **Elsevier：**FULL 视图 XML 和 `mmc` 补充材料；只有 XML 的 bundle 还会下载高分辨率插图（最多 40 张）。
- **Nature：**电子补充材料，最多 12 个文件。
- **代码和数据：**指向该 DOI 的 DataCite 关联，以及 PDF 的数据可用性章节、最后几页和链接注释中找到的链接（GitHub、
  GitLab、Zenodo、figshare、OSF、IRIS/EarthScope 等），写入 `companion_code_data/code_and_data_links.json`。
  `--download-code` 还会下载最多三个、每个不超过 50 MB 的 GitHub 压缩包。

视频一律跳过，每个补充材料最多 50 MB。开放论文的附加材料放在 `open_bundles/`。

### 3.6 礼貌访问

- 每个站点的最小请求间隔：arXiv 3 秒；Wiley TDM 10 秒（Wiley 允许每 10 分钟 60 次）；ETH Research Collection
  10 秒（其 robots.txt 的抓取延迟）；Zenodo、OSTI、GFZ 0.6 秒；Elsevier、USGS、`content.openalex.org` 0.5 秒；HAL
  0.4 秒；DataCite 0.3 秒；Crossref 0.25 秒；OpenAlex 0.15 秒；其他站点 1 秒。一次只发一个请求，论文逐篇处理。
- User-Agent 如实写明工具名。设置 `SEISMO_HARVEST_UA` 可以加上你自己的 `mailto:` 地址。
- HTTP 429/502/503/504 重试一次，遵守 `Retry-After`（最多 30 秒）。`content.openalex.org` 报告当日额度用完后，本次
  运行不再向它请求。
- 重定向由程序手动跟随。重定向一旦离开出版商的域名，就丢弃密钥请求头；带密钥的 URL 不会进入报告或清单。
- Elsevier 熔断：连续 3 次拿到订阅文章的 1 页预览后，不再为订阅文章请求 PDF；连续 3 次 XML 没有全文（说明当前
  网络没有权限）后，不再请求 XML。Elsevier 的开放获取 PDF 始终照常尝试。
- 屏蔽脚本的站点（第 7 节）从不请求。

## 4. 输出、报告与状态

### 4.1 输出目录结构

```
<out-dir>/
  open_pdfs/                       只放开放副本
  tdm_bundles/PaperBundle_<DOI>/   许可副本（仅限本地）
     bundle_manifest.json
     main_manuscript.pdf | main_manuscript.xml
     app_attached_copy.pdf         主稿是许可副本时，对应的开放副本
     fulltext_structured.xml  supplements/  figures/  peer_review_rc_ac/  companion_code_data/
  open_bundles/PaperBundle_<DOI>/  开放论文的附加材料（结构相同）
  harvest_report.jsonl             每篇论文每次运行一行
  harvest_summary.tsv              当前状态，每篇论文一行
  pending_zotero.csv               浏览器 / Zotero 下载清单
  _metadata_cache.sqlite           OpenAlex 元数据缓存（7 天）
```

### 4.2 `harvest_report.jsonl`

每篇论文每次运行一个 JSON 对象，主要字段：

- `key`（`doi:...`、`arxiv:...`，引文则是 `q:<哈希>`）、`query`、`doi`、`arxiv_id`、`title`、`journal`、`year`、
  `first_author`；
- `status`、`reason`、`attached` / `attach_reason`、`open_pdf`、`bundle`；
- `app_copy`、`held_copy`、`held_xml`：渠道、来源 URL、类型、版本、许可、层级、`hosted_ai_upload_allowed`、页数、
  身份校验、字节数、SHA-256；
- `attempts[]`：每一次请求的渠道、URL、结果、原因、HTTP 状态、字节数、时间和耗时；
- `open_url`、`suggestion`、`harvested_at`、`tool`。

格式与 SeismoHub 文献库模式的报告一致，所以 `paper-pdf-harvest status` 两种都能读。

### 4.3 `bundle_manifest.json`

依次记录：抓取器版本与时间、标识符、标题、期刊、OpenAlex 摘要（`oa_status`、正式版许可）；然后是
`main_manuscript`、`app_attached`、`held_back_tdm_copy`，各自带层级和 `hosted_ai_upload_allowed`；最后是写入的
文件、附加材料、代码与数据链接，以及每一次尝试。SeismoHub 的许可守卫读的正是这些字段。

### 4.4 状态

| 状态 | 含义 | 怎么办 |
|---|---|---|
| `success`（汇总里为 `open_pdf`） | 开放副本已校验并保存 | 无需处理 |
| `held_tdm_only` | 许可副本留在 `tdm_bundles/` | 在本地阅读；之后 `--retry-failed` 可能找到开放副本 |
| `captcha_or_bot_block` | 只有屏蔽脚本的网站上有副本 | 浏览器下载，然后 `triage` |
| `no_pdf_but_html` | 对方返回了 HTML 页面（常见于 PMC、nature.com） | 在浏览器打开 `open_url`，保存 PDF |
| `auth_required` | 登录墙、401/402/403，或 1–2 页预览 | 在有权限的网络里用浏览器下载 |
| `no_oa_copy` | 所有渠道都没有可下载的副本 | 浏览器下载；查作者主页或知识库 |
| `transient_error` | 超时、HTTP 5xx（例如 Wiley TDM 的 500）、额度用尽 | 一天后自动重试，或 `--retry-failed` |
| `unresolved_citation` | 没有与引文相符的 Crossref 记录 | 在清单里写上 DOI |
| `duplicate` | 与另一条是同一个 PDF | 通常是预印本 DOI 与期刊 DOI；无需处理 |
| `unsupported`、`unsupported_content_type` | 不是论文（数据集、软件、评审意见）、文件不对，或身份校验没通过 | 通常跳过；用 `--attempts` 查看 |

多个渠道都失败时，论文的状态取最能说明问题的那个，顺序为：`transient_error`、`captcha_or_bot_block`、
`auth_required`、`no_pdf_but_html`、`unsupported_content_type`、`no_oa_copy`、`unsupported`。

## 5. 重复运行与 `--retry-failed`

用同一个 `--out-dir` 再运行 `harvest`，会接着上次的输出目录继续：

| 上次结果 | 默认 | `--retry-failed` | `--force` |
|---|---|---|---|
| 已保存开放副本，或为重复 | 跳过 | 跳过 | 重做 |
| 扣下了许可副本 | 跳过 | 重试（寻找开放副本） | 重做 |
| `transient_error` | 一天后重试 | 重试 | 重做 |
| 其他失败 | 30 天后重试 | 重试 | 重做 |

这与 SeismoHub 文献库模式的策略相同。常见用法：

- Wiley TDM 返回 HTTP 500 后，过几天再跑；
- 连上机构网络或 VPN 后，加 `--retry-failed` 再跑，以获取 Elsevier XML；
- 几周后再跑，补上新出现的开放获取副本和预印本。

## 6. 能拿到什么

| 来源 | 需要密钥吗 | 通常结果 |
|---|---|---|
| arXiv、EarthArXiv、Research Square、EGUsphere 预印本 | 不需要 | 预印本（开放） |
| Copernicus / EGU 期刊、Seismica、Frontiers、PLOS、MDPI（经 PMC）、Science Advances（经 PMC）、PNAS 开放文章（经 PMC） | 不需要 | 正式版（开放） |
| Nature 旗下开放获取（Nature Communications、Scientific Reports、Communications Earth & Environment 等） | 不需要 | 正式版（开放） |
| Springer 开放获取文章 | 不需要 | 正式版（开放） |
| OpenAlex 或 DataCite 收录的机构与国家知识库（HAL、ETH Research Collection、CaltechAUTHORS、GFZ、OSTI、USGS、KITopen 等） | 不需要 | 录用稿或正式版（开放） |
| 含有论文的 Zenodo 记录 | 不需要 | 通常是预印本（开放） |
| Wiley / AGU 金色及混合开放获取（正式版为 CC 许可） | `WILEY_TDM_TOKEN`（出版商网站屏蔽脚本） | 正式版（开放） |
| Wiley / AGU 订阅文章 | `WILEY_TDM_TOKEN`，并且在机构网络内 | 正式版（许可，本地） |
| Elsevier 开放获取 | `ELSEVIER_API_KEY` | 正式版（开放） |
| Elsevier 订阅文章 | `ELSEVIER_API_KEY`，并且在有权限的网络内或有 `ELSEVIER_INSTTOKEN` | 带插图的全文 XML（许可，本地）；接口不提供完整 PDF |
| OpenAlex 缓存 PDF（金色开放获取，例如 2024 年起的 GJI） | `OPENALEX_API_KEY` | 正式版（开放），受每日额度限制 |

## 7. 哪些拿不到，为什么

- **屏蔽脚本的网站。**探测时，这些站点对普通脚本请求返回了 Cloudflare 质询。它们列在 `BOT_WALLED_HOSTS`，工具从不
  请求：

  | 站点 | 期刊 |
  |---|---|
  | `academic.oup.com` | GJI 等 OUP 期刊 |
  | `pubs.geoscienceworld.org` | SSA 的 BSSA、SRL、TSR，GSA 期刊等 |
  | `essopenarchive.org` | ESSOAr 预印本 |
  | `agupubs.onlinelibrary.wiley.com`、`onlinelibrary.wiley.com` | AGU / Wiley 网站（请改用 TDM 接口） |
  | `www.sciencedirect.com` | Elsevier 网站（请改用 API） |
  | `www.science.org`、`www.pnas.org`、`www.mdpi.com` | Science、PNAS、MDPI 网站 |

  如果副本只在这些站点上，状态为 `captcha_or_bot_block`。
- **登录墙和订阅**，且没有 TDM 途径：`auth_required`，或被第 3 道校验拦下的 1–2 页预览。
- **任何地方都没有开放副本：**`no_oa_copy`。老论文和预印本少的期刊很常见。
- **只给脚本返回 HTML 的站点**（部分 PMC 和 nature.com 页面）：`no_pdf_but_html`。
- **Elsevier 订阅文章的 PDF：**接口只给 1 页预览，即使在有权限的网络内也一样。你会得到全文 XML（许可，本地），用
  `render-xml` 可以把它转成 PDF 在本地阅读。
- **不是论文：**数据集、软件、评审意见的 DOI 本来就没有论文 PDF（`unsupported`）。

工具不会破解验证码、不会伪装浏览器、不会驱动浏览器，也不会借用你浏览器里的 cookie。这是设计原则，不是缺少的功能。

## 8. 怎么补缺口

1. **清单。**`pending_zotero.csv` 列出所有仍然没有全文的论文，每行有 `open_url`（DOI 链接，或找到的 HTML 页面）和
   `suggestion`。`paper-pdf-harvest status <pack> --pending` 会把它打印出来。
2. **浏览器下载。**在有权限的网络（校园网或 VPN）里打开链接，保存 PDF。Zotero Connector 一键就能保存 PDF 和元数据；
   之后用 Zotero 导出的 `.bib`，分流时就能拿到可信的 DOI。
3. **许可分流（triage）。**
   ```bash
   paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack            # 试运行
   paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack --commit
   ```
   每个 PDF 先要通过第 1–3 道校验，再与输出目录里的论文匹配，依次为：`.bib` 的 DOI；PDF 上印的 DOI（PDF 标题吻合
   才算）；arXiv ID；完全相同的标题；模糊标题（相似度至少 0.92 且唯一，否则列出待人工确认）。然后判定层级，拿不准
   时一律从严：
   - **开放**：预印本 DOI；或 PDF 上有开放获取 / Creative Commons 声明；或 OpenAlex / Crossref 记录正式版为 CC 许可，
     且 PDF 上既没有 "All rights reserved"，也没有机构下载水印；
   - **许可**：其余情况，包括任何带有 "All rights reserved" 或类似 "Downloaded from ... by \<Institution\> user on
     \<date\>" 水印的 PDF。

   开放 PDF 进入 `open_pdfs/`，许可 PDF 进入 `tdm_bundles/` 并标记 `hosted_ai_upload_allowed: false`。输出目录的缓存
   里没有许可信息时，加 `--online-license-check` 会去问 OpenAlex 和 Crossref。
4. **Zotero"导出 → 文件"文件夹。**直接把文件夹传进去：会读取其中的 `.bib`，优先采信里面的 DOI。这相当于 SeismoHub 的
   `match_zotero_export.py` 的独立版本。
5. **以后再试。**`harvest --retry-failed` 立即重试失败的和被扣下的论文；不加的话，失败的到期才重试（第 5 节）。新的
   预印本和知识库副本会陆续出现。
6. **作者主页和知识库。**很多作者会把录用稿放在个人主页或所在机构的知识库。OpenAlex 或 DataCite 收录的知识库已经
   查过了（渠道 `openalex_repo` 和 `green_oa_cascade`）。其他的，下载后运行 `triage`。分流从严：带开放获取或 CC 声明
   的副本保存为开放；只有期刊 "All rights reserved" 字样的副本按许可保存，因为分流无法区分作者自己公开的版本和出版商
   下载的版本。如果你确知那份是开放的，照样可以在本地读，只是不要上传。

分流能识别常见的标志，但识别不了所有订阅 PDF。除非确知许可允许，否则不要把 PDF 上传到云端 AI 服务。

## 9. 命令参考

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

- `harvest --dry-run` 会下载并校验，但什么也不写：不建文件夹、不写缓存、不写报告。
- `status` 接受三种目录：输出目录；SeismoHub 的 `paper_bundles/`（默认读最新报告，`--all-reports` 合并全部）；
  SeismoHub 阅读清单脚本写出的目录。它只读报告元数据，从不打开 PDF 或 XML。
- `render-xml` 把只有 XML 的 Elsevier bundle 转成带插图的 PDF，供本地阅读。结果仍是许可副本：每页都有 "LICENSED
  TDM COPY ... DO NOT UPLOAD TO HOSTED AI" 横幅，清单记录 `hosted_ai_upload_allowed: false`。

设置（环境变量、`.env` 或密钥文件）：

| 变量 | 作用 |
|---|---|
| `SEISMO_HARVEST_UA` | User-Agent，加上 `mailto:` 和你的地址 |
| `WILEY_TDM_TOKEN`、`ELSEVIER_API_KEY`、`ELSEVIER_INSTTOKEN`、`OPENALEX_API_KEY` | 密钥（[KEYS_zh.md](KEYS_zh.md)） |
| `SEISMO_HARVEST_KEYS_FILE` | 额外读取的密钥文件（先于 `~/.config/seismo_harvester/keys.env` 读取） |
| `SEISMO_HARVEST_MAX_BYTES` | 单次下载大小上限（默认 160 MB） |

密钥文件里每行写 `export NAME="value"` 或 `NAME=value`。只读取上表中的密钥名，并且从不覆盖环境里已经设置的变量。

## 10. Python 接口

```python
from pathlib import Path
from paper_pdf_harvest import fullbundle_harvest as fb
from paper_pdf_harvest.cli import build_harvester, key_presence
from paper_pdf_harvest.seal import keep_non_open_in_bundle

harvester = build_harvester(cache_path=Path("pack/_metadata_cache.sqlite"), readonly=False)
key_presence()                                    # 读取密钥文件，只返回布尔值
out = harvester.harvest(fb.PaperRef("p1", doi="10.5194/se-17-825-2026", title="..."))
keep_non_open_in_bundle(fb, out)                  # 封印：out.app_hit 里只会留下 OPEN 副本
if out.app_hit:
    Path("paper.pdf").write_bytes(out.app_hit.data)        # OPEN 层级
elif out.held_hit or out.held_xml:
    fb.write_bundle(out, Path("tdm_bundles"))              # 许可副本：只放本地
print(out.status, out.reason, [a.as_dict() for a in out.attempts])
```

`build_harvester` 会像 SeismoHub 一样，把升级层装进 `fullbundle_harvest` 模块。网络与校验核心只依赖 `requests` 和
PyMuPDF，也可以放到集群或服务器上运行。

## 11. Claude Code 的 Agent 技能

[`.claude/skills/paper-pdf-harvest/SKILL.md`](../.claude/skills/paper-pdf-harvest/SKILL.md) 给 Agent 提供了工作流程和
不可违背的规则：

- 绝不读取许可副本；
- `--attach-tdm` 已封住；
- 不绕过任何保护；
- 先试运行；
- 密钥只报告有或没有；
- 礼貌访问。

在 Claude Code 里打开本仓库就会自动发现项目技能。想在任何地方都能用：

```bash
mkdir -p ~/.claude/skills && ln -s "$PWD/.claude/skills/paper-pdf-harvest" ~/.claude/skills/paper-pdf-harvest
```

然后就可以说"把 reading_list.txt 里这些 DOI 的 PDF 抓下来"或"为什么这篇没有 PDF"。Agent 只根据报告元数据工作，
抓不到的会给你一份浏览器下载清单。

## 12. 接入 SeismoHub

- **同一个引擎。**SeismoHub 的 `services/fullbundle_harvest.py` 和 `scripts/seismohub_upgrade_runner.py` 是本仓库引擎的
  来源。文献库模式在 SeismoHub 里：`python scripts/harvest_pdfs.py [--dry-run] [--limit N] [--retry-failed] ...`。
  它会先备份数据库、从不覆盖已有 PDF、只挂开放副本。那边的阅读清单模式是 `scripts/harvest_literature_list.py`。
- **同一套密钥。**两个工具都读 `~/.config/seismo_harvester/keys.env`，变量名也相同。
- **同一种报告。**`paper-pdf-harvest status <seismohub>/paper_bundles --all-reports` 可以汇总 SeismoHub 文献库的报告。
- **把输出目录导入 SeismoHub。**把 `<pack>/open_pdfs/` 里的文件拖到应用的 **Upload missing PDFs（上传缺失的 PDF）**，
  会按 DOI 和标题匹配到库里的论文；或者运行 `python scripts/zotero_triage_import.py <pack>/open_pdfs`（先试运行，再
  加 `--commit`），它会额外做许可分流。那边的分流同样从严，所以没有许可声明的预印本可能被按许可副本保存。许可副本
  留在输出目录里；如果要在 SeismoHub 里用，让它的文献库模式重新抓取即可，它会把许可副本放进 `paper_bundles/`，其
  许可守卫会让它们远离 AI 分析和 PDF 问答。
- **同一种清单格式。**SeismoHub 的守卫从 `bundle_manifest.json` 读取层级和 `hosted_ai_upload_allowed`，两个工具写的
  正是这个格式。

## 13. 与 SeismoHub 阅读清单脚本的区别

本命令行在独立使用时替代 `scripts/harvest_literature_list.py`。引擎、升级层和封印完全相同，另外增加了：

- 可续跑的输出目录，带重试日期，以及 `--retry-failed`、`--force`、`--limit`；
- 每篇论文的完整报告（`harvest_report.jsonl`），包含每一次尝试；
- arXiv 条目通过 arXiv API 取得标题和作者，身份校验才能通过；像 `2310.01234` 这样的十月份 ID 会被正确识别为 arXiv
  ID；
- 自由格式引文只有在 Crossref 记录与之相符时才接受（否则为 `unresolved_citation`），不会因为一条认不出的引文而抓来
  一篇不相干的论文；
- 支持 `.bib` 输入；跳过 CSV 表头行；
- 开放论文的附加材料放在 `open_bundles/`，`tdm_bundles/` 里只有许可副本；
- 清单里开放副本的路径改为相对于输出目录；
- 基于输出目录的 `triage`（不需要数据库）、同时支持输出目录和 SeismoHub 的 `status`，以及 `keys`。
