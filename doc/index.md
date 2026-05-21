# 项目导航与阅读顺序

这份文档的目标不是解释所有细节，而是帮助你快速判断：

- 这个仓库的各个目录分别负责什么
- 先看哪些文档最省时间
- 想看结果、想看方法、想改代码时，各自应该去哪里

## 如果你是第一次来

建议按这个顺序看：

1. [README](../README.md)
2. [回测报告阅读指南](report_reading_guide.md)
3. 正式报告：
   - [日线报告](../reports/xiaomi_grid_report.md)
   - [15 分钟线报告](../reports/minute/xiaomi_15m_grid_report.md)
4. 再按需要看专题文档：
   - [日线网格参数测试方法](grid_parameter_search.md)
   - [Yahoo 分钟线支持与 15 分钟回测说明](minute_grid_research.md)

## 如果你只关心结果

直接看：

- [日线报告](../reports/xiaomi_grid_report.md)
- [15 分钟线报告](../reports/minute/xiaomi_15m_grid_report.md)
- [回测报告阅读指南](report_reading_guide.md)

这样做的原因是：报告现在已经按“先看结论、再看细节”的双层结构组织，阅读门槛比直接翻源码低很多。

## 如果你想知道方法怎么来的

建议看：

1. [术语表与口径说明](glossary.md)
2. [日线网格参数测试方法](grid_parameter_search.md)
3. [Yahoo 分钟线支持与 15 分钟回测说明](minute_grid_research.md)

这三份文档分别解决：

- 名词是什么意思
- 日线参数是怎么测试出来的
- 分钟线为什么要单独研究，以及当前怎么切样本

## 如果你要改代码

建议看：

1. [开发与维护说明](development_guide.md)
2. `main.py`
3. `etf_strategy/workflow.py`
4. 你要改动对应的模块

## 仓库结构怎么理解

```text
etf_strategy/    源码
data/processed/  默认正式样本输入
outputs/         工作流中间结果
reports/         图表与正式报告
doc/             长期维护文档
tests/           单元测试
task.md          AI 任务记录
```

可以把它理解成 5 层：

1. 输入层：`data/processed/`
2. 逻辑层：`etf_strategy/`
3. 中间产物层：`outputs/`
4. 结果展示层：`reports/`
5. 文档与协作层：`doc/`、`README.md`、`AGENTS.md`、`task.md`

## 各类文档分别负责什么

- `README.md`
  - 项目首页和最短上手路径
- `doc/index.md`
  - 文档总导航和阅读顺序
- `doc/report_reading_guide.md`
  - 报告怎么读、图怎么读、哪些数字容易看错
- `doc/glossary.md`
  - 统一术语和口径
- `doc/grid_parameter_search.md`
  - 日线专题方法说明
- `doc/minute_grid_research.md`
  - 分钟线专题方法说明
- `doc/development_guide.md`
  - 面向维护者的改动入口和更新约定

## 当前默认工作流

日线主流程：

- 输入：`data/processed/xiaomi_1810_hk_daily.csv`
- 样本外起点：`2026-01-01`
- 样本内窗口：向前回看 `120` 天

分钟线研究流程：

- 输入：`data/processed/xiaomi_1810_hk_15m.csv`
- 数据范围：Yahoo 最近 `60d`
- 切分方式：`75% / 25%`

## 关于 `task.md`

`task.md` 继续保留，但它的职责是：

- 记录 AI 编码任务
- 回填每轮修改方案和设计取舍

它不是用户阅读入口，也不替代正式文档。
