# 账号与密钥

[English](KEYS.md) · **中文**

一个密钥都不是必需的：所有开放渠道都不用密钥。密钥能多出出版商的 TDM 接口和 OpenAlex 缓存 PDF。本页列出代码读取的
每一项设置：去哪里申请、费用、能解锁什么、需要遵守哪些条款。各服务的信息于 2026-11-13 在其官方页面核对过（附来源
链接）。价格和限额会变，依赖之前请再核对一次。

## 密钥放在哪里

```bash
mkdir -p ~/.config/seismo_harvester && chmod 700 ~/.config/seismo_harvester
cat > ~/.config/seismo_harvester/keys.env <<'EOF'
export ELSEVIER_API_KEY="..."
export WILEY_TDM_TOKEN="..."
export OPENALEX_API_KEY="..."
EOF
chmod 600 ~/.config/seismo_harvester/keys.env
paper-pdf-harvest keys          # 只显示"已设置 / 未设置"，从不显示值
```

`load_harvest_keys()` 依次读取 `$SEISMO_HARVEST_KEYS_FILE`、`--keys-file`、`~/.config/seismo_harvester/keys.env`。它
只导入 `WILEY_TDM_TOKEN`、`ELSEVIER_API_KEY`、`ELSEVIER_INSTTOKEN` 和 `OPENALEX_API_KEY`，并且从不覆盖环境里已经设置
的变量。运行目录下的 `.env`（见 [`.env.example`](../.env.example)）也会读取。密钥请放在任何仓库和共享文件夹之外；
`.gitignore` 已排除 `.env` 和 `*.env`。

## 一览

| 变量 | 服务 | 解锁什么 | 费用 | 网络 |
|---|---|---|---|---|
| `SEISMO_HARVEST_UA` | Crossref、DataCite（联系邮箱） | Crossref 礼貌池；DataCite 限额从每 5 分钟 500 次提高到 1000 次 | 免费 | 任意 |
| `WILEY_TDM_TOKEN` | Wiley TDM 接口 | Wiley 和 AGU 的正式版（`10.1002`、`10.1111`、`10.1029`） | 订阅机构的非商业研究不另收费（见下文） | 订阅内容需在机构网络内 |
| `ELSEVIER_API_KEY` | Elsevier 接口 | Elsevier 开放获取 PDF；订阅文章的全文 XML（`10.1016`） | 非商业学术用途免费 | 开放获取：任意；订阅：机构网络，或配合 `ELSEVIER_INSTTOKEN` |
| `ELSEVIER_INSTTOKEN` | Elsevier 接口 | 不在机构网络时获取订阅全文 | 免费，向订阅客户按申请发放 | 任意 |
| `OPENALEX_API_KEY` | OpenAlex | `content.openalex.org` 的缓存 PDF（用于金色开放获取论文和 ESSOAr 预印本） | 免费密钥：每天 1 美元额度（约 100 个 PDF） | 任意 |

## 联系邮箱：`SEISMO_HARVEST_UA`

设置一个写明工具名和你邮箱的 User-Agent：

```bash
export SEISMO_HARVEST_UA="paper-pdf-harvest/1.0 (mailto:you@example.org)"
```

