# ETF Strategy

基于 Yahoo Finance 数据的小型策略回测项目，当前默认用 `1810.HK` 作为开发验证样本，研究“样本起点建仓 + 固定股数网格交易”的回测流程。

这个仓库现在的定位不是“一次性脚本”，而是“可重复运行的策略研究工程”：

- 所有命令统一从根目录 `main.py` 进入
- 只保留 Yahoo 数据链路，降低维护面
- 同时输出中间结果、图表、交易记录和中文报告，方便复盘

## 你先从哪里开始

如果你第一次进入这个仓库，建议按下面顺序看：

1. 看这份 README，了解项目定位和最短上手路径
2. 看[项目导航与阅读顺序](doc/index.md)，建立整体结构感
3. 看[回测报告阅读指南](doc/report_reading_guide.md)，知道报告里的图和指标怎么读
4. 再按需要看专题文档和正式报告

## 仓库内置正式样本

为了让默认流程可复现，仓库直接跟踪两份正式样本：

- `data/processed/1810_hk_daily.csv`
- `data/processed/1810_hk_15m.csv`

它们分别对应：

- 日线主流程默认输入
- `15m` 分钟线研究默认输入

测试临时 CSV 和一次性研究样本不会一起纳入版本控制。

## 最短上手路径

### 1. 安装依赖

```powershell
py -3.13 -m pip install -r requirements.txt
```

### 2. 直接生成日线报告

```powershell
py -3.13 main.py report --data data/processed/1810_hk_daily.csv --symbol 1810.HK
```

输出：

- 中间结果：`outputs/`
- 正式报告：`reports/1810_hk_grid_report.md`

### 3. 直接生成 15 分钟线报告

```powershell
py -3.13 main.py report --data data/processed/1810_hk_15m.csv --symbol 1810.HK --interval 15m
```

输出：

- 中间结果：`outputs/minute/`
- 正式报告：`reports/minute/1810_hk_15m_grid_report.md`

## 文档导航

总导航：

- [项目导航与阅读顺序](doc/index.md)

结果阅读：

- [回测报告阅读指南](doc/report_reading_guide.md)
- [术语表与口径说明](doc/glossary.md)

专题说明：

- [日线网格参数测试方法](doc/grid_parameter_search.md)
- [Yahoo 分钟线支持与 15 分钟回测说明](doc/minute_grid_research.md)

维护者入口：

- [开发与维护说明](doc/development_guide.md)

## 常用命令速查

### 下载日线数据

```powershell
py -3.13 main.py download --start 2024-01-01 --end 2026-05-22 --proxy http://127.0.0.1:7897
```

### 下载默认分钟线数据

```powershell
py -3.13 main.py download --symbol 1810.HK --interval 15m --period 60d --proxy http://127.0.0.1:7897
```

### 样本内参数搜索

```powershell
py -3.13 main.py optimize --data data/processed/1810_hk_daily.csv --symbol 1810.HK
```

### 样本外验证

```powershell
py -3.13 main.py backtest --data data/processed/1810_hk_daily.csv --symbol 1810.HK --grid-spacing 0.07 --grid-count 5 --take-profit 0.03
```

### 一键执行完整流程

```powershell
py -3.13 main.py run --start 2024-01-01 --end 2026-05-22 --proxy http://127.0.0.1:7897
```

如果你在中国大陆直连 Yahoo，通常需要代理。可以设置：

```powershell
$env:ETF_STRATEGY_PROXY="http://127.0.0.1:7897"
```

## 项目结构速览

```text
etf_strategy/    源码
data/processed/  默认正式样本输入
outputs/         运行中间结果
reports/         正式图表与中文报告
doc/             长期维护文档
tests/           标准库 unittest 用例
task.md          AI 任务记录
```

## 输出与版本控制

- `data/processed/`：默认正式样本输入，当前只跟踪两份 `1810.HK` 示例样本
- `outputs/`：运行时中间文件，默认忽略版本控制
- `reports/`：正式中文报告、图表和交易记录展示
- `log/`：日志输出

## VS Code 调试

仓库已提供 `.vscode/launch.json`，覆盖当前主要入口：

- 下载日线数据
- 下载 15 分钟数据
- 日线样本内寻参
- 日线生成报告
- 15 分钟生成报告
- 日线完整流程
- 15 分钟完整流程

## 验证

```powershell
py -3.13 -m unittest tests.test_grid_strategy
```
