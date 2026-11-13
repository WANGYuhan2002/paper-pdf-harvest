# paper-pdf-harvest

[English](README.md) · **中文**

[![ci](https://github.com/WANGYuhan2002/paper-pdf-harvest/actions/workflows/ci.yml/badge.svg)](https://github.com/WANGYuhan2002/paper-pdf-harvest/actions/workflows/ci.yml)

为一份阅读清单抓取经过校验的全文 PDF，并且不违反许可。

输入可以是 DOI、arXiv ID、URL、自由格式的引文，或 Zotero/BibTeX 导出文件。工具会在二十来个开放渠道里找全文：
OpenAlex 收录的副本位置、出版商开放获取、arXiv、EarthArXiv、PMC、Zenodo、HAL、机构与国家知识库等。如果你有密钥，
还会走 Wiley 和 Elsevier 的文本与数据挖掘（TDM）接口。

- 每个 PDF 先要通过四道校验才会保留：确实是 PDF、大小不超过上限、至少 3 页且有 5000 字符以上的文字层、确实是要找的
  那篇论文。
- 许可层级按**实际下载到的副本**判定。开放副本放进 `open_pdfs/`；许可副本只留在本机的 `tdm_bundles/`，绝不交给
  云端 AI。
- 屏蔽脚本的网站一律跳过，绝不绕过。这些论文会列进清单，由你在浏览器或 Zotero 里下载，再用 `triage` 按许可分流导回。

它是 [SeismoHub](https://github.com/WANGYuhan2002/seismohub)（一款地震学文献应用）的 PDF 引擎，单独打包后可以
独立运行。参数是按地震学调的，但渠道是按出版商和开放基础设施组织的，而不是按期刊，所以可以平移到地学乃至其他学科
（见 [docs/OTHER_FIELDS_zh.md](docs/OTHER_FIELDS_zh.md)）。

## 快速上手

```bash
git clone https://github.com/WANGYuhan2002/paper-pdf-harvest
cd paper-pdf-harvest
python3 -m venv .venv && source .venv/bin/activate      # 需要 Python 3.10 或更新版本
pip install -e .

paper-pdf-harvest keys                                   # 看看配置了哪些密钥（一个都没有也能用）
paper-pdf-harvest harvest --input-file examples/reading_list.txt --out-dir ~/pack --dry-run
paper-pdf-harvest harvest --input-file examples/reading_list.txt --out-dir ~/pack
paper-pdf-harvest status ~/pack --pending                # 还缺哪些，附链接
```

没抓到的论文列在 `~/pack/pending_zotero.csv`。在浏览器里下载它们（推荐 Zotero Connector），再导入：

```bash
paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack            # 试运行：显示 OPEN->PACK / TDM->BUNDLE
paper-pdf-harvest triage ~/Zotero/storage --pack ~/pack --commit
```

同一个 `--out-dir` 可以随时再跑 `harvest`：已完成的论文会跳过，失败的到期后自动重试；加 `--retry-failed` 则立即重试。

## 输出目录（pack）

| 路径 | 内容 |
|---|---|
| `open_pdfs/` | 只放开放副本（`OPEN_CC_BY_OR_PREPRINT`）：CC 许可的正式版、预印本、知识库副本。可以分享 |
| `tdm_bundles/PaperBundle_<DOI>/` | 许可副本（`LICENSED_TDM_ONLY`）：经 TDM 接口或订阅下载的出版商 PDF、带图的 Elsevier 全文 XML。**仅限本地使用** |
| `open_bundles/PaperBundle_<DOI>/` | 开放论文的附加材料：全文 XML、补充材料、公开评审意见、代码和数据链接 |
| `harvest_report.jsonl` | 每篇论文每次运行一行：状态、原因、找到的副本、每一次尝试 |
| `harvest_summary.tsv` | 当前状态，每篇论文一行 |
| `pending_zotero.csv` | 仍然没有全文的论文：链接、状态和下一步怎么做 |

每个 bundle 都有一个 `bundle_manifest.json`，记录许可层级、`hosted_ai_upload_allowed`、SHA-256、页数和每一次尝试。

## 两种模式

- **阅读清单模式**就是本仓库：任意清单、任意文件夹，不需要数据库。
- **文献库模式**在 SeismoHub 里运行。`python scripts/harvest_pdfs.py` 用同一个引擎为 SeismoHub 文献库里的论文补齐
  PDF，先备份数据库，再把开放副本挂到论文上。见 [docs/GUIDE_zh.md 第 12 节](docs/GUIDE_zh.md#12-接入-seismohub)。

## 密钥

一个都不是必需的。有了密钥能拿到更多：

| 变量 | 解锁什么 | 费用 |
|---|---|---|
| `SEISMO_HARVEST_UA` | 在 User-Agent 里写上你的联系邮箱：进入 Crossref 礼貌池，提高 DataCite 限额 | 免费 |
| `WILEY_TDM_TOKEN` | 通过 Wiley TDM 接口获取 Wiley / AGU 的正式版（订阅内容需在机构网络内） | 订阅机构的非商业研究不另收费 |
| `ELSEVIER_API_KEY`（及 `ELSEVIER_INSTTOKEN`） | Elsevier 开放获取 PDF；订阅文章的全文 XML（需在有权限的网络内） | 非商业学术用途免费 |
| `OPENALEX_API_KEY` | `content.openalex.org` 的缓存 PDF | 密钥免费，每天 1 美元额度（约 100 个 PDF） |

请把密钥放在 `~/.config/seismo_harvester/keys.env`，放在任何仓库之外。注册页面、条款和限额见
[docs/KEYS_zh.md](docs/KEYS_zh.md)。变量名沿用 SeismoHub 的前缀，所以一个密钥文件两边通用。

## 实际效果

在一个 SeismoHub 文献库上的 18 次运行（2026 年 11 月 8 日至 10 日；2,445 篇地震学和地球物理论文；配置了 Wiley、
Elsevier 和 OpenAlex 密钥；部分时间在机构网络内）中：

- 1,562 篇（64%）找到了开放副本；
- 205 篇（8%）找到了许可副本，留在本地；
- 41 篇（2%）与另一篇论文的 PDF 相同；
- 637 篇（26%）什么都没找到。

缺口主要有三类：

- 没有 TDM 接口、开放副本又少的订阅期刊：GeoScienceWorld 上的美国地震学会（SSA）期刊、SEG，以及转为开放获取之前
  的 OUP 期刊 GJI；
- ESSOAr 预印本，它的服务器屏蔽脚本；
- 其实是数据集而不是论文的 Zenodo DOI。

按出版商、按渠道的覆盖率，以及工具的不足，见 [docs/RESULTS_zh.md](docs/RESULTS_zh.md)。

## 许可规则

- TDM 许可副本只留在你的电脑上：从不写进 `open_pdfs/`，也从不发送给云端 AI。`--attach-tdm` 已封住，以退出码 3
  退出，什么也不做。
- 出版商 PDF 的前两页写着 "All rights reserved"、又没有开放许可声明时，一律按许可内容处理，不管元数据怎么说。
- 反爬保护、验证码和登录墙绝不绕过。没有浏览器自动化，不伪装 User-Agent，每个站点都有最小请求间隔。
- TDM 密钥只能在你所在机构的许可范围内使用，详见 [docs/KEYS_zh.md](docs/KEYS_zh.md)。

## Agent 技能（Claude Code）

[`.claude/skills/paper-pdf-harvest/SKILL.md`](.claude/skills/paper-pdf-harvest/SKILL.md) 教 Agent 这套流程和规则，
比如"绝不读取许可副本""先试运行"。在 Claude Code 里打开本仓库就会自动加载；想在任何地方都能用，就把这个文件夹复制
或软链接到 `~/.claude/skills/`。

## 文档

| 文档 | 内容 |
|---|---|
| [docs/GUIDE_zh.md](docs/GUIDE_zh.md) | 完整指南：渠道及顺序、四道校验、许可层级、输出、状态、补缺口、命令、Python 接口、SeismoHub |
| [docs/KEYS_zh.md](docs/KEYS_zh.md) | 要注册哪些账号和密钥、费用、能解锁什么、需要遵守的条款 |
| [docs/RESULTS_zh.md](docs/RESULTS_zh.md) | 按出版商、渠道、状态统计的实测覆盖率；优点与不足 |
| [docs/OTHER_FIELDS_zh.md](docs/OTHER_FIELDS_zh.md) | 用到地震学以外：哪些直接可用，哪些需要调整 |
| [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [CHANGELOG.md](CHANGELOG.md) | 开发、报告漏洞、版本记录 |

每份文档都有英文版（去掉 `_zh`）。

## 与 SeismoHub 的关系

引擎（`fullbundle_harvest.py`、`upgrades.py` 和各个 resolver 模块）由 SeismoHub 的开源代码生成，这些文件开头都有
"Synced from SeismoHub" 标记。命令行、测试和文档属于本仓库。引擎的修复先进 SeismoHub，再同步过来，所以两个工具的
行为一致。

## 许可证

MIT，见 [LICENSE](LICENSE)。许可证只覆盖代码，不覆盖你下载的论文：每篇论文保留它自己的许可。
