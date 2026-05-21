from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from etf_strategy.config import DEFAULT_REPORT_DIR


def configure_matplotlib() -> None:
    """配置中文绘图环境。"""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def plot_run_result(run_result: dict[str, object], output_path: str | Path, title: str) -> Path:
    """绘制单次回测的价格、成本和收益曲线。"""
    configure_matplotlib()

    history = run_result["history"].copy()
    events = run_result["events"].copy()
    equity_curve = run_result["equity_curve"].copy().reset_index()

    history["Date"] = pd.to_datetime(history["Date"])
    if not events.empty:
        events["Date"] = pd.to_datetime(events["Date"])

    date_column = equity_curve.columns[0]
    equity_curve.rename(columns={date_column: "Date"}, inplace=True)
    equity_curve["Date"] = pd.to_datetime(equity_curve["Date"])
    equity_curve["ReturnPct"] = (equity_curve["Equity"] / 200000.0 - 1) * 100
    equity_curve["DrawdownPct"] = equity_curve["DrawdownPct"] * 100

    figure, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    figure.suptitle(title, fontsize=16, fontweight="bold")

    axes[0].plot(history["Date"], history["Close"], color="#1f77b4", linewidth=1.6, label="收盘价")
    axes[0].plot(history["Date"], history["EffectiveCost"], color="#d62728", linewidth=1.4, label="持仓有效成本")
    axes[0].plot(history["Date"], history["EntryTriggerPrice"], color="#7f7f7f", linestyle="--", linewidth=1.0, label="10% 触发线")
    if not events.empty:
        marker_map = {
            "base_buy": ("^", "#e6550d", "初始建仓"),
            "grid_buy": ("v", "#31a354", "网格买入"),
            "grid_sell": ("o", "#756bb1", "网格卖出"),
        }
        for event_type, (marker, color, label) in marker_map.items():
            subset = events[events["EventType"] == event_type]
            if subset.empty:
                continue
            axes[0].scatter(subset["Date"], subset["Price"], marker=marker, s=70, color=color, label=label, zorder=5)
    axes[0].set_ylabel("价格")
    axes[0].legend(loc="upper right", ncol=4)

    axes[1].plot(history["Date"], history["GrossCost"], color="#3182bd", linewidth=1.5, label="当前投入资金")
    axes[1].plot(history["Date"], history["RealizedGridProfit"], color="#ff7f0e", linewidth=1.5, label="累计网格已实现收益")
    axes[1].set_ylabel("金额")
    axes[1].legend(loc="upper right")

    axes[2].plot(equity_curve["Date"], equity_curve["ReturnPct"], color="#2ca02c", linewidth=1.5, label="组合收益率")
    axes[2].plot(equity_curve["Date"], equity_curve["DrawdownPct"], color="#d62728", linewidth=1.2, label="回撤比例")
    axes[2].axhline(0, color="#7f7f7f", linewidth=0.8)
    axes[2].set_ylabel("百分比")
    axes[2].set_xlabel("日期")
    axes[2].legend(loc="upper right")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return target


def plot_grid_search(results: pd.DataFrame, output_path: str | Path) -> Path:
    """绘制参数搜索热力图。"""
    configure_matplotlib()

    grid = (
        results.pivot_table(index="GridCount", columns="GridSpacingPct", values="Score", aggfunc="max")
        .sort_index()
        .sort_index(axis=1)
    )

    figure, axis = plt.subplots(figsize=(10, 6))
    image = axis.imshow(grid.values, cmap="RdYlGn", aspect="auto")
    axis.set_xticks(range(len(grid.columns)))
    axis.set_xticklabels([f"{value:.1f}%" for value in grid.columns])
    axis.set_yticks(range(len(grid.index)))
    axis.set_yticklabels([str(value) for value in grid.index])
    axis.set_xlabel("网格间距")
    axis.set_ylabel("网格层数")
    axis.set_title("样本内参数综合评分热力图")

    for row_index in range(len(grid.index)):
        for column_index in range(len(grid.columns)):
            value = grid.iloc[row_index, column_index]
            axis.text(column_index, row_index, f"{value:.1f}", ha="center", va="center", fontsize=9)

    figure.colorbar(image, ax=axis, shrink=0.9, label="综合评分")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return target


