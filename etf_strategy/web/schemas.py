from __future__ import annotations

"""FastAPI 请求模型。"""

from pydantic import BaseModel, Field


class BacktestRequestModel(BaseModel):
    symbol: str = Field(..., description="Yahoo 标的代码")
    interval: str | None = Field(default=None)
    strategy_kind: str | None = Field(default=None)
    validation_start: str | None = Field(default=None)
    lookback_days: int | None = Field(default=None, ge=1)
    validation_ratio: float | None = Field(default=None, gt=0, lt=1)
    execution_profile: str | None = Field(default=None)
    commission_bps: float | None = None
    slippage_bps: float | None = None
    max_position_ratio: float | None = None
    stop_loss_pct: float | None = None
    cooldown_bars: int | None = None
    benchmark: str | None = None
    left_side_policy: str | None = None
    force_exit_loss_pct: float | None = None
    jobs: int | None = Field(default=None, ge=1)
    template_id: int | None = None
    parameter_space: dict[str, object] | None = None


class StrategyTemplateCreateModel(BaseModel):
    template_key: str
    template_name: str
    strategy_kind: str
    interval: str
    execution_profile: str = Field(default="realistic")
    validation_start: str | None = None
    lookback_days: int | None = Field(default=None, ge=1)
    validation_ratio: float | None = Field(default=None, gt=0, lt=1)
    jobs: int = Field(default=1, ge=1)
    execution_overrides_json: dict[str, object] | None = None
    parameter_space_json: dict[str, object] | None = None
    description: str = ""
    is_active: bool = True
    is_default: bool = False


class StrategyTemplateUpdateModel(BaseModel):
    template_key: str | None = None
    template_name: str | None = None
    strategy_kind: str | None = None
    interval: str | None = None
    execution_profile: str | None = None
    validation_start: str | None = None
    lookback_days: int | None = Field(default=None, ge=1)
    validation_ratio: float | None = Field(default=None, gt=0, lt=1)
    jobs: int | None = Field(default=None, ge=1)
    execution_overrides_json: dict[str, object] | None = None
    parameter_space_json: dict[str, object] | None = None
    description: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class SyncRequestModel(BaseModel):
    symbol: str | None = None
    interval: str = Field(default="1d")
    proxy: str | None = None
    period: str | None = None


class BacktestBulkActionModel(BaseModel):
    job_ids: list[int] = Field(default_factory=list)
