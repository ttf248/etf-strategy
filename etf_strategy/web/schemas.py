from __future__ import annotations

"""FastAPI 请求模型。"""

from pydantic import BaseModel, Field


class BacktestRequestModel(BaseModel):
    symbol: str = Field(..., description="Yahoo 标的代码")
    interval: str = Field(default="15m")
    strategy_kind: str = Field(default="grid")
    validation_start: str = Field(default="2026-01-01")
    lookback_days: int = Field(default=120, ge=1)
    validation_ratio: float = Field(default=0.25, gt=0, lt=1)
    execution_profile: str = Field(default="realistic")
    commission_bps: float | None = None
    slippage_bps: float | None = None
    max_position_ratio: float | None = None
    stop_loss_pct: float | None = None
    cooldown_bars: int | None = None
    benchmark: str | None = None
    left_side_policy: str | None = None
    force_exit_loss_pct: float | None = None
    jobs: int = Field(default=1, ge=1)


class SyncRequestModel(BaseModel):
    symbol: str | None = None
    interval: str = Field(default="1d")
    proxy: str | None = None
    period: str | None = None

