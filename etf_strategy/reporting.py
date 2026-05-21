from __future__ import annotations
"""报告与图表输出层。

这里不重新实现回测逻辑，只负责把工作流产出的结构化结果翻译成：
- 图表
- Markdown 表格
- 更接近投资者视角的中文说明
"""

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
    # 权益曲线沿用回测账户总资金口径，不能硬编码，否则未来改资金规模会画错。
    total_capital = float(run_result["summary"].get("TotalCapital", 200000.0))
    equity_curve["ReturnPct"] = (equity_curve["Equity"] / total_capital - 1) * 100
    equity_curve["DrawdownPct"] = equity_curve["DrawdownPct"] * 100

    figure, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    figure.suptitle(title, fontsize=16, fontweight="bold")

    axes[0].plot(history["Date"], history["Close"], color="#1f77b4", linewidth=1.6, label="收盘价")
    axes[0].plot(history["Date"], history["EffectiveCost"], color="#d62728", linewidth=1.4, label="持仓有效成本")
    if not events.empty:
        # 价格图上的散点只负责帮助人眼定位关键交易，不承载收益计算逻辑。
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
    total_capital = float(summary.get("TotalCapital", total_capital))

    final_equity = float(summary["FinalEquity"])
    total_pnl = final_equity - total_capital
    triggered_entry = bool(summary.get("TriggeredEntry", False))
    if triggered_entry:
        end_price = float(history.iloc[-1]["Close"])
        base_buy = events[events["EventType"] == "base_buy"].iloc[0]
        base_units = int(base_buy["Units"])
        base_cash_flow = float(base_buy["CashFlow"])
        base_cash_left = total_capital - base_cash_flow
        # 这里构造“只拿底仓不做网格”的对照组，方便解释网格究竟贡献了多少。
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


def _format_markdown_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _build_markdown_table(frame: pd.DataFrame, columns: list[str], rename_map: dict[str, str]) -> str:
    """把 DataFrame 安全地转成 Markdown 表格。

    这里只输出调用方显式允许的列，避免把 backtesting.py 的内部字段原样泄露到报告里。
    """
    if frame.empty:
        return "暂无记录。"

    available_columns = [column for column in columns if column in frame.columns]
    display = frame.loc[:, available_columns].copy()
    display.rename(columns=rename_map, inplace=True)
    headers = list(display.columns)
    rows = [[_format_markdown_value(value) for value in row] for row in display.itertuples(index=False, name=None)]
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, separator_line, *row_lines])


def _build_event_table(run_result: dict[str, object]) -> str:
    return _build_markdown_table(
        run_result["events"],
        columns=["Date", "EventType", "Level", "Price", "Units", "CashFlow", "Note"],
        rename_map={
            "Date": "时间",
            "EventType": "事件类型",
            "Level": "层级",
            "Price": "价格",
            "Units": "数量",
            "CashFlow": "金额",
            "Note": "说明",
        },
    )


def _build_trade_table(run_result: dict[str, object]) -> str:
    """生成成交结果表。

    交易表和事件表并存，是因为两者回答的问题不同：
    - 事件表看执行过程
    - 交易表看单笔盈亏归因
    """
    trades = run_result["trades"].copy()
    if trades.empty:
        return "暂无记录。"

    trades["PnL"] = trades["PnL"].astype("float64")
    trades["ReturnPctDisplay"] = trades["ReturnPct"].astype("float64") * 100
    trades["Level"] = trades["Tag"].fillna("").astype(str).str.replace("grid_", "网格 ", regex=False)
    trades.loc[trades["Tag"] == "base", "Level"] = "底仓"
    return _build_markdown_table(
        trades,
        columns=[
            "EntryTime",
            "ExitTime",
            "Duration",
            "EntryPrice",
            "ExitPrice",
            "Size",
            "PnL",
            "ReturnPctDisplay",
            "Level",
        ],
        rename_map={
            "EntryTime": "开仓时间",
            "ExitTime": "平仓时间",
            "Duration": "持有时长",
            "EntryPrice": "开仓价",
            "ExitPrice": "平仓价",
            "Size": "数量",
            "PnL": "盈亏",
            "ReturnPctDisplay": "收益率(%)",
            "Level": "仓位类型",
        },
    )


def plot_grid_search(results: pd.DataFrame, output_path: str | Path) -> Path:
    """绘制参数搜索热力图。"""
    configure_matplotlib()

    # 热力图只按“层数 x 间距”聚合，止盈维度通过取最大评分折叠，避免图表过于拥挤。
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


