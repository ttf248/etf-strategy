from __future__ import annotations
"""报告与图表输出层。

这里不重新实现回测逻辑，只负责把工作流产出的结构化结果翻译成：
- 图表
- Markdown 表格
- 更接近投资者视角的中文说明
"""

from pathlib import Path
import re
from time import perf_counter

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from loguru import logger

from strategy_studio.config import (
    DEFAULT_MINUTE_REPORT_DIR,
    DEFAULT_REPORT_DIR,
    DEFAULT_REPORT_INDEX_PATH,
    DEFAULT_REPORT_REGISTRY_PATH,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SYMBOL,
)
from strategy_studio.symbols import (
    CN_ETF_513050,
    HSTECH_CONSTITUENTS,
    INDEX_GRID_159605,
    INDEX_GRID_159866,
    INDEX_GRID_159941,
    SymbolSpec,
)


GOOD_RETURN_HIGHLIGHT_THRESHOLD_PCT = 5.0


def configure_matplotlib() -> None:
    """配置中文绘图环境。"""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


REPORT_INDEX_COLUMNS = [
    "Symbol",
    "Name",
    "Category",
    "Source",
    "Interval",
    "ReportView",
    "StrategyKind",
    "StrategyName",
    "Status",
    "ValidationNetReturnPct",
    "ValidationMaxDrawdownPct",
    "Note",
    "Error",
    "ReportPath",
    "GeneratedAt",
]


def _symbol_specs_by_symbol() -> dict[str, SymbolSpec]:
    specs = {spec.symbol.upper(): spec for spec in HSTECH_CONSTITUENTS}
    specs[CN_ETF_513050.symbol.upper()] = CN_ETF_513050
    specs[INDEX_GRID_159941.symbol.upper()] = INDEX_GRID_159941
    specs[INDEX_GRID_159605.symbol.upper()] = INDEX_GRID_159605
    specs[INDEX_GRID_159866.symbol.upper()] = INDEX_GRID_159866
    return specs


def resolve_symbol_spec(symbol: str) -> SymbolSpec:
    normalized = symbol.strip().upper()
    specs = _symbol_specs_by_symbol()
    if normalized in specs:
        return specs[normalized]
    if normalized == DEFAULT_SYMBOL:
        return SymbolSpec(symbol=normalized, name=normalized, category="默认标的", source="项目默认标的")
    return SymbolSpec(symbol=normalized, name=normalized, category="自定义标的", source="命令行或本地报告")


def _report_index_key(entry: dict[str, object]) -> str:
    return "|".join(
        [
            str(entry.get("Symbol", "")).upper(),
            str(entry.get("Interval", "")),
            str(entry.get("ReportView", "")),
        ]
    )


def _generated_at_sort_key(value: object) -> tuple[int, str]:
    text = str(value or "")
    if text == "legacy":
        return (0, "")
    return (1, text)


def _relative_markdown_link(target: str | Path, base_dir: Path) -> str:
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = target_path.resolve()
    return target_path.relative_to(base_dir.resolve()).as_posix()


def _registry_path(report_root: str | Path = DEFAULT_REPORT_ROOT) -> Path:
    root = Path(report_root)
    if root.resolve() == DEFAULT_REPORT_ROOT.resolve():
        return DEFAULT_REPORT_REGISTRY_PATH
    return root / DEFAULT_REPORT_REGISTRY_PATH.name


def _index_path(report_root: str | Path = DEFAULT_REPORT_ROOT) -> Path:
    root = Path(report_root)
    if root.resolve() == DEFAULT_REPORT_ROOT.resolve():
        return DEFAULT_REPORT_INDEX_PATH
    return root / DEFAULT_REPORT_INDEX_PATH.name


def load_report_registry(report_root: str | Path = DEFAULT_REPORT_ROOT) -> pd.DataFrame:
    registry_path = _registry_path(report_root)
    if not registry_path.exists():
        return pd.DataFrame(columns=REPORT_INDEX_COLUMNS)
    registry = pd.read_csv(registry_path, encoding="utf-8-sig")
    for column in REPORT_INDEX_COLUMNS:
        if column not in registry.columns:
            registry[column] = ""
    return registry.loc[:, REPORT_INDEX_COLUMNS].fillna("")


def register_report_index_entries(
    entries: list[dict[str, object]],
    report_root: str | Path = DEFAULT_REPORT_ROOT,
) -> Path:
    """把报告记录写入统一注册表，后续再统一重建 Markdown 总报告。"""
    registry_path = _registry_path(report_root)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry = load_report_registry(report_root)
    merged_entries = {
        _report_index_key(record): {column: record.get(column, "") for column in REPORT_INDEX_COLUMNS}
        for record in registry.to_dict(orient="records")
    }
    for entry in entries:
        normalized = {column: entry.get(column, "") for column in REPORT_INDEX_COLUMNS}
        key = _report_index_key(normalized)
        current = merged_entries.get(key)
        if current is None:
            merged_entries[key] = normalized
            continue
        current_status = str(current.get("Status", ""))
        new_status = str(normalized.get("Status", ""))
        current_generated = _generated_at_sort_key(current.get("GeneratedAt", ""))
        new_generated = _generated_at_sort_key(normalized.get("GeneratedAt", ""))
        if current_status != "ok" and new_status == "ok":
            merged_entries[key] = normalized
        elif current_status == new_status and new_generated >= current_generated:
            merged_entries[key] = normalized
    updated = pd.DataFrame(merged_entries.values(), columns=REPORT_INDEX_COLUMNS)
    updated = updated.sort_values(["Category", "Symbol", "Interval", "ReportView"], na_position="last").reset_index(drop=True)
    updated.to_csv(registry_path, index=False, encoding="utf-8-sig")
    return registry_path


def _parse_legacy_batch_index(report_root: str | Path = DEFAULT_REPORT_ROOT) -> list[dict[str, object]]:
    """兼容历史 hstech_15m_report_index.md，迁移后可直接删除旧文件。"""
    legacy_path = Path(report_root) / "hstech_15m_report_index.md"
    if not legacy_path.exists():
        return []
    entries: list[dict[str, object]] = []
    for line in legacy_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        if "分类" in line or " --- " in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 9:
            continue
        category, symbol, name, interval, validation_return, max_drawdown, status, note, report_cell = cells
        link_match = re.search(r"\(([^)]+)\)", report_cell)
        report_path = link_match.group(1) if link_match else ""
        spec = resolve_symbol_spec(symbol)
        entries.append(
            {
                "Symbol": symbol,
                "Name": name or spec.name,
                "Category": category or spec.category,
                "Source": spec.source,
                "Interval": interval,
                "ReportView": "grid",
                "StrategyKind": "grid",
                "StrategyName": "网格",
                "Status": status,
                "ValidationNetReturnPct": validation_return.replace("%", "") if validation_return != "-" else "",
                "ValidationMaxDrawdownPct": max_drawdown.replace("%", "") if max_drawdown != "-" else "",
                "Note": note,
                "Error": note if status != "ok" else "",
                "ReportPath": report_path,
                "GeneratedAt": "legacy",
            }
        )
    return entries


def bootstrap_report_registry(report_root: str | Path = DEFAULT_REPORT_ROOT) -> Path:
    """用历史批量索引初始化统一注册表。"""
    registry = load_report_registry(report_root)
    if not registry.empty:
        return _registry_path(report_root)
    legacy_entries = _parse_legacy_batch_index(report_root)
    if not legacy_entries:
        return _registry_path(report_root)
    return register_report_index_entries(legacy_entries, report_root=report_root)


