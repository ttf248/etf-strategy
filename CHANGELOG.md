# Changelog

本文件记录面向用户和维护者的重要变化。

## Unreleased

- 重建开源项目文档体系。
- 将文档主线调整为研究平台：架构、数据流、部署、运维、开发、API 和策略引擎。
- 新增 MIT License、贡献指南、安全策略和支持说明。
- 新增 GitHub CI、Issue 模板、PR 模板、`.editorconfig`、`.gitattributes` 和 `pyproject.toml`。
- 收敛仓库体积，移除仓库内历史样例数据与 Markdown 报告，只保留 `data/README.md`、`reports/README.md` 作为目录边界说明。
- CLI 默认链路切换为数据库优先，正式行情与回测结果不再落地到本地 CSV 或仓库内报告目录。
- 新增开源准备度审计文档，明确评分基线、改造项和后续缺口。