def _build_run_chart_summary(run_result: dict[str, object], run_words: dict[str, float | bool]) -> str:
    """生成单次回测图的速读总结。"""
    summary = run_result["summary"]
    history = run_result["history"]
    end_price = float(history.iloc[-1]["Close"])
    entry_price = float(summary["EntryPrice"])
    effective_cost = float(summary["EffectiveCost"])
    price_change_pct = (end_price / entry_price - 1) * 100 if entry_price else 0.0
    cost_gap_pct = (end_price / effective_cost - 1) * 100 if effective_cost else 0.0
    cycles = int(summary["GridCyclesCompleted"])
    realized_profit = float(summary["RealizedGridProfit"])
    if end_price >= effective_cost:
        cost_comment = (
            f"样本结束时收盘价 `{end_price:.2f}` 已经回到有效成本 `{effective_cost:.2f}` 之上，"
            f"剩余持仓按摊薄口径已经转回浮盈区。"
        )
    else:
        cost_comment = (
            f"样本结束时收盘价 `{end_price:.2f}` 仍低于有效成本 `{effective_cost:.2f}`，"
            f"剩余持仓按摊薄口径还处在约 `{abs(cost_gap_pct):.2f}%` 的浮亏区。"
        )

    if cycles > 0:
        cycle_comment = (
            f"图里的买卖点一共完成了 `{cycles}` 轮网格闭环，"
            f"已经落袋的网格利润累计 `{realized_profit:.2f}`。"
        )
    else:
        cycle_comment = "这段区间里没有完成任何网格闭环，所以图上即使有持仓波动，也还没有形成已落袋的网格利润。"

    if float(summary["ReturnPct"]) >= 0:
        account_comment = (
            f"总账户最终是盈利状态，期末权益 `{run_words['final_equity']:.2f}`，"
            f"说明底仓浮盈浮亏加上网格利润后，整体结果已经转正。"
        )
    else:
        account_comment = (
            f"总账户最终仍是亏损状态，期末权益 `{run_words['final_equity']:.2f}`；"
            f"也就是说，网格已实现利润还没完全覆盖底仓和未平仓仓位的回撤。"
        )

    return "\n".join(
        [
            f"- 这一段价格从 `{entry_price:.2f}` 走到 `{end_price:.2f}`，区间涨跌幅约 `{price_change_pct:.2f}%`。",
            f"- {cost_comment}",
            f"- {cycle_comment}",
            f"- {account_comment}",
        ]
    )


def _build_heatmap_summary(results: pd.DataFrame) -> str:
    """生成热力图结论，减少读者自己猜颜色和最优区间。"""
    best_row = results.sort_values(["Score", "ReturnPct"], ascending=[False, False]).iloc[0]
    best_score = float(best_row["Score"])
    best_spacing = float(best_row["GridSpacingPct"])
    best_count = int(best_row["GridCount"])
    best_take_profit = float(best_row["TakeProfitPct"])
    top_candidates = results.sort_values(["Score", "ReturnPct"], ascending=[False, False]).head(5)
    same_best_rows = results[(results["Score"] - best_score).abs() < 1e-9]

    if same_best_rows["GridCount"].nunique() > 1:
        min_count = int(same_best_rows["GridCount"].min())
        max_count = int(same_best_rows["GridCount"].max())
        plateau_comment = (
            f"最亮的区域不是单个点，而是网格层数 `{min_count}` 到 `{max_count}` 的一段平台，"
            "说明继续把层数加深，并没有明显抬高综合得分。"
        )
    else:
        plateau_comment = (
            f"最优点比较集中在网格间距 `{best_spacing:.2f}%`、网格层数 `{best_count}` 附近，"
            "说明这组参数不是完全随机撞出来的。"
        )

    top_spacing = float(top_candidates["GridSpacingPct"].mode().iloc[0])
    top_count = int(top_candidates["GridCount"].mode().iloc[0])
    return "\n".join(
        [
            "- 热力图横轴是网格间距，纵轴是网格层数，颜色越偏绿代表综合评分越高；每个格子里没有单独画出的止盈比例，已经折叠成该格子的最好结果。",
            (
                f"- 当前样本里，最优参数落在“网格间距 `{best_spacing:.2f}%` / "
                f"网格层数 `{best_count}` / 止盈比例 `{best_take_profit:.2f}%`”。"
            ),
            f"- 从前几名结果看，高分区域主要集中在网格间距 `{top_spacing:.2f}%`、网格层数 `{top_count}` 附近。",
            f"- {plateau_comment}",
        ]
    )


