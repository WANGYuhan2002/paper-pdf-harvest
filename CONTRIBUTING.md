# Contributing / 贡献指南

Issues and pull requests are welcome in English or Chinese. 欢迎提交 issue 和 pull request，中英文均可。

## Set up / 环境

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
python -m pytest -q                    # offline: HTTP is faked, PDFs are generated in the tests
python tools/check_repo_hygiene.py     # no PDFs, reports, keys or personal data in the tree
```

The tests never touch the network or your keys: `tests/conftest.py` hides the keys file and settings, and restores
the engine after every test.
测试完全离线：`tests/conftest.py` 会屏蔽你的密钥文件和设置，并在每个测试后把引擎恢复原状。

## Where code lives / 代码归属

- **Synced engine files** start with a `# Synced from SeismoHub ...` banner. They are generated from SeismoHub's
  open-source tree, so a direct edit would be overwritten by the next sync:
  `paper_pdf_harvest/fullbundle_harvest.py`, `upgrades.py`, `deep_oa_and_vor_resolvers.py`,
  `pmc_oa_and_whitelist_channel.py`, `xml_render.py`, `seal.py`, `licence_triage.py`, `matching.py`,
  `citations.py`, `report_summary.py`, `tests/test_engine_core.py`, `tests/test_upgrades.py`,
  `tests/test_seal.py`. Open your pull request here anyway: the maintainer ports engine changes to SeismoHub and
  syncs them back, so both tools stay identical.
- **This repository's own files:** `paper_pdf_harvest/cli.py`, the other tests, `docs/`, `README*`, the skill and
  CI. Edit them directly.

- **同步的引擎文件**开头有 `# Synced from SeismoHub ...` 标记，由 SeismoHub 的开源代码生成，直接修改会在下次同步时被
  覆盖。请照常在这里提 PR，维护者会把改动移植到 SeismoHub 再同步回来，保证两边一致。
- **本仓库自己的文件**（`cli.py`、其余测试、`docs/`、`README*`、技能、CI）可以直接修改。

## Rules that are part of the product / 属于产品本身的规则

- Licensed (TDM) copies stay local: nothing may write a non-OPEN copy to `open_pdfs/` or send it to a hosted AI
  service. Keep the tiers, the seal (`seal.keep_non_open_in_bundle`) and `hosted_ai_upload_allowed` intact.
- No CAPTCHA solving, no bot-protection workarounds, no browser automation against publisher sites, no User-Agent
  spoofing. Do not remove entries from `BOT_WALLED_HOSTS` or shorten the per-host intervals to force access.
- Keys are reported as present or absent only. Never log, print or store a key value.
- Never commit PDFs, packs, bundles, reports or `.env` files. CI fails if you do.
- Few dependencies: explain any new runtime dependency in the pull request.

- TDM 许可副本只留在本地：任何代码都不得把非 OPEN 副本写进 `open_pdfs/` 或发送给云端 AI；保留分层、封印与
  `hosted_ai_upload_allowed`。
- 不破解验证码、不绕过反爬、不对出版商网站做浏览器自动化、不伪装 User-Agent；不要删减 `BOT_WALLED_HOSTS` 或缩短限速。
- 密钥只报告"有/无"，绝不记录、打印或保存其值。
- 不要提交 PDF、包目录、bundle、报告或 `.env`，CI 会拦下。

## Pull requests / 提交 PR

- One topic per pull request, with tests for new behaviour. Tests must stay offline.
- Docs are bilingual: when you change `X.md`, change `X_zh.md` too (or say in the PR that it needs translating).
- 文档是双语的：改了 `X.md` 请同时改 `X_zh.md`，或在 PR 里注明需要翻译。