def build_report_markdown(
    workflow_result: dict[str, object],
    report_dir: str | Path = DEFAULT_REPORT_DIR,
) -> Path:
    """根据完整工作流结果生成中文报告。"""
    target_dir = Path(report_dir)
    figure_dir = target_dir / "figures"
    target_dir.mkdir(parents=True, exist_ok=True)

    optimization = workflow_result["optimization"]
    validation = workflow_result["validation"]
    decline_window = optimization["decline_window"]
    best_summary = optimization["best_run"]["summary"]
    validation_summary = validation["run"]["summary"]

    in_sample_chart = plot_run_result(
        optimization["best_run"],
        figure_dir / "xiaomi_in_sample_grid.png",
        "小米港股样本内网格回测",
    )
    validation_chart = plot_run_result(
        validation["run"],
        figure_dir / "xiaomi_validation_2026_grid.png",
        "小米港股 2026 样本外网格回测",
    )
    search_chart = plot_grid_search(
        optimization["results"],
        figure_dir / "xiaomi_grid_search_heatmap.png",
    )

    conclusion = (
        "在这轮下跌样本里，网格交易能明显摊薄持仓成本，但不足以把组合收益拉回正值。"
        if best_summary["ReturnPct"] < 0 and validation_summary["ReturnPct"] < 0
        else "网格交易在本轮样本里既带来了成本摊薄，也对收益有正向帮助。"
    )
    validation_comment = (
        "2026 样本外区间延续了成本摊薄，但收益仍为负，说明策略更像风险缓冲而不是单独的反转信号。"
        if validation_summary["ReturnPct"] < 0
        else "2026 样本外区间收益转正，说明最优参数在新阶段仍具一定延续性。"
    )

    report_path = target_dir / "xiaomi_grid_report.md"
    report_content = f"""# 小米港股网格回测报告

## 摘要

- 标的：小米集团 `1810.HK`
- 样本内窗口：{decline_window.sample_start} 至 {decline_window.sample_end}
- 样本外窗口：{decline_window.validation_start} 至 {validation_summary["EndDate"]}
- 初始规则：从局部高点回撤 10% 后投入 50% 资金建底仓，剩余 50% 资金做网格买卖
- 最优参数：网格间距 {best_summary["GridSpacingPct"]:.2f}% / 网格层数 {int(best_summary["GridCount"])} / 止盈比例 {best_summary["TakeProfitPct"]:.2f}%

{conclusion}

## 样本内寻参结果

- 参考高点：{decline_window.peak_date}，收盘价 {decline_window.peak_price:.2f}
- 初始建仓触发日：{decline_window.entry_date}，收盘价 {decline_window.entry_price:.2f}
- 样本内收益率：{best_summary["ReturnPct"]:.2f}%
- 样本内年化收益率：{best_summary["AnnualReturnPct"]:.2f}%
- 样本内最大回撤：{best_summary["MaxDrawdownPct"]:.2f}%
- 期末有效持仓成本：{best_summary["EffectiveCost"]:.2f}
- 相对初始建仓成本下降：{best_summary["CostReductionPct"]:.2f}%
- 网格已实现收益：{best_summary["RealizedGridProfit"]:.2f}
- 完成网格循环次数：{int(best_summary["GridCyclesCompleted"])}

![样本内回测图](figures/{in_sample_chart.name})

![样本内参数热力图](figures/{search_chart.name})

## 2026 样本外验证

- 样本外收益率：{validation_summary["ReturnPct"]:.2f}%
- 样本外年化收益率：{validation_summary["AnnualReturnPct"]:.2f}%
- 样本外最大回撤：{validation_summary["MaxDrawdownPct"]:.2f}%
- 期末有效持仓成本：{validation_summary["EffectiveCost"]:.2f}
- 相对样本外首笔建仓成本下降：{validation_summary["CostReductionPct"]:.2f}%
- 网格已实现收益：{validation_summary["RealizedGridProfit"]:.2f}
- 完成网格循环次数：{int(validation_summary["GridCyclesCompleted"])}

{validation_comment}

![样本外回测图](figures/{validation_chart.name})

## 结论

- 这套参数更适合“先急跌、后震荡修复”的行情，能够通过来回做网格降低持仓成本。
- 如果行情持续单边下跌，网格收益只能部分对冲亏损，不能替代趋势止损或更强的择时规则。
- 当前样本下，成本摊薄效果稳定存在：样本内下降 {best_summary["CostReductionPct"]:.2f}%，样本外下降 {validation_summary["CostReductionPct"]:.2f}%。
- 如果后续继续扩展策略，优先方向应该是加入趋势过滤或分阶段停手机制，而不是单纯增加网格层数。
"""
    report_path.write_text(report_content, encoding="utf-8")
    return report_path