def _build_exec_summary(
    in_sample_summary: dict[str, object],
    validation_summary: dict[str, object],
    optimization_results: pd.DataFrame,
) -> str:
    """生成放在报告前部的极简结论。"""
    best_row = optimization_results.sort_values(["Score", "ReturnPct"], ascending=[False, False]).iloc[0]
    same_best_rows = optimization_results[
        (optimization_results["Score"] - float(best_row["Score"])).abs() < 1e-9
    ]
    best_spacing = float(best_row["GridSpacingPct"])
    best_count = int(best_row["GridCount"])
    best_take_profit = float(best_row["TakeProfitPct"])
    count_platform = ""
    if same_best_rows["GridCount"].nunique() > 1:
        count_platform = (
            f"，而且网格层数 `{int(same_best_rows['GridCount'].min())}` 到 "
            f"`{int(same_best_rows['GridCount'].max())}` 的表现差别不大"
        )

    if float(in_sample_summary["ReturnPct"]) >= 0:
        in_sample_conclusion = (
            f"样本内这套参数最终赚钱，收益率 `{float(in_sample_summary['ReturnPct']):.2f}%`，"
            f"但中途最大回撤也到了 `{float(in_sample_summary['MaxDrawdownPct']):.2f}%`。"
        )
    else:
        in_sample_conclusion = (
            f"样本内虽然通过网格把成本压低了 `{float(in_sample_summary['CostReductionPct']):.2f}%`，"
            f"但总账户最终还是亏损 `{abs(float(in_sample_summary['ReturnPct'])):.2f}%`。"
        )

    if float(validation_summary["ReturnPct"]) >= 0:
        validation_conclusion = (
            f"样本外结果转正，收益率 `{float(validation_summary['ReturnPct']):.2f}%`，"
            "说明这组参数在新阶段还有一定延续性。"
        )
    else:
        validation_conclusion = (
            f"样本外依然没有转正，收益率 `{float(validation_summary['ReturnPct']):.2f}%`，"
            "说明它更像摊薄成本工具，而不是独立盈利策略。"
        )

    return "\n".join(
        [
            f"- 先看结论：{in_sample_conclusion}",
            (
                f"- 最值得关注的参数组合是“网格间距 `{best_spacing:.2f}%` / 网格层数 `{best_count}` / "
                f"止盈比例 `{best_take_profit:.2f}%`”{count_platform}。"
            ),
            f"- 再看样本外：{validation_conclusion}",
        ]
    )


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
            f"- 初始规则：样本开始时投入 50% 资金建底仓，剩余 50% 资金做网格买卖",
            f"- 最小交易单位：{int(best_summary['LotSize'])} 股，来源：{best_summary['LotSizeSource']}",
            f"- 固定底仓数量：{int(best_summary['BaseUnits'])} 股",
            f"- 单层网格固定数量：{int(best_summary['GridUnitsPerLevel'])} 股",
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
            f"- 初始规则：样本开始时投入 50% 资金建底仓，剩余 50% 资金做网格买卖",
            f"- 最小交易单位：{int(best_summary['LotSize'])} 股，来源：{best_summary['LotSizeSource']}",
            f"- 固定底仓数量：{int(best_summary['BaseUnits'])} 股",
            f"- 单层网格固定数量：{int(best_summary['GridUnitsPerLevel'])} 股",
            f"- 最优参数：网格间距 {best_summary['GridSpacingPct']:.2f}% / 网格层数 {int(best_summary['GridCount'])} / 止盈比例 {best_summary['TakeProfitPct']:.2f}%",
        ]
        validation_title = "2026 样本外验证"
        conclusion_tail = "如果后续继续扩展策略，优先方向应该是加入趋势过滤或分阶段停手机制，而不是单纯增加网格层数。"

    # 结论语句是报告层的解释模板，不参与回测结果计算。
    if best_summary["ReturnPct"] <= 0 and validation_summary["ReturnPct"] <= 0:
        conclusion = "在这轮样本里，网格交易能摊薄持仓成本，但还没有把总账户稳定拉回正收益。"
    elif best_summary["ReturnPct"] > 0 and validation_summary["ReturnPct"] > 0:
        conclusion = "网格交易在本轮样本里同时改善了成本和总收益，参数延续性相对更强。"
    else:
        conclusion = "这轮样本里，网格交易的效果呈现阶段性差异，需要结合样本内外所处行情阶段一起理解。"
    validation_scope = "分钟线样本外区间" if workflow_type == "minute" else "2026 样本外区间"
    if not validation_words["triggered_entry"]:
        validation_comment = f"{validation_scope}未能完成样本起点建仓，因此这段结果不能直接用来证明参数有效或失效。"
    elif validation_summary["ReturnPct"] < 0:
        validation_comment = f"{validation_scope}延续了成本摊薄，但收益仍为负，说明策略更像风险缓冲而不是单独的反转信号。"
    elif validation_summary["ReturnPct"] > 0:
        validation_comment = f"{validation_scope}收益转正，说明最优参数在新阶段仍具一定延续性。"
    else:
        validation_comment = f"{validation_scope}最终回到盈亏平衡附近，说明这套参数至少没有在这段样本里造成新的损失。"

    total_pnl_text = "盈利" if in_sample_words["total_pnl"] >= 0 else "亏损"
    validation_total_pnl_text = "盈利" if validation_words["total_pnl"] >= 0 else "亏损"
    grid_vs_base_text = "多赚了" if in_sample_words["grid_vs_base_only"] >= 0 else "多亏了"
    in_sample_chart_summary = _build_run_chart_summary(optimization["best_run"], in_sample_words)
    validation_chart_summary = _build_run_chart_summary(validation["run"], validation_words)
    heatmap_summary = _build_heatmap_summary(optimization["results"])
    exec_summary = _build_exec_summary(best_summary, validation_summary, optimization["results"])
    if validation_words["triggered_entry"]:
        # 验证段尽量复用结构化字段，避免在报告层二次推导造成口径漂移。
        validation_extra_lines = f"""- 期末有效持仓成本：{validation_summary["EffectiveCost"]:.2f}
- 把已经兑现的网格利润算进去后，当前剩余仓位的摊薄成本大约是 `{validation_summary["EffectiveCost"]:.2f}`。
- 相对样本外首笔建仓成本下降：{validation_summary["CostReductionPct"]:.2f}%
- 和样本外首笔底仓买入价相比，当前持仓成本被压低了 `{validation_summary["CostReductionPct"]:.2f}%`。
- 网格已实现收益：{validation_summary["RealizedGridProfit"]:.2f}
- 这部分是已经完成低买高卖、真正落袋的利润，样本外累计为 `{validation_summary["RealizedGridProfit"]:.2f}`。
- 完成网格循环次数：{int(validation_summary["GridCyclesCompleted"])}
- 这段样本外区间里，网格实际完成了 `{int(validation_summary["GridCyclesCompleted"])}` 轮买入后反弹卖出的闭环。"""
    else:
        validation_extra_lines = """- 本段样本外没有成功建立底仓，因此没有发生任何网格成交。
- 没有持仓、也没有成交时，收益率停在原地是正常结果。"""
    in_sample_event_table = _build_event_table(optimization["best_run"])
    in_sample_trade_table = _build_trade_table(optimization["best_run"])
    validation_event_table = _build_event_table(validation["run"])
    validation_trade_table = _build_trade_table(validation["run"])
    report_content = f"""# 小米港股网格回测报告

## 摘要

{chr(10).join(summary_lines)}

{conclusion}

## 第一层：先看结论

### 老板一眼看懂版

{exec_summary}

### 怎么使用这份报告

- 如果你只想判断这套参数值不值得继续研究，看完上面 3 条就够了。
- 如果你想知道为什么会得出这个结论，再往下看“第二层：展开细节”。

## 第二层：展开细节

### 样本内寻参结果

- 样本内首笔建仓日：{decline_window.entry_date}
- 样本内建仓价：{decline_window.entry_price:.2f}
- 最小交易单位：{int(best_summary["LotSize"])} 股
- 固定底仓数量：{int(best_summary["BaseUnits"])} 股
- 单层网格固定数量：{int(best_summary["GridUnitsPerLevel"])} 股
- 网格层数含义：最多允许开启 {int(best_summary["GridCount"])} 层“固定股数”网格仓位，不再是“每层分多少钱”
- 样本内收益率：{best_summary["ReturnPct"]:.2f}%
  - 按这套策略跑完样本内区间，账户从 `200000` 走到 `{in_sample_words["final_equity"]:.2f}`，合计{total_pnl_text} `{abs(in_sample_words["total_pnl"]):.2f}`。
- 样本内年化收益率：{best_summary["AnnualReturnPct"]:.2f}%
  - 这个数主要拿来和别的策略横向比较，表示把当前样本期收益折算成年化后的结果。
- 样本内最大回撤：{best_summary["MaxDrawdownPct"]:.2f}%
  - 这段样本里最难受的时候，账户相对阶段高点最多回撤了 `{best_summary["MaxDrawdownPct"]:.2f}%`。
- 期末有效持仓成本：{best_summary["EffectiveCost"]:.2f}
  - 把已经兑现的网格利润算进去后，当前剩余仓位的摊薄成本大约是 `{best_summary["EffectiveCost"]:.2f}`。
- 相对初始建仓成本下降：{best_summary["CostReductionPct"]:.2f}%
  - 和最初底仓买入价 `{decline_window.entry_price:.2f}` 相比，当前持仓成本被压低了 `{best_summary["CostReductionPct"]:.2f}%`。
- 网格已实现收益：{best_summary["RealizedGridProfit"]:.2f}
  - 这部分是已经完成低买高卖、真正落袋的利润，样本内累计为 `{best_summary["RealizedGridProfit"]:.2f}`。
- 完成网格循环次数：{int(best_summary["GridCyclesCompleted"])}
  - 这段样本里，网格实际完成了 `{int(best_summary["GridCyclesCompleted"])}` 轮买入后反弹卖出的闭环。

### 样本内怎么看懂

- 如果你只按规则先买 `50%` 底仓，后面完全不做网格，到样本结束时账户大约是 `{in_sample_words["base_only_equity"]:.2f}`。
- 当前这版网格策略的最终账户是 `{in_sample_words["final_equity"]:.2f}`，收益率 `{best_summary["ReturnPct"]:.2f}%`。
- 这里每次网格买入的不是固定金额，而是固定 `{int(best_summary["GridUnitsPerLevel"])}` 股；只要跌到下一层，就按同样股数再买一层。
- 也就是说：网格本身虽然已经落袋赚了 `{best_summary["RealizedGridProfit"]:.2f}`，但额外接进来的下跌仓位浮盈浮亏也会影响总账户，所以整套策略相对“只拿底仓不做网格”{grid_vs_base_text} `{abs(in_sample_words["grid_vs_base_only"]):.2f}`。
- 所以这里不能把“网格已实现收益”直接理解成“整个策略赚了这么多钱”；它只代表网格来回滚动已经兑现的那部分利润。

### 关于收益曲线为什么看起来像 0

- 图里的收益曲线不是全程为 0。
- 现在这版策略在样本开始时就直接建仓，所以收益曲线会从首笔底仓建立后立即开始波动。
- 如果你肉眼看图时觉得它“贴着 0”，通常是因为整体盈亏波动幅度不大，或者样本后半段虽然有网格利润，但总账户仍在盈亏平衡附近徘徊。

### 图表速读总结

{in_sample_chart_summary}

### 热力图速读总结

{heatmap_summary}

![样本内回测图](figures/{in_sample_chart.name})

![样本内参数热力图](figures/{search_chart.name})

### {validation_title}

- 样本外收益率：{validation_summary["ReturnPct"]:.2f}%
  - 按同一套参数跑完样本外区间，账户从 `200000` 走到 `{validation_words["final_equity"]:.2f}`，合计{validation_total_pnl_text} `{abs(validation_words["total_pnl"]):.2f}`。
- 样本外年化收益率：{validation_summary["AnnualReturnPct"]:.2f}%
  - 这个数主要拿来和别的策略横向比较，表示把当前样本外收益折算成年化后的结果。
- 样本外最大回撤：{validation_summary["MaxDrawdownPct"]:.2f}%
  - 样本外这段时间里，账户相对阶段高点最多回撤了 `{validation_summary["MaxDrawdownPct"]:.2f}%`。
- 样本外沿用最小交易单位：{int(validation_summary["LotSize"])} 股
- 样本外单层网格固定数量：{int(validation_summary["GridUnitsPerLevel"])} 股
{validation_extra_lines}

{validation_comment}

### 样本外图表速读总结

{validation_chart_summary}

![样本外回测图](figures/{validation_chart.name})

### 交易记录

### 样本内事件流水

{in_sample_event_table}

### 样本内成交结果

{in_sample_trade_table}

### 样本外事件流水

{validation_event_table}

### 样本外成交结果

{validation_trade_table}

## 最终结论

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
