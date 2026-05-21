from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from etf_strategy.config import DEFAULT_MINUTE_REPORT_DIR, DEFAULT_REPORT_DIR


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

    axes[2].plot(
        equity_curve["Date"],
        equity_curve["ReturnPct"],
        color="#2ca02c",
        linewidth=1.5,
        label="组合收益率（建仓前固定为 0%）",
    )
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


def _describe_run_in_plain_words(run_result: dict[str, object], total_capital: float = 200000.0) -> dict[str, float | bool]:
    """把回测结果翻译成更接近投资者视角的金额口径。"""
    summary = run_result["summary"]
    history = run_result["history"]
    events = run_result["events"]

    final_equity = float(summary["FinalEquity"])
    total_pnl = final_equity - total_capital
    triggered_entry = bool(summary.get("TriggeredEntry", False))
    if triggered_entry:
        end_price = float(history.iloc[-1]["Close"])
        base_buy = events[events["EventType"] == "base_buy"].iloc[0]
        base_units = int(base_buy["Units"])
        base_cash_flow = float(base_buy["CashFlow"])
        base_cash_left = total_capital - base_cash_flow
        base_only_equity = base_cash_left + base_units * end_price
    else:
        base_only_equity = total_capital

    return {
        "final_equity": final_equity,
        "total_pnl": total_pnl,
        "base_only_equity": base_only_equity,
        "grid_vs_base_only": final_equity - base_only_equity,
        "triggered_entry": triggered_entry,
    }


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
    workflow_type = workflow_result.get("workflow_type", "daily")
    interval = workflow_result.get("interval", "1d")
    target_dir = Path(report_dir)
    figure_dir = target_dir / "figures"
    target_dir.mkdir(parents=True, exist_ok=True)

    optimization = workflow_result["optimization"]
    validation = workflow_result["validation"]
    decline_window = optimization["decline_window"]
    best_summary = optimization["best_run"]["summary"]
    validation_summary = validation["run"]["summary"]
    in_sample_words = _describe_run_in_plain_words(optimization["best_run"])
    validation_words = _describe_run_in_plain_words(validation["run"])

    if workflow_type == "minute":
        in_sample_chart = plot_run_result(
            optimization["best_run"],
            figure_dir / "xiaomi_15m_in_sample_grid.png",
            "小米港股 15 分钟样本内网格回测",
        )
        validation_chart = plot_run_result(
            validation["run"],
            figure_dir / "xiaomi_15m_validation_grid.png",
            "小米港股 15 分钟样本外网格回测",
        )
        search_chart = plot_grid_search(
            optimization["results"],
            figure_dir / "xiaomi_15m_grid_search_heatmap.png",
        )
        report_path = target_dir / "xiaomi_15m_grid_report.md"
        summary_lines = [
            f"- 标的：小米集团 `1810.HK`",
            f"- 数据周期：Yahoo Finance 最近 60 天 `{interval}`",
            f"- 样本内窗口：{decline_window.sample_start} 至 {decline_window.sample_end}",
            f"- 样本外窗口：{decline_window.validation_start} 至 {validation_summary['EndDate']}",
            f"- 切分方式：最近分钟线样本按 `75% / 25%` 拆分样本内与样本外",
            f"- 初始规则：从局部高点回撤 10% 后投入 50% 资金建底仓，剩余 50% 资金做网格买卖",
            f"- 最优参数：网格间距 {best_summary['GridSpacingPct']:.2f}% / 网格层数 {int(best_summary['GridCount'])} / 止盈比例 {best_summary['TakeProfitPct']:.2f}%",
        ]
        validation_title = "分钟线样本外验证"
        conclusion_tail = "这份报告只代表最近 60 天分钟级行情下的短周期表现，不等同于长期日线参数。"
    else:
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
        report_path = target_dir / "xiaomi_grid_report.md"
        summary_lines = [
            f"- 标的：小米集团 `1810.HK`",
            f"- 样本内窗口：{decline_window.sample_start} 至 {decline_window.sample_end}",
            f"- 样本外窗口：{decline_window.validation_start} 至 {validation_summary['EndDate']}",
            f"- 初始规则：从局部高点回撤 10% 后投入 50% 资金建底仓，剩余 50% 资金做网格买卖",
            f"- 最优参数：网格间距 {best_summary['GridSpacingPct']:.2f}% / 网格层数 {int(best_summary['GridCount'])} / 止盈比例 {best_summary['TakeProfitPct']:.2f}%",
        ]
        validation_title = "2026 样本外验证"
        conclusion_tail = "如果后续继续扩展策略，优先方向应该是加入趋势过滤或分阶段停手机制，而不是单纯增加网格层数。"

    if best_summary["ReturnPct"] <= 0 and validation_summary["ReturnPct"] <= 0:
        conclusion = "在这轮样本里，网格交易能摊薄持仓成本，但还没有把总账户稳定拉回正收益。"
    elif best_summary["ReturnPct"] > 0 and validation_summary["ReturnPct"] > 0:
        conclusion = "网格交易在本轮样本里同时改善了成本和总收益，参数延续性相对更强。"
    else:
        conclusion = "这轮样本里，网格交易的效果呈现阶段性差异，需要结合是否真正触发建仓一起理解。"
    validation_scope = "分钟线样本外区间" if workflow_type == "minute" else "2026 样本外区间"
    if not validation_words["triggered_entry"]:
        validation_comment = f"{validation_scope}没有触发 10% 回撤建仓，因此这段结果更像“策略没有出手”，不能直接用来证明参数有效或失效。"
    elif validation_summary["ReturnPct"] < 0:
        validation_comment = f"{validation_scope}延续了成本摊薄，但收益仍为负，说明策略更像风险缓冲而不是单独的反转信号。"
    elif validation_summary["ReturnPct"] > 0:
        validation_comment = f"{validation_scope}收益转正，说明最优参数在新阶段仍具一定延续性。"
    else:
        validation_comment = f"{validation_scope}最终回到盈亏平衡附近，说明这套参数至少没有在这段样本里造成新的损失。"

    total_pnl_text = "盈利" if in_sample_words["total_pnl"] >= 0 else "亏损"
    validation_total_pnl_text = "盈利" if validation_words["total_pnl"] >= 0 else "亏损"
    grid_vs_base_text = "多赚了" if in_sample_words["grid_vs_base_only"] >= 0 else "多亏了"
    if validation_words["triggered_entry"]:
        validation_extra_lines = f"""- 期末有效持仓成本：{validation_summary["EffectiveCost"]:.2f}
- 相对样本外首笔建仓成本下降：{validation_summary["CostReductionPct"]:.2f}%
- 网格已实现收益：{validation_summary["RealizedGridProfit"]:.2f}
  - 人话：单看已经完成并兑现的网格交易，样本外一共落袋赚了 `{validation_summary["RealizedGridProfit"]:.2f}`。
- 完成网格循环次数：{int(validation_summary["GridCyclesCompleted"])}"""
    else:
        validation_extra_lines = """- 本段样本外没有触发 10% 回撤建仓，所以没有发生底仓买入，也没有任何网格成交。
- 人话：收益率保持 `0%` 不是图画错了，而是这段分钟线数据里策略根本没有进场。"""
    report_content = f"""# 小米港股网格回测报告

## 摘要

{chr(10).join(summary_lines)}

{conclusion}

## 样本内寻参结果

- 参考高点：{decline_window.peak_date}，收盘价 {decline_window.peak_price:.2f}
- 初始建仓触发日：{decline_window.entry_date}，收盘价 {decline_window.entry_price:.2f}
- 样本内收益率：{best_summary["ReturnPct"]:.2f}%
  - 人话：整个账户从 `200000` 变成了 `{in_sample_words["final_equity"]:.2f}`，合计{total_pnl_text} `{abs(in_sample_words["total_pnl"]):.2f}`。
- 样本内年化收益率：{best_summary["AnnualReturnPct"]:.2f}%
  - 人话：这是把这段样本期的结果折算成年化后的速度，用来和别的策略比较，不是说你真的持有满一年亏这么多。
- 样本内最大回撤：{best_summary["MaxDrawdownPct"]:.2f}%
  - 人话：样本里最差的时候，账户相对阶段最高点最多回撤了约 `{best_summary["MaxDrawdownPct"]:.2f}%`。
- 期末有效持仓成本：{best_summary["EffectiveCost"]:.2f}
  - 人话：把已经通过网格落袋的利润扣掉后，你手里剩余持仓等效成本大约是 `{best_summary["EffectiveCost"]:.2f}`。
- 相对初始建仓成本下降：{best_summary["CostReductionPct"]:.2f}%
  - 人话：最开始底仓买在 `{decline_window.entry_price:.2f}`，现在等效成本被网格摊低了约 `{best_summary["CostReductionPct"]:.2f}%`。
- 网格已实现收益：{best_summary["RealizedGridProfit"]:.2f}
  - 人话：单看“低买高卖已经完成并落袋”的网格交易，本轮一共赚了 `{best_summary["RealizedGridProfit"]:.2f}`。
- 完成网格循环次数：{int(best_summary["GridCyclesCompleted"])}
  - 人话：有 `{int(best_summary["GridCyclesCompleted"])}` 次网格仓位完成了“买入 -> 反弹 -> 卖出”的完整闭环。

### 样本内怎么看懂

- 如果你只按规则先买 `50%` 底仓，后面完全不做网格，到样本结束时账户大约是 `{in_sample_words["base_only_equity"]:.2f}`。
- 当前这版网格策略的最终账户是 `{in_sample_words["final_equity"]:.2f}`，收益率 `{best_summary["ReturnPct"]:.2f}%`。
- 也就是说：网格本身虽然已经落袋赚了 `{best_summary["RealizedGridProfit"]:.2f}`，但额外接进来的下跌仓位浮盈浮亏也会影响总账户，所以整套策略相对“只拿底仓不做网格”{grid_vs_base_text} `{abs(in_sample_words["grid_vs_base_only"]):.2f}`。
- 所以这里不能把“网格已实现收益”直接理解成“整个策略赚了这么多钱”；它只代表网格来回滚动已经兑现的那部分利润。

### 关于收益曲线为什么看起来像 0

- 图里的收益曲线不是全程为 0。
- 建仓前没有持仓，所以那一段收益率固定是 `0%`，这是正常的。
- 建仓后如果总账户没有回正，收益曲线就会从 `0%` 往下走；如果后来翻红，也会重新回到 `0%` 上方。
- 如果你肉眼看图时觉得它“都贴着 0”，主要是因为前半段建仓前确实是一条 0 线，而后半段始终在负区间，没有出现重新翻红。

![样本内回测图](figures/{in_sample_chart.name})

![样本内参数热力图](figures/{search_chart.name})

## {validation_title}

- 样本外收益率：{validation_summary["ReturnPct"]:.2f}%
  - 人话：整个账户从 `200000` 变成了 `{validation_words["final_equity"]:.2f}`，合计{validation_total_pnl_text} `{abs(validation_words["total_pnl"]):.2f}`。
- 样本外年化收益率：{validation_summary["AnnualReturnPct"]:.2f}%
- 样本外最大回撤：{validation_summary["MaxDrawdownPct"]:.2f}%
{validation_extra_lines}

{validation_comment}

![样本外回测图](figures/{validation_chart.name})

## 结论

- 这套参数更适合“先急跌、后震荡修复”的行情，能够通过来回做网格降低持仓成本。
- 如果行情持续单边下跌，网格收益只能部分对冲亏损，不能替代趋势止损或更强的择时规则。
- 当前样本下，成本摊薄效果稳定存在：样本内下降 {best_summary["CostReductionPct"]:.2f}%，样本外下降 {validation_summary["CostReductionPct"]:.2f}%。
- {conclusion_tail}
"""
    report_path.write_text(report_content, encoding="utf-8")
    return report_path


def build_minute_report_markdown(
    workflow_result: dict[str, object],
    report_dir: str | Path = DEFAULT_MINUTE_REPORT_DIR,
) -> Path:
    """生成分钟线专用报告。"""
    return build_report_markdown(workflow_result, report_dir=report_dir)