- **Crossref** 不需要密钥。带上 `mailto` 就进入"礼貌池"。自 2026 年 7 月 21 日起，单条记录每秒 5 次（礼貌池 10 次），
  检索每秒 1 次（礼貌池 3 次），并发 1 个（礼貌池 5 个），按邮箱地址计算
  （[访问与认证](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/)、
  [限额调整公告](https://community.crossref.org/t/refining-rest-api-limits-for-improved-stability-and-reliability/16137)）。
  Metadata Plus 是可选的付费服务，本工具用不到。
- **DataCite** 每个 IP 每 5 分钟 500 次；User-Agent 里带邮箱可到 1000 次
  （[限额](https://support.datacite.org/docs/rate-limit)）。
- **OpenAlex** 已取消 `mailto` 礼貌池，自 2026 年 2 月起忽略 `mailto`，改用 API 密钥
  （[认证](https://help.openalex.org/api/authentication/)）。

不设置时，工具发送 `paper-pdf-harvest/1.0 (academic-research)`，不含任何个人信息。

## Wiley TDM 令牌：`WILEY_TDM_TOKEN`

- **申请：**登录 Wiley Online Library 账号后，在 Wiley 的文本与数据挖掘页面
  <https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining> 获取。Wiley 自己的客户端文档也是这么
  写的：[WileyLabs/tdm-client](https://github.com/WileyLabs/tdm-client)。页面会要求你接受 Wiley 的 TDM 许可；该网站
  拦截了自动检查，所以条款请在申请时到页面上阅读。
- **费用：**按 Wiley 的说法，订阅机构的非商业研究不另收费。请先确认你所在机构与 Wiley 的协议。
- **解锁：**通过 `api.wiley.com/onlinelibrary/tdm/v1/articles/<DOI>` 获取 Wiley 期刊（含 AGU 期刊，`10.1002`、
  `10.1111`、`10.1029`）的正式版 PDF。
  - 金色或混合开放获取的文章（CC 许可）：副本为**开放**，进入 `open_pdfs/`。AGU 和 Wiley 网站屏蔽脚本，这个接口是
    自动拿到这些 PDF 的唯一途径。
  - 订阅文章：副本为**许可**，留在 `tdm_bundles/`。
- **网络：**能否获取订阅内容由你的公网 IP 决定。在机构网络或 VPN 上可以；校外、单点登录或云服务器上不行（据客户端
  文档）。
- **限额：**每秒最多 3 篇，每 10 分钟最多 60 次请求。工具在两次 Wiley 请求之间等待 10 秒。Wiley TDM 时常会有一段时间
  返回 HTTP 500，这些论文记为 `transient_error`，过一阵再跑即可。
- **条款：**仅限非商业研究；不得再分发 PDF；许可副本只留在本地。

## Elsevier API 密钥：`ELSEVIER_API_KEY`（以及 `ELSEVIER_INSTTOKEN`）

- **申请：**<https://dev.elsevier.com/apikey/manage>（用 Elsevier ID 登录）。密钥属于个人，不要共享。
- **费用：**大多数 Elsevier 接口对学术、公共部门和非营利研究人员的非商业用途免费；商业用途需要付费许可
  （[ScienceDirect APIs](https://www.elsevier.support/sciencedirect/answer/sciencedirect-apis)）。只有密钥本身并不能
  访问任何内容。
- **解锁：**通过 `api.elsevier.com/content/article/doi/<DOI>` 获取 `10.1016` 的文章：
  - 开放获取 PDF，任何网络都可以（副本为**开放**）；
  - 订阅文章：在有权限的网络内获取全文 XML（FULL 视图），以及 `mmc` 补充材料和高分辨率插图（副本为**许可**，留在
    `tdm_bundles/`）。这类文章的 PDF 接口只返回 1 页预览，在机构网络内也一样；工具会用第 3 道校验拒绝它，改取 XML。
    `render-xml` 可以把 XML 转成 PDF 供本地阅读。
- **网络：**只有当你的 IP 属于有权限的机构，或带有机构令牌时，才返回全文
  （[认证说明](https://dev.elsevier.com/tecdoc_api_authentication.html)）。
- **机构令牌**（`ELSEVIER_INSTTOKEN`，以 `X-ELS-Insttoken` 请求头发送）：Elsevier 只发给订阅客户的密文，通过
  [研究产品 API 支持中心](https://service.elsevier.com/app/contact/supporthub/researchproductsapis/)申请。它必须只留在
  你的电脑上，只通过 HTTPS 发送，可能被随时吊销。多数用户用不到，在机构网络或 VPN 上运行即可。
- **限额：**文章获取接口每周 50,000 次、每秒 10 次（[密钥设置](https://dev.elsevier.com/api_key_settings.html)）。工具
  请求间隔 0.5 秒。连续三次拿到订阅 PDF 的 1 页预览后不再请求订阅 PDF，连续三次 XML 没有全文后不再请求 XML，免得在
  没有权限的网络上浪费额度。
- **条款**（[TDM 政策](https://www.elsevier.com/about/policies-and-standards/text-and-data-mining)、
  [API 服务协议](https://dev.elsevier.com/api_service_agreement.html)）：
  - 只能对订阅内容做非商业研究，并且只能通过接口获取（不得爬取网页）；
  - 不得再分发语料，改为分享 DOI 列表；
  - 引用片段不超过 200 个字符，并附 DOI 链接；
  - 产出不得替代 Elsevier 的产品；
  - 不得用于训练外部 AI 模型，AI 系统不得存储或再分发这些内容；
  - 访问权限终止后须删除内容。

  本工具把许可副本留在 `tdm_bundles/`、不交给云端 AI，就是为了遵守这些关于 AI 的规定。

## OpenAlex API 密钥：`OPENALEX_API_KEY`

- **申请：**在 <https://openalex.org/signup> 注册账号，然后在 <https://openalex.org/settings/api-key> 复制密钥。
- **费用**（[费用示例](https://help.openalex.org/access/example-costs/)、
  [限额](https://help.openalex.org/how-to-use-the-api/rate-limits-and-authentication)）：
  - 基本使用不需要密钥，密钥本身免费；
  - 每日额度：没有密钥 0.10 美元，有免费密钥 1 美元，UTC 0 点重置；
  - 单篇查询免费（工具用它取元数据）；
  - 从 `content.openalex.org` 下载一个缓存 PDF 是 0.01 美元，所以免费密钥每天大约 100 个 PDF；
  - 2026 年 11 月 3 日以后创建的账号，前 1 美元每 5 分钟最多花 0.10 美元；
  - 速率：没有密钥每秒 10 次，有密钥每秒 30 次。
- **解锁 `openalex_content` 渠道**，即 OpenAlex 缓存的论文 PDF。两种情况会用到：论文是金色开放获取且没有其他可用的
  开放副本（例如 2024 年转为开放获取后的 GJI）；ESSOAr 预印本。额度用完后，本次运行不再使用这个渠道。
- **工具如何发送它：**只发给 `content.openalex.org` 和免费的单篇查询，从不发给付费的列表或检索接口；报告和清单里的
  所有 URL 都会去掉它。
- **条款：**[openalex.org/terms](https://openalex.org/terms)。元数据为 CC0；缓存的 PDF 保留原有版权，OpenAlex 不授予
  额外权利，所以工具只对开放获取论文使用它们。

## 不需要密钥的服务

| 服务 | 用途 | 需要遵守的限额（官方公布） | 工具的间隔 |
|---|---|---|---|
| arXiv（`export.arxiv.org`） | 元数据和 PDF | 每 3 秒 1 次请求、一个连接（[API 条款](https://info.arxiv.org/help/api/tou.html)）；批量获取请用 `export.arxiv.org` | 3 秒 |
| Crossref | 元数据、许可、`link[]`、引文检索 | 见上文 | 0.25 秒 |
| OpenAlex（`api.openalex.org`） | 论文记录和副本位置 | 没有密钥每秒 10 次 | 0.15 秒 |
| AWS 上的 PMC（`pmc-oa-opendata`） | PMC 开放获取 PDF，逐篇许可 | 无需账号（[PMC on AWS](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)） | 1 秒 |
| Europe PMC、NCBI E-utilities | DOI 转 PMCID | Europe PMC 每秒 10 次；E-utilities 没有密钥每秒 3 次 | 1 秒 |
| Zenodo | 记录中的文件 | 访客每分钟 60 次、每小时 2000 次（[开发者文档](https://developers.zenodo.org/)） | 0.6 秒 |
| DataCite | 知识库检索、代码与数据关联 | 见上文 | 0.3 秒 |
| HAL、OSTI、USGS Publications Warehouse、GFZ PubMan、CaltechAUTHORS、EarthArXiv、Research Square、ETH Research Collection、Copernicus、Nature、Springer | 开放副本 | 都不需要密钥；CaltechAUTHORS 返回的限额为每分钟 50 次；ETH Research Collection 要求请求间隔 10 秒 | 0.4–1 秒；ETH 10 秒 |
| GitHub | `--download-code` 下载压缩包 | 没有令牌每小时 60 次 | 1 秒 |

## 不使用的服务

- **Unpaywall。**自 2025 年底起它运行在 OpenAlex 的数据库上（[OpenAlex 帮助](https://help.openalex.org/access/unpaywall/)），
  在 OpenAlex 之后再查不会多出副本；而且它的接口要在每个请求 URL 里带上你的邮箱。已关闭
  （`ENABLE_UNPAYWALL_FALLBACK = False`）。
- **Semantic Scholar。**代码里有 resolver（`resolve_s2_open_copy`），但还没有接入候选列表。
- **Springer Nature API。**Springer Nature 提供需要密钥的接口：Meta 和 Open Access 有免费方案，TDM 接口属于机构方案
  （[订阅方案](https://dev.springernature.com/subscription/)）。本工具没有使用它们：开放的 Springer PDF 直接从
  `link.springer.com` 获取，许可的则扣下。加一个 `springer_tdm` 渠道是很自然的扩展（见
  [OTHER_FIELDS_zh.md](OTHER_FIELDS_zh.md)）。
- **NCBI API 密钥**和 **GitHub 令牌。**不发送；工具的请求量在不带密钥的限额之内。

## 所有密钥都要遵守的条款

- TDM 密钥只能用于非商业研究，并且在你所在机构的许可范围内使用。
- 密钥属于个人。不要提交到仓库，不要贴进聊天或 issue，也不要写在命令行上。
- 许可副本（`LICENSED_TDM_ONLY`）只留在你的电脑上：不要上传到云端 AI 服务，不要分享或再分发；需要时分享 DOI 列表。
- 遵守限额。不要修改站点间隔或屏蔽站点列表来强行请求。

如果密钥泄露，先到服务商处吊销，再从仓库历史里清除（见 [SECURITY.md](../SECURITY.md)）。