def build_report_index_entry(
    report_path: str | Path,
    symbol: str,
    interval: str,
    report_view: str,
    strategy_kind: str,
    strategy_name: str,
    validation_return_pct: float | str | None,
    max_drawdown_pct: float | str | None,
    note: str,
    status: str = "ok",
    error: str = "",
    category: str | None = None,
    name: str | None = None,
    source: str | None = None,
    generated_at: str | None = None,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
) -> dict[str, object]:
    spec = resolve_symbol_spec(symbol)
    return {
        "Symbol": symbol.upper(),
        "Name": name or spec.name,
        "Category": category or spec.category,
        "Source": source or spec.source,
        "Interval": interval,
        "ReportView": report_view,
        "StrategyKind": strategy_kind,
        "StrategyName": strategy_name,
        "Status": status,
        "ValidationNetReturnPct": validation_return_pct if validation_return_pct is not None else "",
        "ValidationMaxDrawdownPct": max_drawdown_pct if max_drawdown_pct is not None else "",
        "Note": note,
        "Error": error,
        "ReportPath": _relative_markdown_link(report_path, Path(report_root)),
        "GeneratedAt": generated_at or pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_unified_report_index(report_root: str | Path = DEFAULT_REPORT_ROOT) -> Path:
    """根据统一注册表重建唯一 Markdown 汇总报告。"""
    bootstrap_report_registry(report_root)
    registry = load_report_registry(report_root)
    report_root_path = Path(report_root)
    report_root_path.mkdir(parents=True, exist_ok=True)
    target = _index_path(report_root)
    if registry.empty:
        target.write_text("# 正式报告总览\n\n暂无记录。\n", encoding="utf-8")
        return target

    registry["ValidationNetReturnPct"] = pd.to_numeric(registry["ValidationNetReturnPct"], errors="coerce")
    registry["ValidationMaxDrawdownPct"] = pd.to_numeric(registry["ValidationMaxDrawdownPct"], errors="coerce")
    ok_rows = registry[registry["Status"] == "ok"].copy()
    failed_rows = registry[registry["Status"] != "ok"].copy()

    table_rows: list[str] = []
    for row in registry.sort_values(["Category", "Symbol", "Interval", "ReportView"]).itertuples(index=False):
        report_target = str(row.ReportPath)
        report_link = f"[打开报告]({report_target})" if report_target else "未生成"
        highlight_good_return = (
            str(row.Status) == "ok"
            and not pd.isna(row.ValidationNetReturnPct)
            and float(row.ValidationNetReturnPct) > GOOD_RETURN_HIGHLIGHT_THRESHOLD_PCT
        )
        validation_return = "-" if pd.isna(row.ValidationNetReturnPct) else f"{float(row.ValidationNetReturnPct):.2f}%"
        max_drawdown = "-" if pd.isna(row.ValidationMaxDrawdownPct) else f"{float(row.ValidationMaxDrawdownPct):.2f}%"
        symbol_display = f"**{row.Symbol}**" if highlight_good_return else str(row.Symbol)
        name_display = f"**{row.Name}**" if highlight_good_return else str(row.Name)
        validation_return_display = f"**{validation_return}**" if highlight_good_return and validation_return != "-" else validation_return
        note_text = str(row.Note).replace("|", "/")
        note_display = f"**{note_text}**" if highlight_good_return and note_text else note_text
        table_rows.append(
            "| "
            + " | ".join(
                [
                    str(row.Category),
                    symbol_display,
                    name_display,
                    str(row.Interval),
                    str(row.ReportView),
                    str(row.StrategyName),
                    validation_return_display,
                    max_drawdown,
                    str(row.Status),
                    note_display,
                    report_link,
                ]
            )
            + " |"
        )

    content = "\n".join(
        [
            "# 正式报告总览",
            "",
            "## 汇总说明",
            "",
            f"- 正式报告总数：`{len(registry)}`，成功 `{'%d' % len(ok_rows)}`，失败 `{'%d' % len(failed_rows)}`。",
            "- 这份文件是唯一正式汇总报告；单个合约、批量合约、单策略报告和多策略对比报告都收录在同一张表里。",
            "- 主键口径：`symbol + interval + report_view`；同一视图重复生成时会覆盖旧记录。",
            f"- 样本外净收益率高于 `{GOOD_RETURN_HIGHLIGHT_THRESHOLD_PCT:.2f}%` 的记录会在总表中加粗，便于先看高收益候选。",
            "",
            "## 报告列表",
            "",
            "| 分类 | 标的 | 名称 | 周期 | 视图 | 策略 | 样本外收益 | 最大回撤 | 状态 | 备注 | 报告 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            *table_rows,
            "",
        ]
    )
    target.write_text(content, encoding="utf-8")
    return target


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

    figure, axes = plt.subplots(4, 1, figsize=(16, 15), sharex=True)
    figure.suptitle(title, fontsize=16, fontweight="bold")

    axes[0].plot(history["Date"], history["Close"], color="#1f77b4", linewidth=1.6, label="收盘价")
    axes[0].plot(history["Date"], history["EffectiveCost"], color="#d62728", linewidth=1.4, label="持仓有效成本")
    if not events.empty:
        # 价格图上的散点只负责帮助人眼定位关键交易，不承载收益计算逻辑。
        marker_map = {
            "grid_buy": ("v", "#31a354", "网格买入"),
            "grid_sell": ("o", "#756bb1", "网格卖出"),
            "force_exit_sell": ("x", "#de2d26", "强制卖出"),
            "base_buy": ("^", "#1f78b4", "底仓买入"),
            "retrace_buy": ("v", "#33a02c", "反弹买入"),
            "retrace_sell": ("o", "#ff7f00", "回落卖出"),
            "dca_buy": ("^", "#2ca25f", "定投买入"),
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
        label="组合收益率",
    )
    axes[2].plot(equity_curve["Date"], equity_curve["DrawdownPct"], color="#d62728", linewidth=1.2, label="回撤比例")
    axes[2].axhline(0, color="#7f7f7f", linewidth=0.8)
    axes[2].set_ylabel("百分比")
    axes[2].legend(loc="upper right")

    if "PositionRatioPct" in history.columns:
        axes[3].plot(history["Date"], history["PositionRatioPct"], color="#6a51a3", linewidth=1.4, label="仓位占用")
        max_position_ratio = float(run_result["summary"].get("MaxPositionRatio", 100.0))
        axes[3].axhline(max_position_ratio, color="#9e9ac8", linewidth=1.0, linestyle="--", label="仓位上限")
        axes[3].set_ylabel("仓位(%)")
    if "TransactionCostCumulative" in history.columns:
        cost_axis = axes[3].twinx()
        cost_axis.plot(
            history["Date"],
            history["TransactionCostCumulative"],
            color="#e6550d",
            linewidth=1.2,
            label="累计手续费",
        )
        if "SlippageCostCumulative" in history.columns:
            cost_axis.plot(
                history["Date"],
                history["SlippageCostCumulative"],
                color="#31a354",
                linewidth=1.2,
                label="累计滑点",
            )
        cost_axis.set_ylabel("成本")
        lines, labels = axes[3].get_legend_handles_labels()
        cost_lines, cost_labels = cost_axis.get_legend_handles_labels()
        axes[3].legend(lines + cost_lines, labels + cost_labels, loc="upper right", ncol=4)
    else:
        axes[3].legend(loc="upper right")
    axes[3].set_xlabel("日期")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return target


def _describe_run_in_plain_words(run_result: dict[str, object], total_capital: float = 200000.0) -> dict[str, float | bool]:
    """把回测结果翻译成更接近投资者视角的金额口径。"""
    summary = run_result["summary"]
    total_capital = float(summary.get("TotalCapital", total_capital))

    final_equity = float(summary["FinalEquity"])
    total_pnl = final_equity - total_capital
    triggered_entry = bool(summary.get("TriggeredGridEntry", summary.get("TriggeredEntry", False)))
    cash_idle_equity = float(summary.get("CashIdleFinalEquity", total_capital))
    cash_idle_pnl = cash_idle_equity - total_capital
    buy_hold_equity = float(summary.get("BuyHoldFinalEquity", cash_idle_equity))
    buy_hold_pnl = buy_hold_equity - total_capital

    return {
        "final_equity": final_equity,
        "total_pnl": total_pnl,
        "cash_idle_equity": cash_idle_equity,
        "cash_idle_pnl": cash_idle_pnl,
        "cash_idle_return_pct": cash_idle_pnl / total_capital * 100,
        "grid_vs_cash_idle": final_equity - cash_idle_equity,
        # 旧 key 作为报告内部过渡别名，避免下方历史函数漏改时报错。
        "base_only_equity": cash_idle_equity,
        "base_only_pnl": cash_idle_pnl,
        "base_only_return_pct": cash_idle_pnl / total_capital * 100,
        "grid_vs_base_only": final_equity - cash_idle_equity,
        "buy_hold_equity": buy_hold_equity,
        "buy_hold_pnl": buy_hold_pnl,
        "buy_hold_return_pct": buy_hold_pnl / total_capital * 100,
        "grid_vs_buy_hold": final_equity - buy_hold_equity,
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


def _build_simple_markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    """生成简单 Markdown 表格，用于报告里的结论与对比区块。"""
    if not rows:
        return "暂无记录。"
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = []
    for row in rows:
        row_lines.append("| " + " | ".join(_format_markdown_value(value) for value in row) + " |")
    return "\n".join([header_line, separator_line, *row_lines])


def _build_event_table(run_result: dict[str, object]) -> str:
    return _build_markdown_table(
        run_result["events"],
        columns=[
            "Date",
            "EventType",
            "Level",
            "Price",
            "ExecutionPrice",
            "Units",
            "CashFlow",
            "TransactionCost",
            "SlippageCost",
            "Note",
        ],
        rename_map={
            "Date": "时间",
            "EventType": "事件类型",
            "Level": "层级",
            "Price": "价格",
            "ExecutionPrice": "估算成交价",
            "Units": "数量",
            "CashFlow": "金额",
            "TransactionCost": "手续费",
            "SlippageCost": "滑点成本",
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
    trades.loc[trades["Tag"] == "base", "Level"] = "历史底仓"
    trades.loc[trades["Tag"] == "retrace_grid", "Level"] = "网格仓"
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

    # 热力图只按“层数 x 间距”聚合，止盈维度通过取最大稳健评分折叠，避免图表过于拥挤。
    grid = (
        results.pivot_table(index="GridCount", columns="GridSpacingPct", values="RobustScore", aggfunc="max")
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
    axis.set_title("样本内参数稳健评分热力图")

    for row_index in range(len(grid.index)):
        for column_index in range(len(grid.columns)):
            value = grid.iloc[row_index, column_index]
            axis.text(column_index, row_index, f"{value:.1f}", ha="center", va="center", fontsize=9)

    figure.colorbar(image, ax=axis, shrink=0.9, label="稳健评分")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return target


def _symbol_to_slug(symbol: str) -> str:
    """把标的代码转换成适合文件名使用的稳定 slug。"""
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", symbol.strip().lower())
    return normalized.strip("_") or "symbol"


def _build_report_artifact_names(symbol: str, workflow_type: str, interval: str) -> dict[str, str]:
    """根据标的和周期生成报告与图表文件名。"""
    slug = _symbol_to_slug(symbol)
    if workflow_type == "minute":
        return {
            "report": f"{slug}_{interval}_grid_report.md",
            "in_sample_chart": f"{slug}_{interval}_in_sample_grid.png",
            "validation_chart": f"{slug}_{interval}_validation_grid.png",
            "search_chart": f"{slug}_{interval}_grid_search_heatmap.png",
        }
    return {
        "report": f"{slug}_grid_report.md",
        "in_sample_chart": f"{slug}_in_sample_grid.png",
        "validation_chart": f"{slug}_validation_grid.png",
        "search_chart": f"{slug}_grid_search_heatmap.png",
    }


def _build_run_chart_summary(run_result: dict[str, object], run_words: dict[str, float | bool]) -> str:
    """生成单次回测图的速读总结。"""
    summary = run_result["summary"]
    history = run_result["history"]
    end_price = float(history.iloc[-1]["Close"])
    entry_price = float(summary["EntryPrice"])
    effective_cost = float(summary["EffectiveCost"])
    position_units = int(summary.get("PositionUnits", 0))
    price_change_pct = (end_price / entry_price - 1) * 100 if entry_price else 0.0
    cost_gap_pct = (end_price / effective_cost - 1) * 100 if effective_cost else 0.0
    cycles = int(summary["GridCyclesCompleted"])
    realized_profit = float(summary["RealizedGridProfit"])
    unrealized_pnl = float(summary.get("UnrealizedPnl", 0.0))
    force_exit_triggered = bool(summary.get("ForceExitTriggered", False))
    if position_units <= 0:
        cost_comment = "样本结束时没有未平网格仓位，剩余风险已经体现在现金和已实现利润里。"
    elif end_price >= effective_cost:
        cost_comment = (
            f"样本结束时收盘价 `{end_price:.2f}` 已经回到有效成本 `{effective_cost:.2f}` 之上，"
            f"未平网格按当前口径已经转回浮盈区。"
        )
    else:
        cost_comment = (
            f"样本结束时收盘价 `{end_price:.2f}` 仍低于有效成本 `{effective_cost:.2f}`，"
            f"未平网格还处在约 `{abs(cost_gap_pct):.2f}%` 的浮亏区。"
        )

    if cycles > 0:
        cycle_comment = (
            f"图里的买卖点一共完成了 `{cycles}` 轮网格闭环，"
            f"已经落袋的网格利润累计 `{realized_profit:.2f}`。"
        )
    else:
        cycle_comment = "这段区间里没有完成任何网格闭环，所以图上即使有持仓波动，也还没有形成已落袋的网格利润。"

    risk_comment = (
        "左侧强制退出已经触发，后续不再继续开新网格。"
        if force_exit_triggered
        else f"期末未平网格浮动盈亏为 `{unrealized_pnl:.2f}`。"
    )

    if float(summary["ReturnPct"]) >= 0:
        account_comment = (
            f"总账户最终是盈利状态，期末权益 `{run_words['final_equity']:.2f}`，"
            f"说明闭环利润、未平仓浮动盈亏和现金余额合计后已经转正。"
        )
    else:
        account_comment = (
            f"总账户最终仍是亏损状态，期末权益 `{run_words['final_equity']:.2f}`；"
            f"也就是说，已实现网格利润还没完全覆盖未平仓或强制退出带来的亏损。"
        )

    return "\n".join(
        [
            f"- 这一段价格从 `{entry_price:.2f}` 走到 `{end_price:.2f}`，区间涨跌幅约 `{price_change_pct:.2f}%`。",
            f"- {cost_comment}",
            f"- {cycle_comment}",
            f"- {risk_comment}",
            f"- {account_comment}",
        ]
    )


def _build_heatmap_summary(results: pd.DataFrame) -> str:
    """生成热力图结论，减少读者自己猜颜色和最优区间。"""
    best_row = results.sort_values(
        ["RobustScore", "WalkForwardScoreMin", "WalkForwardPositiveWindowRatio", "Score", "ReturnPct"],
        ascending=[False, False, False, False, False],
    ).iloc[0]
    best_score = float(best_row["RobustScore"])
    best_spacing = float(best_row["GridSpacingPct"])
    best_count = int(best_row["GridCount"])
    best_take_profit = float(best_row["TakeProfitPct"])
    top_candidates = results.sort_values(
        ["RobustScore", "WalkForwardScoreMin", "WalkForwardPositiveWindowRatio", "Score", "ReturnPct"],
        ascending=[False, False, False, False, False],
    ).head(5)
    same_best_rows = results[(results["RobustScore"] - best_score).abs() < 1e-9]

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
            "- 热力图横轴是网格间距，纵轴是网格层数，颜色越偏绿代表稳健评分越高；每个格子里没有单独画出的止盈比例，已经折叠成该格子的最好结果。",
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
            f"样本内总账户最终亏损 `{abs(float(in_sample_summary['ReturnPct'])):.2f}%`，"
            f"闭环网格净利润为 `{float(in_sample_summary.get('ClosedGridNetProfit', 0.0)):.2f}`。"
        )

    if float(validation_summary["ReturnPct"]) >= 0:
        validation_conclusion = (
            f"样本外结果转正，收益率 `{float(validation_summary['ReturnPct']):.2f}%`，"
            "说明这组参数在新阶段还有一定延续性。"
        )
    else:
        validation_conclusion = (
            f"样本外依然没有转正，收益率 `{float(validation_summary['ReturnPct']):.2f}%`，"
            "说明这组网格参数在该行情结构下还不能独立证明盈利能力。"
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


def _build_profit_judgement(best_summary: dict[str, object], validation_summary: dict[str, object]) -> str:
    """给出面向小白的盈利结论。"""
    in_sample_return = float(best_summary["ReturnPct"])
    validation_return = float(validation_summary["ReturnPct"])
    if in_sample_return > 0 and validation_return > 0:
        return "当前样本内和样本外都为正收益，可以继续观察，但还不能直接等同于稳定实盘盈利。"
    if validation_return > 0:
        return "样本外已经转正，但样本内没有稳定赚钱，暂时只能说参数在新阶段有改善，不能证明长期稳定盈利。"
    return "当前还不能证明这套网格能稳定盈利，尤其要继续观察单边下跌时未平仓风险如何处理。"


def _build_quick_answer_table(
    best_summary: dict[str, object],
    validation_summary: dict[str, object],
    in_sample_words: dict[str, float | bool],
    validation_words: dict[str, float | bool],
) -> str:
    """用问答表格直接回答小白最关心的问题。"""
    stability_text = (
        f"{float(best_summary['WalkForwardPositiveWindowRatio']):.0f}% 窗口为正，"
        f"最差窗口收益 `{float(best_summary['WalkForwardReturnWorstPct']):.2f}%`，"
        f"收益波动 `{float(best_summary['WalkForwardReturnStdPct']):.2f}` 个百分点。"
    )
    rows = [
        [
            "这套策略能不能赚钱",
            f"{float(best_summary['ReturnPct']):.2f}%",
            f"{float(validation_summary['ReturnPct']):.2f}%",
            _build_profit_judgement(best_summary, validation_summary),
        ],
        [
            "比现金闲置好不好",
            f"{float(in_sample_words['grid_vs_cash_idle']):.2f}",
            f"{float(validation_words['grid_vs_cash_idle']):.2f}",
            "正数表示网格策略赚到钱，负数表示不交易反而更好。",
        ],
        [
            "比买入持有好不好",
            f"{float(in_sample_words['grid_vs_buy_hold']):.2f}",
            f"{float(validation_words['grid_vs_buy_hold']):.2f}",
            "买入持有用同样资金、交易单位和执行口径估算，正数表示网格更好。",
        ],
        [
            "交易成本高不高",
            f"{float(best_summary.get('TransactionCost', 0.0)):.2f}",
            f"{float(validation_summary.get('TransactionCost', 0.0)):.2f}",
            "这里统计手续费，滑点会单独体现在估算成交价和滑点成本里。",
        ],
        [
            "最坏会亏到什么程度",
            f"{float(best_summary['MaxDrawdownPct']):.2f}%",
            f"{float(validation_summary['MaxDrawdownPct']):.2f}%",
            "这是账户在样本期间相对阶段高点出现过的最大回撤。",
        ],
        [
            "这组参数稳不稳",
            f"稳健分 {float(best_summary['RobustScore']):.2f}",
            f"沿用同一组参数",
            f"不是只看一整段最高分，而是看多窗口表现是否稳定。当前结果：{stability_text}",
        ],
    ]
    return _build_simple_markdown_table(["问题", "样本内", "样本外", "怎么理解"], rows)


def _build_selection_method_table(best_summary: dict[str, object], optimization_results: pd.DataFrame) -> str:
    """说明参数为什么是这样选出来的。"""
    rows = [
        [
            "执行口径",
            str(best_summary.get("ExecutionProfile", "research")),
            (
                f"手续费 {float(best_summary.get('CommissionBps', 0.0)):.2f} bps，"
                f"滑点 {float(best_summary.get('SlippageBps', 0.0)):.2f} bps。"
            ),
        ],
        ["候选组合数", len(optimization_results), "先把候选参数全部跑完，不做随机抽样。"],
        [
            "单窗综合分",
            f"{float(best_summary['Score']):.2f}",
            "这是整段样本内的收益、回撤、闭环网格利润综合分。",
        ],
        [
            "稳健窗口数",
            int(best_summary["WalkForwardWindowCount"]),
            "再把样本内按时间顺序拆成多个连续窗口，检查同一参数会不会只在一小段行情里好看。",
        ],
        [
            "稳健分 RobustScore",
            f"{float(best_summary['RobustScore']):.2f}",
            "计算方式：0.6 x 窗口平均分 + 0.4 x 最差窗口分 - 0.25 x 窗口收益波动。",
        ],
        [
            "最终入选参数",
            (
                f"间距 {float(best_summary['GridSpacingPct']):.2f}% / "
                f"层数 {int(best_summary['GridCount'])} / 止盈 {float(best_summary['TakeProfitPct']):.2f}%"
            ),
            "优先挑多窗口更稳的组合，而不是只挑单窗最亮的孤点。",
        ],
    ]
    return _build_simple_markdown_table(["筛选环节", "结果", "你该怎么理解"], rows)


def _build_execution_risk_table(
    best_summary: dict[str, object],
    validation_summary: dict[str, object],
) -> str:
    """展示执行口径和基础风控约束。"""
    rows = [
        [
            "执行口径",
            str(best_summary.get("ExecutionProfile", "research")),
            str(validation_summary.get("ExecutionProfile", "research")),
        ],
        [
            "网格模式",
            str(best_summary.get("GridMode", "cash")),
            str(validation_summary.get("GridMode", "cash")),
        ],
        [
            "左侧处理口径",
            str(best_summary.get("RequestedLeftSidePolicy", best_summary.get("LeftSidePolicy", "hold"))),
            str(validation_summary.get("RequestedLeftSidePolicy", validation_summary.get("LeftSidePolicy", "hold"))),
        ],
        [
            "手续费 / 滑点",
            f"{float(best_summary.get('CommissionBps', 0.0)):.2f} / {float(best_summary.get('SlippageBps', 0.0)):.2f} bps",
            f"{float(validation_summary.get('CommissionBps', 0.0)):.2f} / {float(validation_summary.get('SlippageBps', 0.0)):.2f} bps",
        ],
        [
            "最大仓位占用",
            f"{float(best_summary.get('MaxPositionRatioUsed', 0.0)):.2f}% / 上限 {float(best_summary.get('MaxPositionRatio', 100.0)):.2f}%",
            f"{float(validation_summary.get('MaxPositionRatioUsed', 0.0)):.2f}% / 上限 {float(validation_summary.get('MaxPositionRatio', 100.0)):.2f}%",
        ],
        [
            "停手事件",
            int(best_summary.get("StopLossEvents", 0)),
            int(validation_summary.get("StopLossEvents", 0)),
        ],
        [
            "强制退出事件",
            int(best_summary.get("ForceExitEvents", 0)),
            int(validation_summary.get("ForceExitEvents", 0)),
        ],
    ]
    return _build_simple_markdown_table(["约束", "样本内", "样本外"], rows)


def _build_core_metric_table(
    best_summary: dict[str, object],
    validation_summary: dict[str, object],
) -> str:
    """给出最关键的对比指标，减少长段落重复解释。"""
    rows = [
        ["净收益率", f"{float(best_summary.get('NetReturnPct', best_summary['ReturnPct'])):.2f}%", f"{float(validation_summary.get('NetReturnPct', validation_summary['ReturnPct'])):.2f}%", "已经按当前执行口径扣除回测引擎支持的费用影响。"],
        [
            "最大回撤",
            f"{float(best_summary['MaxDrawdownPct']):.2f}%",
            f"{float(validation_summary['MaxDrawdownPct']):.2f}%",
            "再看亏起来最难受会到什么程度。",
        ],
        [
            "交易成本",
            f"{float(best_summary.get('TransactionCost', 0.0)):.2f}",
            f"{float(validation_summary.get('TransactionCost', 0.0)):.2f}",
            "策略内部估算的手续费累计值，帮助判断网格频繁交易是否吃掉收益。",
        ],
        [
            "滑点成本",
            f"{float(best_summary.get('SlippageCost', 0.0)):.2f}",
            f"{float(validation_summary.get('SlippageCost', 0.0)):.2f}",
            "按收盘价和估算成交价差额累计，属于近似实盘口径。",
        ],
        [
            "未平网格有效成本",
            f"{float(best_summary['EffectiveCost']):.2f}",
            f"{float(validation_summary['EffectiveCost']):.2f}",
            "只在期末仍有未平网格仓位时有意义。",
        ],
        [
            "闭环网格净利润",
            f"{float(best_summary.get('ClosedGridNetProfit', best_summary['RealizedGridProfit'])):.2f}",
            f"{float(validation_summary.get('ClosedGridNetProfit', validation_summary['RealizedGridProfit'])):.2f}",
            "这是已经完成低买高卖、真正落袋的利润，不等于总账户收益。",
        ],
        [
            "未平网格浮动盈亏",
            f"{float(best_summary.get('UnrealizedPnl', 0.0)):.2f}",
            f"{float(validation_summary.get('UnrealizedPnl', 0.0)):.2f}",
            "hold 口径会保留这部分风险，force_exit 口径触发后通常回到 0。",
        ],
        [
            "网格闭环次数",
            int(best_summary["GridCyclesCompleted"]),
            int(validation_summary["GridCyclesCompleted"]),
            "次数越多，说明震荡里成交越频繁；但次数多不等于总账户一定赚钱。",
        ],
    ]
    return _build_simple_markdown_table(["指标", "样本内", "样本外", "怎么读"], rows)


def _build_benchmark_comparison_table(
    in_sample_words: dict[str, float | bool],
    validation_words: dict[str, float | bool],
    best_summary: dict[str, object],
    validation_summary: dict[str, object],
) -> str:
    """展示网格相对现金闲置和买入持有的增益或拖累。"""
    rows = [
        [
            "现金闲置收益率",
            f"{float(in_sample_words['cash_idle_return_pct']):.2f}%",
            f"{float(validation_words['cash_idle_return_pct']):.2f}%",
        ],
        [
            "买入持有收益率",
            f"{float(in_sample_words['buy_hold_return_pct']):.2f}%",
            f"{float(validation_words['buy_hold_return_pct']):.2f}%",
        ],
        [
            "网格策略收益率",
            f"{float(best_summary.get('NetReturnPct', best_summary['ReturnPct'])):.2f}%",
            f"{float(validation_summary.get('NetReturnPct', validation_summary['ReturnPct'])):.2f}%",
        ],
        [
            "网格相对现金闲置多赚/多亏",
            f"{float(in_sample_words['grid_vs_cash_idle']):.2f}",
            f"{float(validation_words['grid_vs_cash_idle']):.2f}",
        ],
        [
            "网格相对买入持有多赚/多亏",
            f"{float(in_sample_words['grid_vs_buy_hold']):.2f}",
            f"{float(validation_words['grid_vs_buy_hold']):.2f}",
        ],
    ]
    return _build_simple_markdown_table(["对比项", "样本内", "样本外"], rows)


def _policy_label(policy: str) -> str:
    labels = {
        "hold": "hold：未平网格继续持有",
        "force_exit": "force_exit：达到亏损阈值强平",
    }
    return labels.get(policy, policy)


def _strategy_display_name(summary: dict[str, object], fallback: str | None = None) -> str:
    explicit = str(summary.get("StrategyName", "")).strip()
    if explicit and explicit.lower() != "strategy":
        return explicit
    strategy_kind = str(summary.get("StrategyKind", fallback or "grid"))
    mapping = {
        "grid": "网格",
        "dca": "定投",
        "daily_rebound": "日线超跌反弹",
        "minute_rebound": "分钟急跌反抽",
        "minute_rebound_with_fade_filter": "分钟反抽+冲高回落过滤",
        "minute_index_grid_retrace": "指数回落反弹网格",
    }
    return mapping.get(strategy_kind, strategy_kind)


def _build_policy_comparison_table(in_sample_run: dict[str, object], validation_run: dict[str, object]) -> str:
    """展示 hold 与 force_exit 两种左侧处理方式的结果差异。"""
    in_sample_policies = in_sample_run.get("policy_results")
    validation_policies = validation_run.get("policy_results")
    if not isinstance(in_sample_policies, dict) or not isinstance(validation_policies, dict):
        policy = str(in_sample_run["summary"].get("LeftSidePolicy", "hold"))
        return f"当前仅计算 `{policy}` 口径，未生成 hold / force_exit 对照。"

    rows = []
    for policy in ["hold", "force_exit"]:
        in_policy_run = in_sample_policies.get(policy)
        out_policy_run = validation_policies.get(policy)
        if not isinstance(in_policy_run, dict) or not isinstance(out_policy_run, dict):
            continue
        in_summary = in_policy_run["summary"]
        out_summary = out_policy_run["summary"]
        rows.append(
            [
                _policy_label(policy),
                f"{float(in_summary.get('NetReturnPct', in_summary['ReturnPct'])):.2f}%",
                f"{float(in_summary.get('ClosedGridNetProfit', 0.0)):.2f}",
                f"{float(in_summary.get('UnrealizedPnl', 0.0)):.2f}",
                "是" if bool(in_summary.get("ForceExitTriggered", False)) else "否",
                f"{float(out_summary.get('NetReturnPct', out_summary['ReturnPct'])):.2f}%",
                f"{float(out_summary.get('ClosedGridNetProfit', 0.0)):.2f}",
                f"{float(out_summary.get('UnrealizedPnl', 0.0)):.2f}",
                "是" if bool(out_summary.get("ForceExitTriggered", False)) else "否",
            ]
        )
    return _build_simple_markdown_table(
        ["左侧口径", "样本内净收益率", "样本内闭环利润", "样本内浮动盈亏", "样本内强平", "样本外净收益率", "样本外闭环利润", "样本外浮动盈亏", "样本外强平"],
        rows,
    )


def _build_dca_report_markdown(workflow_result: dict[str, object], report_dir: str | Path) -> Path:
    """生成定投策略报告。

    定投没有网格层数和热力图含义，因此使用独立模板，重点解释投入节奏、
    累计投入、平均成本以及相对一次性买入持有的差额。
    """
    started_at = perf_counter()
    workflow_type = workflow_result.get("workflow_type", "daily")
    interval = workflow_result.get("interval", "1d")
    optimization = workflow_result["optimization"]
    validation = workflow_result["validation"]
    decline_window = optimization["decline_window"]
    best_summary = optimization["best_run"]["summary"]
    validation_summary = validation["run"]["summary"]
    symbol = str(best_summary["Symbol"])
    target_dir = Path(report_dir)
    figure_dir = target_dir / "figures"
    target_dir.mkdir(parents=True, exist_ok=True)
    slug = _symbol_to_slug(symbol)
    suffix = f"{interval}_dca" if workflow_type == "minute" else "dca"
    report_path = target_dir / f"{slug}_{suffix}_report.md"
    in_sample_chart = plot_run_result(
        optimization["best_run"],
        figure_dir / f"{slug}_{suffix}_in_sample.png",
        f"{symbol} 样本内定投回测",
    )
    validation_chart = plot_run_result(
        validation["run"],
        figure_dir / f"{slug}_{suffix}_validation.png",
        f"{symbol} 样本外定投回测",
    )
    in_sample_words = _describe_run_in_plain_words(optimization["best_run"])
    validation_words = _describe_run_in_plain_words(validation["run"])
    quick_table = _build_simple_markdown_table(
        ["问题", "样本内", "样本外"],
        [
            ["净收益率", f"{float(best_summary['NetReturnPct']):.2f}%", f"{float(validation_summary['NetReturnPct']):.2f}%"],
            ["最大回撤", f"{float(best_summary['MaxDrawdownPct']):.2f}%", f"{float(validation_summary['MaxDrawdownPct']):.2f}%"],
            ["定投次数", f"{int(best_summary.get('DcaBuyCount', 0))}", f"{int(validation_summary.get('DcaBuyCount', 0))}"],
            ["累计投入", f"{float(best_summary.get('DcaInvestedCash', 0.0)):.2f}", f"{float(validation_summary.get('DcaInvestedCash', 0.0)):.2f}"],
            ["期末平均成本", f"{float(best_summary.get('DcaAverageCost', 0.0)):.2f}", f"{float(validation_summary.get('DcaAverageCost', 0.0)):.2f}"],
            ["相对一次性买入", f"{float(best_summary.get('GridVsBuyHold', 0.0)):.2f}", f"{float(validation_summary.get('GridVsBuyHold', 0.0)):.2f}"],
        ],
    )
    params_table = _build_simple_markdown_table(
        ["参数", "取值"],
        [
            ["每期投入金额", f"{float(best_summary.get('investment_amount', 0.0)):.2f}"],
            ["定投频率", str(best_summary.get("frequency", ""))],
            ["触发日规则", str(best_summary.get("day_rule", ""))],
            ["最大仓位", f"{float(best_summary.get('max_position_ratio', 0.0)) * 100:.2f}%"],
            ["最小交易单位", f"{int(best_summary['LotSize'])} 股"],
            ["执行口径", str(best_summary.get("ExecutionProfile", "research"))],
        ],
    )
    in_sample_chart_summary = _build_run_chart_summary(optimization["best_run"], in_sample_words)
    validation_chart_summary = _build_run_chart_summary(validation["run"], validation_words)
    report_content = f"""# {symbol} 定投回测报告

## 摘要

- 标的：`{symbol}`
- 样本内窗口：{decline_window.sample_start} 至 {decline_window.sample_end}
- 样本外窗口：{decline_window.validation_start} 至 {validation_summary['EndDate']}
- 策略：按固定周期第一个交易日投入固定金额，买入数量按最小交易单位向下取整
- 费用口径：`{best_summary.get('ExecutionProfile', 'research')}`，手续费 `{float(best_summary.get('CommissionBps', 0.0)):.2f}` bps，滑点 `{float(best_summary.get('SlippageBps', 0.0)):.2f}` bps

## 第一层：先看结论

{quick_table}

- 定投的核心问题不是单次买卖是否抓到底，而是资金投入节奏是否降低了择时风险。
- 如果相对一次性买入为正，说明分批投入在当前样本里比首日满仓更合适；反之则说明上涨行情里现金拖累更明显。

## 第二层：展开细节

### 最优定投参数

{params_table}

### 样本内回测图

{in_sample_chart_summary}

![样本内回测图](figures/{in_sample_chart.name})

### 样本外回测图

{validation_chart_summary}

![样本外回测图](figures/{validation_chart.name})

### 样本内事件流水

{_build_event_table(optimization["best_run"])}

### 样本内成交记录

{_build_trade_table(optimization["best_run"])}

### 样本外事件流水

{_build_event_table(validation["run"])}

### 样本外成交记录

{_build_trade_table(validation["run"])}

## 最终结论

- 样本外账户最终从 `200000` 走到 `{validation_words["final_equity"]:.2f}`，总盈亏 `{validation_words["total_pnl"]:.2f}`。
- 样本外累计投入 `{float(validation_summary.get('DcaInvestedCash', 0.0)):.2f}`，剩余现金和持仓市值共同决定最终权益。
- 这份报告只说明当前历史样本下定投节奏的结果，不构成实盘建议；后续可继续扩展为跨标的、跨起点的定投稳健性检验。
"""
    report_path.write_text(report_content, encoding="utf-8")
    logger.info("定投正式报告生成完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return report_path


def build_report_markdown(
    workflow_result: dict[str, object],
    report_dir: str | Path = DEFAULT_REPORT_DIR,
) -> Path:
    """根据完整工作流结果生成中文报告。"""
    started_at = perf_counter()
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
    strategy_kind = str(best_summary.get("StrategyKind", "grid"))
    if strategy_kind == "dca":
        return _build_dca_report_markdown(workflow_result, report_dir=report_dir)
    symbol = str(best_summary["Symbol"])
    logger.info("[2/2] 开始生成正式报告: symbol={} workflow_type={} report_dir={}", symbol, workflow_type, report_dir)
    in_sample_words = _describe_run_in_plain_words(optimization["best_run"])
    validation_words = _describe_run_in_plain_words(validation["run"])
    artifact_names = _build_report_artifact_names(symbol, workflow_type, interval)

    if workflow_type == "minute":
        in_sample_chart = plot_run_result(
            optimization["best_run"],
            figure_dir / artifact_names["in_sample_chart"],
            f"{symbol} 15 分钟样本内网格回测",
        )
        validation_chart = plot_run_result(
            validation["run"],
            figure_dir / artifact_names["validation_chart"],
            f"{symbol} 15 分钟样本外网格回测",
        )
        search_chart = plot_grid_search(
            optimization["results"],
            figure_dir / artifact_names["search_chart"],
        )
        report_path = target_dir / artifact_names["report"]
        summary_lines = [
            f"- 标的：`{symbol}`",
            f"- 数据周期：Yahoo Finance 最近 60 天 `{interval}`；下载必须配置代理，Yahoo 失败时流程直接停止",
            f"- 样本内窗口：{decline_window.sample_start} 至 {decline_window.sample_end}",
            f"- 样本外窗口：{decline_window.validation_start} 至 {validation_summary['EndDate']}",
            f"- 切分方式：最近分钟线样本按 `75% / 25%` 拆分样本内与样本外",
            f"- 网格模式：纯现金网格，不在样本起点建立底仓；第一根 K 线收盘价只作为网格锚点",
            f"- 最小交易单位：{int(best_summary['LotSize'])} 股，来源：{best_summary['LotSizeSource']}",
            f"- 单层网格固定数量：{int(best_summary['GridUnitsPerLevel'])} 股",
            f"- 左侧处理：`{best_summary.get('RequestedLeftSidePolicy', best_summary.get('LeftSidePolicy', 'hold'))}`，强制退出阈值 `{float(best_summary.get('ForceExitLossPct', 0.0)):.2f}%` 总资金浮亏",
            f"- 执行口径：`{best_summary.get('ExecutionProfile', 'research')}`，手续费 `{float(best_summary.get('CommissionBps', 0.0)):.2f}` bps，滑点 `{float(best_summary.get('SlippageBps', 0.0)):.2f}` bps",
            f"- 最优参数：网格间距 {best_summary['GridSpacingPct']:.2f}% / 网格层数 {int(best_summary['GridCount'])} / 止盈比例 {best_summary['TakeProfitPct']:.2f}%",
        ]
        validation_title = "分钟线样本外验证"
        conclusion_tail = "这份报告只代表最近 60 天分钟级行情下的短周期表现，不等同于长期日线参数。"
    else:
        in_sample_chart = plot_run_result(
            optimization["best_run"],
            figure_dir / artifact_names["in_sample_chart"],
            f"{symbol} 样本内网格回测",
        )
        validation_chart = plot_run_result(
            validation["run"],
            figure_dir / artifact_names["validation_chart"],
            f"{symbol} 样本外网格回测",
        )
        search_chart = plot_grid_search(
            optimization["results"],
            figure_dir / artifact_names["search_chart"],
        )
        report_path = target_dir / artifact_names["report"]
        summary_lines = [
            f"- 标的：`{symbol}`",
            f"- 样本内窗口：{decline_window.sample_start} 至 {decline_window.sample_end}",
            f"- 样本外窗口：{decline_window.validation_start} 至 {validation_summary['EndDate']}",
            f"- 网格模式：纯现金网格，不在样本起点建立底仓；第一根 K 线收盘价只作为网格锚点",
            f"- 最小交易单位：{int(best_summary['LotSize'])} 股，来源：{best_summary['LotSizeSource']}",
            f"- 单层网格固定数量：{int(best_summary['GridUnitsPerLevel'])} 股",
            f"- 左侧处理：`{best_summary.get('RequestedLeftSidePolicy', best_summary.get('LeftSidePolicy', 'hold'))}`，强制退出阈值 `{float(best_summary.get('ForceExitLossPct', 0.0)):.2f}%` 总资金浮亏",
            f"- 执行口径：`{best_summary.get('ExecutionProfile', 'research')}`，手续费 `{float(best_summary.get('CommissionBps', 0.0)):.2f}` bps，滑点 `{float(best_summary.get('SlippageBps', 0.0)):.2f}` bps",
            f"- 最优参数：网格间距 {best_summary['GridSpacingPct']:.2f}% / 网格层数 {int(best_summary['GridCount'])} / 止盈比例 {best_summary['TakeProfitPct']:.2f}%",
        ]
        validation_title = "2026 样本外验证"
        conclusion_tail = "如果后续继续扩展策略，优先方向应该是加入趋势过滤或分阶段停手机制，而不是单纯增加网格层数。"

    # 结论语句是报告层的解释模板，不参与回测结果计算。
    if best_summary["ReturnPct"] <= 0 and validation_summary["ReturnPct"] <= 0:
        conclusion = "这套网格当前还不能证明能稳定把总账户做成正收益，左侧下跌风险是主要约束。"
    elif best_summary["ReturnPct"] > 0 and validation_summary["ReturnPct"] > 0:
        conclusion = "这套网格在当前样本里样本内外都转正，说明参数具备继续观察的价值。"
    else:
        conclusion = "这套网格在不同阶段表现不一致，说明它对行情结构比较敏感，不能只看单段结果下结论。"

    if not validation_words["triggered_entry"]:
        validation_comment = "样本外这段区间没有触发任何网格买入，所以这里只能说明价格没有进入计划网格区间。"
    elif float(validation_summary["ReturnPct"]) > 0:
        validation_comment = "样本外结果转正，说明这组参数在新阶段没有立刻失效。"
    else:
        validation_comment = "样本外没有转正，说明这组参数还不能在该行情结构下独立制造稳定盈利。"

    in_sample_chart_summary = _build_run_chart_summary(optimization["best_run"], in_sample_words)
    validation_chart_summary = _build_run_chart_summary(validation["run"], validation_words)
    heatmap_summary = _build_heatmap_summary(optimization["results"])
    selection_method_table = _build_selection_method_table(best_summary, optimization["results"])
    quick_answer_table = _build_quick_answer_table(best_summary, validation_summary, in_sample_words, validation_words)
    core_metric_table = _build_core_metric_table(best_summary, validation_summary)
    execution_risk_table = _build_execution_risk_table(best_summary, validation_summary)
    benchmark_comparison_table = _build_benchmark_comparison_table(
        in_sample_words=in_sample_words,
        validation_words=validation_words,
        best_summary=best_summary,
        validation_summary=validation_summary,
    )
    policy_comparison_table = _build_policy_comparison_table(optimization["best_run"], validation["run"])
    in_sample_event_table = _build_event_table(optimization["best_run"])
    in_sample_trade_table = _build_trade_table(optimization["best_run"])
    validation_event_table = _build_event_table(validation["run"])
    validation_trade_table = _build_trade_table(validation["run"])
    report_content = f"""# {symbol} 网格回测报告

## 摘要

{chr(10).join(summary_lines)}

{conclusion}

## 第一层：先看结论

### 先回答关键问题

{quick_answer_table}

### 一句话判断

- {conclusion}
- 当前正式拿去实盘的证据还不够，更合理的定位是：先验证它能否通过网格闭环赚钱，再看左侧行情下能否控制亏损。
- 如果你只想知道现在值不值得继续研究，看完上面这张表就够了。

## 第二层：展开细节

### 参数是怎么选的

{selection_method_table}

### 关键结果对照

{core_metric_table}

### 执行口径和风控约束

{execution_risk_table}

### 网格到底有没有帮忙

{benchmark_comparison_table}

### 左侧行情怎么处理

{policy_comparison_table}

补一句最重要的解释：

- “网格已实现收益”只代表已经完成低买高卖、真正落袋的那部分利润。
- 真正决定你账户最后赚没赚钱的，是“已实现网格收益 + 未平仓网格浮动盈亏 + 现金余额”三者一起的结果。
- 所以完全可能出现“网格已经落袋赚钱，但总账户还是亏钱”的情况。

### 图表速读总结

#### 样本内回测图

{in_sample_chart_summary}

![样本内回测图](figures/{in_sample_chart.name})

#### 热力图

{heatmap_summary}

![样本内参数热力图](figures/{search_chart.name})

#### {validation_title}

- 样本外账户最终从 `200000` 走到 `{validation_words["final_equity"]:.2f}`，总盈亏 `{validation_words["total_pnl"]:.2f}`。
- 样本外单层网格按最小交易单位 `{int(validation_summary["LotSize"])}` 股取整，固定数量是 `{int(validation_summary["GridUnitsPerLevel"])}` 股。
- {validation_comment}

#### 样本外回测图

{validation_chart_summary}

![样本外回测图](figures/{validation_chart.name})

### 交易记录和明细

如果你只是想判断策略值不值得继续，到这里通常已经够了；下面这些表主要用于追交易过程和排查归因。

### 样本内事件流水

{in_sample_event_table}

### 样本内成交结果

{in_sample_trade_table}

### 样本外事件流水

{validation_event_table}

### 样本外成交结果

{validation_trade_table}

## 最终结论

- 这套参数更适合“先跌一段、再进入震荡或反弹”的行情，因为它依赖反弹来兑现网格利润。
- 如果行情持续单边下跌，hold 口径会继续持有未平网格，force_exit 口径会在浮亏达到阈值后清仓并停止交易。
- 当前样本下，闭环网格净利润：样本内 {float(best_summary.get("ClosedGridNetProfit", 0.0)):.2f}，样本外 {float(validation_summary.get("ClosedGridNetProfit", 0.0)):.2f}。
- {conclusion_tail}
"""
    report_path.write_text(report_content, encoding="utf-8")
    logger.info("[2/2] 正式报告生成完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return report_path


def _build_index_grid_report_markdown(
    workflow_result: dict[str, object],
    report_dir: str | Path,
) -> Path:
    """生成指数 ETF 动态回落/反弹网格报告。"""
    started_at = perf_counter()
    optimization = workflow_result["optimization"]
    validation = workflow_result["validation"]
    decline_window = optimization["decline_window"]
    best_summary = optimization["best_run"]["summary"]
    validation_summary = validation["run"]["summary"]
    symbol = str(best_summary["Symbol"])
    interval = str(workflow_result.get("interval", "1m"))
    target_dir = Path(report_dir)
    figure_dir = target_dir / "figures"
    target_dir.mkdir(parents=True, exist_ok=True)
    slug = _symbol_to_slug(symbol)
    report_path = target_dir / f"{slug}_{interval}_index_grid_report.md"
    in_sample_chart = plot_run_result(
        optimization["best_run"],
        figure_dir / f"{slug}_{interval}_in_sample_index_grid.png",
        f"{symbol} 1 分钟样本内指数回落反弹网格",
    )
    validation_chart = plot_run_result(
        validation["run"],
        figure_dir / f"{slug}_{interval}_validation_index_grid.png",
        f"{symbol} 1 分钟样本外指数回落反弹网格",
    )
    in_sample_words = _describe_run_in_plain_words(optimization["best_run"], total_capital=float(best_summary["TotalCapital"]))
    validation_words = _describe_run_in_plain_words(validation["run"], total_capital=float(validation_summary["TotalCapital"]))
    logger.info("[2/2] 开始生成指数 ETF 正式报告: symbol={} report_dir={}", symbol, report_dir)

    outperform_validation = bool(validation_summary.get("OutperformBuyHold", False))
    if outperform_validation:
        conclusion = "这套固定参数在当前样本外窗口里跑赢了同标的买入持有，说明低买高卖至少没有被底仓拖累。"
    elif float(validation_summary.get("StrategyVsBuyHold", 0.0)) == 0:
        conclusion = "这套固定参数在当前样本外窗口里和买入持有基本持平，暂时看不出明显优势。"
    else:
        conclusion = "这套固定参数在当前样本外窗口里没有跑赢同标的买入持有，说明最近 60 天的波动结构还不足以支撑这套网格占优。"

    quick_table = _build_simple_markdown_table(
        ["问题", "样本内", "样本外"],
        [
            ["策略净收益率", f"{float(best_summary['NetReturnPct']):.2f}%", f"{float(validation_summary['NetReturnPct']):.2f}%"],
            ["相对买入持有", f"{float(best_summary['StrategyVsBuyHold']):.2f}", f"{float(validation_summary['StrategyVsBuyHold']):.2f}"],
            ["是否跑赢买入持有", "是" if bool(best_summary["OutperformBuyHold"]) else "否", "是" if outperform_validation else "否"],
            ["网格已实现利润", f"{float(best_summary['GridRealizedProfit']):.2f}", f"{float(validation_summary['GridRealizedProfit']):.2f}"],
            ["底仓浮动盈亏", f"{float(best_summary['BaseUnrealizedPnl']):.2f}", f"{float(validation_summary['BaseUnrealizedPnl']):.2f}"],
            ["网格浮动盈亏", f"{float(best_summary['GridUnrealizedPnl']):.2f}", f"{float(validation_summary['GridUnrealizedPnl']):.2f}"],
        ],
    )
    benchmark_table = _build_simple_markdown_table(
        ["对比项", "样本内", "样本外"],
        [
            ["策略期末权益", f"{float(best_summary['FinalEquity']):.2f}", f"{float(validation_summary['FinalEquity']):.2f}"],
            ["买入持有期末权益", f"{float(best_summary['BuyHoldFinalEquity']):.2f}", f"{float(validation_summary['BuyHoldFinalEquity']):.2f}"],
            ["策略相对买入持有", f"{float(best_summary['StrategyVsBuyHold']):.2f}", f"{float(validation_summary['StrategyVsBuyHold']):.2f}"],
            ["最大回撤", f"{float(best_summary['MaxDrawdownPct']):.2f}%", f"{float(validation_summary['MaxDrawdownPct']):.2f}%"],
            ["网格买入次数", f"{int(best_summary['GridBuyCount'])}", f"{int(validation_summary['GridBuyCount'])}"],
            ["网格卖出次数", f"{int(best_summary['GridSellCount'])}", f"{int(validation_summary['GridSellCount'])}"],
        ],
    )
    rule_table = _build_simple_markdown_table(
        ["规则", "参数"],
        [
            ["总资金", f"{float(best_summary['TotalCapital']):.2f}"],
            ["底仓比例", f"{float(best_summary['BasePositionRatioPct']):.2f}%"],
            ["单次网格比例", f"{float(best_summary['GridTradeRatioPct']):.2f}%"],
            ["上涨触发", f"{float(best_summary['RiseTriggerPct']):.2f}%"],
            ["上涨后回落卖出", f"{float(best_summary['SellPullbackPct']):.2f}%"],
            ["下跌触发", f"{float(best_summary['DeclineTriggerPct']):.2f}%"],
            ["下跌后反弹买入", f"{float(best_summary['BuyReboundPct']):.2f}%"],
            ["底仓股数", f"{int(best_summary['BasePositionUnits'])}"],
            ["单次网格股数", f"{int(best_summary['GridUnitsPerTrade'])}"],
        ],
    )
    in_sample_chart_summary = _build_run_chart_summary(optimization["best_run"], in_sample_words)
    validation_chart_summary = _build_run_chart_summary(validation["run"], validation_words)
    in_sample_event_table = _build_event_table(optimization["best_run"])
    validation_event_table = _build_event_table(validation["run"])
    in_sample_trade_table = _build_trade_table(optimization["best_run"])
    validation_trade_table = _build_trade_table(validation["run"])

    report_content = f"""# {symbol} 指数回落反弹网格报告

## 摘要

- 标的：`{symbol}`
- 数据周期：Yahoo Finance 最近 60 天 `1m`
- 样本内窗口：{decline_window.sample_start} 至 {decline_window.sample_end}
- 样本外窗口：{decline_window.validation_start} 至 {validation_summary['EndDate']}
- 切分方式：最近分钟线样本按 `75% / 25%` 拆分样本内与样本外
- 交易假设：首根 K 线买入 `50%` 长期底仓，其余资金按总资金 `20%` 的固定单元做网格
- 触发语义：先达到涨跌阈值，再等待从局部高低点回落/反弹确认后成交
- 最小交易单位：{int(best_summary['LotSize'])} 股，来源：{best_summary['LotSizeSource']}
- 费用口径：`{best_summary.get('ExecutionProfile', 'research')}`，手续费 `{float(best_summary.get('CommissionBps', 0.0)):.2f}` bps，滑点 `{float(best_summary.get('SlippageBps', 0.0)):.2f}` bps

{conclusion}

## 第一层：先看结论

### 先回答关键问题

{quick_table}

### 一句话判断

- {conclusion}
- 这套策略的收益来源不是“猜趋势”，而是底仓承接指数长期上涨、网格去吃短周期波动里的低买高卖。
- 真正要盯的是“策略相对买入持有多赚了多少”，而不是只看网格已实现利润。

## 第二层：展开细节

### 固定参数与交易单元

{rule_table}

### 和买入持有相比到底有没有优势

{benchmark_table}

### 样本内回测图

{in_sample_chart_summary}

![样本内回测图](figures/{in_sample_chart.name})

### 样本外回测图

{validation_chart_summary}

![样本外回测图](figures/{validation_chart.name})

### 交易记录和明细

#### 样本内事件流水

{in_sample_event_table}

#### 样本内成交结果

{in_sample_trade_table}

#### 样本外事件流水

{validation_event_table}

#### 样本外成交结果

{validation_trade_table}

## 最终结论

- 样本外相对买入持有差额：`{float(validation_summary['StrategyVsBuyHold']):.2f}`。
- 样本外底仓浮动盈亏：`{float(validation_summary['BaseUnrealizedPnl']):.2f}`；网格浮动盈亏：`{float(validation_summary['GridUnrealizedPnl']):.2f}`。
- 样本外网格已实现利润：`{float(validation_summary['GridRealizedProfit']):.2f}`，网格买卖次数 `买 {int(validation_summary['GridBuyCount'])} / 卖 {int(validation_summary['GridSellCount'])}`。
- 这份报告只代表最近 60 天 `1m` 粒度下的结果，不等同于长期稳健结论；后续如果要提高可信度，应继续积累本地 1 分钟历史后重复验证。
"""
    report_path.write_text(report_content, encoding="utf-8")
    logger.info("指数 ETF 正式报告生成完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return report_path


def build_minute_report_markdown(
    workflow_result: dict[str, object],
    report_dir: str | Path = DEFAULT_MINUTE_REPORT_DIR,
) -> Path:
    """生成分钟线专用报告。"""
    strategy_kind = str(workflow_result["optimization"]["best_run"]["summary"].get("StrategyKind", "grid"))
    if strategy_kind == "minute_index_grid_retrace":
        return _build_index_grid_report_markdown(workflow_result, report_dir=report_dir)
    return build_report_markdown(workflow_result, report_dir=report_dir)


def plot_strategy_comparison(
    strategy_results: dict[str, dict[str, object]],
    output_path: str | Path,
    title: str,
) -> Path:
    """绘制多策略样本外净值对比。"""
    configure_matplotlib()
    figure, axis = plt.subplots(figsize=(14, 7))

    for strategy_kind, workflow_result in strategy_results.items():
        validation_run = workflow_result["validation"]["run"]
        summary = validation_run["summary"]
        curve = validation_run["equity_curve"].copy().reset_index()
        if curve.empty:
            continue
        date_column = curve.columns[0]
        curve.rename(columns={date_column: "Date"}, inplace=True)
        curve["Date"] = pd.to_datetime(curve["Date"])
        capital = float(summary.get("TotalCapital", 200000.0))
        curve["NetValue"] = curve["Equity"] / capital
        axis.plot(curve["Date"], curve["NetValue"], linewidth=1.6, label=_strategy_display_name(summary, strategy_kind))

    axis.set_title(title)
    axis.set_ylabel("净值")
    axis.set_xlabel("日期")
    axis.legend(loc="best")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return target


def _comparison_rows(strategy_results: dict[str, dict[str, object]]) -> list[list[object]]:
    rows: list[list[object]] = []
    for workflow_result in strategy_results.values():
        best_summary = workflow_result["optimization"]["best_run"]["summary"]
        validation_summary = workflow_result["validation"]["run"]["summary"]
        rows.append(
            [
                _strategy_display_name(best_summary),
                str(best_summary.get("StrategyKind", "grid")),
                f"{float(best_summary.get('NetReturnPct', best_summary.get('ReturnPct', 0.0))):.2f}%",
                f"{float(best_summary.get('MaxDrawdownPct', 0.0)):.2f}%",
                f"{float(validation_summary.get('NetReturnPct', validation_summary.get('ReturnPct', 0.0))):.2f}%",
                f"{float(validation_summary.get('MaxDrawdownPct', 0.0)):.2f}%",
                f"{float(validation_summary.get('TransactionCost', 0.0)):.2f}",
                f"{float(validation_summary.get('ClosedTrades', 0)):.0f}",
                _format_markdown_value(best_summary.get("TakeProfitPct", 0.0)),
            ]
        )
    return rows


def _pick_recommended_strategy(strategy_results: dict[str, dict[str, object]]) -> dict[str, object]:
    ranked = sorted(
        strategy_results.values(),
        key=lambda workflow_result: (
            float(workflow_result["validation"]["run"]["summary"].get("NetReturnPct", workflow_result["validation"]["run"]["summary"].get("ReturnPct", 0.0))),
            -float(workflow_result["validation"]["run"]["summary"].get("MaxDrawdownPct", 0.0)),
            float(workflow_result["optimization"]["best_run"]["summary"].get("RobustScore", workflow_result["optimization"]["best_run"]["summary"].get("Score", 0.0))),
        ),
        reverse=True,
    )
    return ranked[0]


def build_strategy_comparison_report(
    strategy_results: dict[str, dict[str, object]],
    interval: str,
    symbol: str,
    report_dir: str | Path,
) -> Path:
    """生成小米默认使用的多策略对比报告。"""
    started_at = perf_counter()
    target_dir = Path(report_dir)
    figure_dir = target_dir / "figures"
    target_dir.mkdir(parents=True, exist_ok=True)
    slug = _symbol_to_slug(symbol)
    interval_slug = interval if interval != "1d" else "daily"
    report_path = target_dir / f"{slug}_{interval_slug}_strategy_compare_report.md"
    comparison_chart = plot_strategy_comparison(
        strategy_results=strategy_results,
        output_path=figure_dir / f"{slug}_{interval_slug}_strategy_compare.png",
        title=f"{symbol} 多策略样本外净值对比",
    )

    recommended = _pick_recommended_strategy(strategy_results)
    recommended_best = recommended["optimization"]["best_run"]["summary"]
    recommended_validation = recommended["validation"]["run"]["summary"]
    quick_rows = _comparison_rows(strategy_results)
    quick_table = _build_simple_markdown_table(
        ["策略名称", "策略代码", "样本内净收益率", "样本内最大回撤", "样本外净收益率", "样本外最大回撤", "样本外手续费", "样本外成交笔数", "止盈参数(%)"],
        quick_rows,
    )

    recommended_text = (
        f"当前更推荐 `{_strategy_display_name(recommended_best)}`，"
        f"因为它在样本外给出了 `{float(recommended_validation.get('NetReturnPct', recommended_validation.get('ReturnPct', 0.0))):.2f}%` 的净收益率，"
        f"同时最大回撤控制在 `{float(recommended_validation.get('MaxDrawdownPct', 0.0)):.2f}%`。"
    )
    notes: list[str] = []
    for workflow_result in strategy_results.values():
        best_summary = workflow_result["optimization"]["best_run"]["summary"]
        validation_summary = workflow_result["validation"]["run"]["summary"]
        strategy_name = _strategy_display_name(best_summary)
        parameter_bits = []
        for key in [
            "rsi_window",
            "rsi_entry",
            "ma_window",
            "deviation_entry_pct",
            "lookback_bars",
            "drop_entry_pct",
            "stop_loss_atr",
            "stop_loss_pct",
            "max_hold_bars",
            "fade_filter_upper_shadow_pct",
            "fade_filter_block_bars",
            "investment_amount",
            "frequency",
            "day_rule",
            "max_position_ratio",
        ]:
            if key in best_summary:
                parameter_bits.append(f"{key}={best_summary[key]}")
        if not parameter_bits and float(best_summary.get("GridCount", 0)) > 0:
            parameter_bits = [
                f"grid_spacing={float(best_summary.get('GridSpacingPct', 0.0)):.2f}%",
                f"grid_count={int(best_summary.get('GridCount', 0))}",
                f"take_profit={float(best_summary.get('TakeProfitPct', 0.0)):.2f}%",
            ]
        notes.append(
            f"- `{strategy_name}`：样本内最优参数为 `{', '.join(parameter_bits)}`；样本外净收益率 `{float(validation_summary.get('NetReturnPct', validation_summary.get('ReturnPct', 0.0))):.2f}%`，最大回撤 `{float(validation_summary.get('MaxDrawdownPct', 0.0)):.2f}%`。"
        )

    report_content = "\n".join(
        [
            f"# {symbol} 多策略对比报告",
            "",
            "## 摘要",
            "",
            f"- 标的：`{symbol}`",
            f"- 周期：`{interval}`",
            f"- 策略集合：{', '.join(_strategy_display_name(workflow_result['optimization']['best_run']['summary'], key) for key, workflow_result in strategy_results.items())}",
            f"- 推荐结论：{recommended_text}",
            "- 报告重点回答：在左侧下跌、偶尔反抽和日内冲高回落的结构下，是否有比网格更契合的做多策略。",
            "",
            "## 第一层：先看结论",
            "",
            quick_table,
            "",
            f"- {recommended_text}",
            "- 如果样本外净收益接近，但新策略显著降低回撤，也视为比网格更契合当前结构。",
            "",
            "## 第二层：展开细节",
            "",
            "### 各策略样本外净值对比",
            "",
            f"![多策略样本外净值对比](figures/{comparison_chart.name})",
            "",
            "### 各策略参数与结论",
            "",
            *notes,
            "",
            "### 结果怎么读",
            "",
            "- 网格更依赖价格在下跌后进入震荡，已经落袋的闭环利润不代表总账户一定转正。",
            "- 日线超跌反弹更偏向少做、等极端价差后出手，适合减少左侧持续下跌中的反复接刀。",
            "- 分钟急跌反抽更偏向抓短促回补；叠加冲高回落过滤后，目标是减少日内追高后被砸回来的无效交易。",
            "",
            "## 最终结论",
            "",
            f"- 推荐策略：`{_strategy_display_name(recommended_best)}`。",
            f"- 推荐依据：样本外净收益率 `{float(recommended_validation.get('NetReturnPct', recommended_validation.get('ReturnPct', 0.0))):.2f}%`，最大回撤 `{float(recommended_validation.get('MaxDrawdownPct', 0.0)):.2f}%`。",
            "- 这份报告只基于仓库当前小米样本，不构成实盘建议；后续若扩到更多港股，应继续做跨标的稳健性检验。",
            "",
        ]
    )
    report_path.write_text(report_content, encoding="utf-8")
    logger.info("多策略对比报告生成完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return report_path
