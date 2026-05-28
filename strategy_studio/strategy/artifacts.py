from __future__ import annotations
"""回测输入加载和产物落盘。

策略执行只负责产生结构化结果；这里负责把 CSV 输入和明细输出集中处理。
"""

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from strategy_studio.strategy.sampling import DeclineWindow


def load_price_frame(data_path: str | Path) -> pd.DataFrame:
    """加载标准化 CSV 并转成 backtesting.py 需要的结构。"""
    frame = pd.read_csv(data_path, parse_dates=["Date"])
    required_columns = {"Date", "Open", "High", "Low", "Close", "Volume"}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(f"标准化 CSV 缺少字段: {sorted(missing_columns)}")

    frame = frame.sort_values("Date").set_index("Date")
    frame = frame.loc[:, ["Open", "High", "Low", "Close", "Volume"]]
    frame = frame.astype(
        {
            "Open": "float64",
            "High": "float64",
            "Low": "float64",
            "Close": "float64",
            "Volume": "int64",
        }
    )
    return frame


def save_run_artifacts(output_dir: str | Path, prefix: str, run_result: dict[str, object]) -> dict[str, Path]:
    """保存单次回测产生的明细文件。

    仅供离线 CLI 研究使用；平台 worker 会直接把结构化结果写入数据库。
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    summary_path = target_dir / f"{prefix}_summary.csv"
    history_path = target_dir / f"{prefix}_history.csv"
    events_path = target_dir / f"{prefix}_events.csv"
    trades_path = target_dir / f"{prefix}_trades.csv"
    equity_path = target_dir / f"{prefix}_equity_curve.csv"

    pd.DataFrame([run_result["summary"]]).to_csv(summary_path, index=False, encoding="utf-8-sig")
    run_result["history"].to_csv(history_path, index=False, encoding="utf-8-sig")
    run_result["events"].to_csv(events_path, index=False, encoding="utf-8-sig")
    run_result["trades"].to_csv(trades_path, index=False, encoding="utf-8-sig")
    run_result["equity_curve"].to_csv(equity_path, index=True, encoding="utf-8-sig")

    return {
        "summary": summary_path,
        "history": history_path,
        "events": events_path,
        "trades": trades_path,
        "equity_curve": equity_path,
    }


def save_decline_window(output_dir: str | Path, decline_window: DeclineWindow) -> Path:
    """保存样本内区间定位结果。

    仅供离线 CLI 研究使用；平台 worker 不再依赖本地窗口文件。
    """
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    window_path = target / "in_sample_window.csv"
    pd.DataFrame([asdict(decline_window)]).to_csv(window_path, index=False, encoding="utf-8-sig")
    return window_path
