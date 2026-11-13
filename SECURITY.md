# Security / 安全

## Model / 安全模型

paper-pdf-harvest is a local command-line tool. It runs no server, and it sends requests only to the scholarly APIs
and hosts named in [docs/GUIDE.md](docs/GUIDE.md). Your keys stay in your environment or keys file. They are sent
only as request headers to the provider they belong to, are dropped when a redirect leaves that provider's domain,
and never appear in reports or manifests.

paper-pdf-harvest 是本地命令行工具，不运行任何服务，只访问 [docs/GUIDE.md](docs/GUIDE.md) 中列出的学术接口和站点。
密钥只保存在你的环境变量或密钥文件里，只以请求头的形式发给对应的服务商；重定向一旦离开该服务商的域名就会被丢弃，
也绝不会出现在报告或清单里。

## Reporting / 报告漏洞

Please do not open a public issue for a vulnerability. Use GitHub's private vulnerability reporting
(**Security → Report a vulnerability**) on this repository. Include steps to reproduce and the affected version.

请不要用公开 issue 报告漏洞。请使用本仓库的 GitHub 私密漏洞报告（**Security → Report a vulnerability**），
并附上复现步骤和受影响的版本。

## If you leaked a key / 如果泄露了密钥

Revoke it at the provider first (Elsevier, Wiley, OpenAlex), then remove it from the repository history. Deleting
the file in a new commit is not enough.

先到服务商处吊销密钥（Elsevier、Wiley、OpenAlex），再从仓库历史中清除。只在新提交里删除文件是不够的。

## Licensed content / 许可内容

Licensed (TDM) copies are not a security secret, but they are covered by your institution's licence. Never commit
them, share them or upload them to a hosted AI service. `tools/check_repo_hygiene.py` (run in CI) rejects PDFs,
bundles and reports in the tree.

TDM 许可副本虽不是密钥，但受机构许可约束：不要提交、分享或上传到云端 AI。CI 中运行的
`tools/check_repo_hygiene.py` 会拒绝仓库里出现 PDF、bundle 和报告。
