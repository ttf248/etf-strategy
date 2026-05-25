from __future__ import annotations

"""策略参数模板服务。"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from etf_strategy.config import DEFAULT_MINUTE_INTERVAL
from etf_strategy.db.models import StrategyParameterTemplate
from etf_strategy.db.session import open_session
from etf_strategy.repositories.templates import (
    clear_default_template_flag,
    create_strategy_template,
    get_strategy_template,
    get_strategy_template_by_key,
    list_strategy_templates as list_strategy_templates_repo,
    update_strategy_template,
)
from etf_strategy.strategy.registry import (
    default_parameter_space_for_strategy,
    get_strategy_spec,
    normalize_parameter_space_for_strategy,
    validate_strategy_interval,
)
from etf_strategy.settings import (
    DAILY_GRID_COUNTS,
    DAILY_REBOUND_DEVIATIONS,
    DAILY_REBOUND_MA_WINDOWS,
    DAILY_REBOUND_MAX_HOLD_BARS,
    DAILY_REBOUND_RSI_ENTRIES,
    DAILY_REBOUND_RSI_WINDOWS,
    DAILY_REBOUND_STOP_LOSS_ATRS,
    DAILY_REBOUND_TAKE_PROFITS,
    DAILY_SPACINGS,
    DAILY_TAKE_PROFITS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_VALIDATION_RATIO,
    DEFAULT_VALIDATION_START,
    INTRADAY_GRID_COUNTS,
    INTRADAY_SPACINGS,
    INTRADAY_TAKE_PROFITS,
    MINUTE_REBOUND_DROP_ENTRIES,
    MINUTE_REBOUND_FADE_BLOCK_BARS,
    MINUTE_REBOUND_FADE_UPPER_SHADOWS,
    MINUTE_REBOUND_LOOKBACK_BARS,
    MINUTE_REBOUND_MAX_HOLD_BARS,
    MINUTE_REBOUND_RSI_ENTRIES,
    MINUTE_REBOUND_STOP_LOSSES,
    MINUTE_REBOUND_TAKE_PROFITS,
    StrategyKind,
    default_execution_config,
)


DEFAULT_TEMPLATE_EXECUTION_PROFILE = "realistic"
DEFAULT_TEMPLATE_JOBS = 1
GRID_PARAMETER_KEYS = ("spacings", "grid_counts", "take_profits")
DAILY_REBOUND_PARAMETER_KEYS = (
    "rsi_window",
    "rsi_entry",
    "ma_window",
    "deviation_entry_pct",
    "take_profit_pct",
    "stop_loss_atr",
    "max_hold_bars",
)
MINUTE_REBOUND_PARAMETER_KEYS = (
    "lookback_bars",
    "drop_entry_pct",
    "rsi_entry",
    "take_profit_pct",
    "stop_loss_pct",
    "max_hold_bars",
)
FADE_FILTER_PARAMETER_KEYS = ("fade_filter_upper_shadow_pct", "fade_filter_block_bars")
EXECUTION_OVERRIDE_KEYS = (
    "commission_bps",
    "slippage_bps",
    "max_position_ratio",
    "stop_loss_pct",
    "cooldown_bars",
    "benchmark",
    "left_side_policy",
    "force_exit_loss_pct",
)


@dataclass(frozen=True)
class TemplateSeed:
    template_key: str
    template_name: str
    strategy_kind: str
    interval: str
    execution_profile: str
    validation_start: str
    lookback_days: int | None
    validation_ratio: float | None
    jobs: int
    execution_overrides_json: dict[str, object]
    parameter_space_json: dict[str, object]
    description: str
    is_active: bool = True
    is_default: bool = True


def _validate_strategy_interval(strategy_kind: str, interval: str) -> None:
    validate_strategy_interval(strategy_kind, interval)


def _normalize_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串。")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空。")
    return normalized


def _normalize_numeric_list(value: object, field_name: str, item_type: type[int] | type[float]) -> list[int] | list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} 必须是非空数组。")
    normalized: list[int] | list[float] = []
    for item in value:
        if item_type is int:
            normalized.append(int(item))
        else:
            normalized.append(float(item))
    return normalized


def _default_execution_overrides(profile: str) -> dict[str, object]:
    execution = default_execution_config(profile=profile)
    return {
        "commission_bps": execution.commission_bps,
        "slippage_bps": execution.slippage_bps,
        "max_position_ratio": execution.max_position_ratio,
        "stop_loss_pct": execution.stop_loss_pct,
        "cooldown_bars": execution.cooldown_bars,
        "benchmark": execution.benchmark,
        "left_side_policy": execution.left_side_policy,
        "force_exit_loss_pct": execution.force_exit_loss_pct,
    }


def default_parameter_space_for_template(strategy_kind: str, interval: str) -> dict[str, object]:
    return default_parameter_space_for_strategy(strategy_kind, interval)


def normalize_parameter_space(strategy_kind: str, parameter_space: dict[str, object] | None, interval: str) -> dict[str, object] | None:
    return normalize_parameter_space_for_strategy(strategy_kind, parameter_space, interval)


def normalize_execution_overrides(value: dict[str, object] | None, profile: str) -> dict[str, object]:
    base = _default_execution_overrides(profile)
    if value is None:
        return base
    if not isinstance(value, dict):
        raise ValueError("execution_overrides_json 必须是对象。")
    normalized = dict(base)
    for key in EXECUTION_OVERRIDE_KEYS:
        if key not in value or value[key] is None:
            continue
        if key in {"cooldown_bars"}:
            normalized[key] = int(value[key])
        elif key in {"benchmark", "left_side_policy"}:
            normalized[key] = str(value[key])
        else:
            normalized[key] = float(value[key])
    return normalized


def _template_to_dict(template: StrategyParameterTemplate) -> dict[str, object]:
    return {
        "id": template.id,
        "template_key": template.template_key,
        "template_name": template.template_name,
        "strategy_kind": template.strategy_kind,
        "interval": template.interval,
        "execution_profile": template.execution_profile,
        "validation_start": template.validation_start,
        "lookback_days": template.lookback_days,
        "validation_ratio": template.validation_ratio,
        "jobs": template.jobs,
        "execution_overrides_json": template.execution_overrides_json,
        "parameter_space_json": template.parameter_space_json,
        "description": template.description,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "created_at": template.created_at.isoformat(sep=" "),
        "updated_at": template.updated_at.isoformat(sep=" "),
    }


def _normalize_template_payload(
    payload: dict[str, object],
    existing: StrategyParameterTemplate | None = None,
) -> dict[str, object]:
    template_key = _normalize_string(payload.get("template_key") or (existing.template_key if existing else None), "template_key")
    template_name = _normalize_string(payload.get("template_name") or (existing.template_name if existing else None), "template_name")
    strategy_kind = _normalize_string(payload.get("strategy_kind") or (existing.strategy_kind if existing else None), "strategy_kind")
    interval = _normalize_string(payload.get("interval") or (existing.interval if existing else None), "interval")
    _validate_strategy_interval(strategy_kind, interval)

    execution_profile = str(payload.get("execution_profile") or (existing.execution_profile if existing else DEFAULT_TEMPLATE_EXECUTION_PROFILE))
    validation_start = str(payload.get("validation_start") if "validation_start" in payload else (existing.validation_start if existing else DEFAULT_VALIDATION_START))
    lookback_days_raw = payload.get("lookback_days") if "lookback_days" in payload else (existing.lookback_days if existing else DEFAULT_LOOKBACK_DAYS)
    validation_ratio_raw = payload.get("validation_ratio") if "validation_ratio" in payload else (existing.validation_ratio if existing else DEFAULT_VALIDATION_RATIO)
    jobs_raw = payload.get("jobs") if "jobs" in payload else (existing.jobs if existing else DEFAULT_TEMPLATE_JOBS)
    execution_overrides = normalize_execution_overrides(
        payload.get("execution_overrides_json") if "execution_overrides_json" in payload else (existing.execution_overrides_json if existing else None),
        execution_profile,
    )
    parameter_space = normalize_parameter_space(
        strategy_kind,
        payload.get("parameter_space_json") if "parameter_space_json" in payload else (existing.parameter_space_json if existing else None),
        interval,
    )
    if parameter_space is None:
        parameter_space = default_parameter_space_for_template(strategy_kind, interval)

    lookback_days = int(lookback_days_raw) if lookback_days_raw is not None else None
    validation_ratio = float(validation_ratio_raw) if validation_ratio_raw is not None else None
    jobs = int(jobs_raw) if jobs_raw is not None else DEFAULT_TEMPLATE_JOBS
    if jobs <= 0:
        raise ValueError("jobs 必须是正整数。")

    description = str(payload.get("description") if "description" in payload else (existing.description if existing else ""))
    is_active = bool(payload.get("is_active") if "is_active" in payload else (existing.is_active if existing else True))
    is_default = bool(payload.get("is_default") if "is_default" in payload else (existing.is_default if existing else False))

    if interval == "1d":
        validation_ratio = None
        if lookback_days is None:
            lookback_days = DEFAULT_LOOKBACK_DAYS
    else:
        validation_start = ""
        lookback_days = None
        if validation_ratio is None:
            validation_ratio = DEFAULT_VALIDATION_RATIO

    return {
        "template_key": template_key,
        "template_name": template_name,
        "strategy_kind": strategy_kind,
        "interval": interval,
        "execution_profile": execution_profile,
        "validation_start": validation_start,
        "lookback_days": lookback_days,
        "validation_ratio": validation_ratio,
        "jobs": jobs,
        "execution_overrides_json": execution_overrides,
        "parameter_space_json": parameter_space,
        "description": description,
        "is_active": is_active,
        "is_default": is_default,
    }


def build_seed_templates() -> list[TemplateSeed]:
    base_execution = _default_execution_overrides("realistic")
    return [
        TemplateSeed(
            template_key="grid_daily_realistic_default",
            template_name="网格-日线实盘口径默认模板",
            strategy_kind="grid",
            interval="1d",
            execution_profile="realistic",
            validation_start=DEFAULT_VALIDATION_START,
            lookback_days=DEFAULT_LOOKBACK_DAYS,
            validation_ratio=None,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("grid", "1d"),
            description="日线网格的默认平台模板。",
        ),
        TemplateSeed(
            template_key="grid_15m_realistic_default",
            template_name="网格-15m 实盘口径默认模板",
            strategy_kind="grid",
            interval="15m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=DEFAULT_VALIDATION_RATIO,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("grid", "15m"),
            description="15 分钟网格的默认平台模板。",
        ),
        TemplateSeed(
            template_key="grid_1m_realistic_default",
            template_name="网格-1m 实盘口径默认模板",
            strategy_kind="grid",
            interval="1m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=DEFAULT_VALIDATION_RATIO,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("grid", "1m"),
            description="1 分钟网格的默认平台模板。",
        ),
        TemplateSeed(
            template_key="dca_daily_realistic_default",
            template_name="定投-日线实盘口径默认模板",
            strategy_kind="dca",
            interval="1d",
            execution_profile="realistic",
            validation_start=DEFAULT_VALIDATION_START,
            lookback_days=DEFAULT_LOOKBACK_DAYS,
            validation_ratio=None,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("dca", "1d"),
            description="按交易周期固定金额买入的日线定投默认模板。",
        ),
        TemplateSeed(
            template_key="daily_rebound_1d_realistic_default",
            template_name="日线超跌反弹-默认模板",
            strategy_kind="daily_rebound",
            interval="1d",
            execution_profile="realistic",
            validation_start=DEFAULT_VALIDATION_START,
            lookback_days=DEFAULT_LOOKBACK_DAYS,
            validation_ratio=None,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("daily_rebound", "1d"),
            description="日线超跌反弹的默认平台模板。",
        ),
        TemplateSeed(
            template_key="minute_rebound_15m_realistic_default",
            template_name="分钟急跌反抽-15m 默认模板",
            strategy_kind="minute_rebound",
            interval="15m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=DEFAULT_VALIDATION_RATIO,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("minute_rebound", "15m"),
            description="15 分钟分钟急跌反抽默认模板。",
        ),
        TemplateSeed(
            template_key="minute_rebound_1m_realistic_default",
            template_name="分钟急跌反抽-1m 默认模板",
            strategy_kind="minute_rebound",
            interval="1m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=DEFAULT_VALIDATION_RATIO,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("minute_rebound", "1m"),
            description="1 分钟分钟急跌反抽默认模板。",
        ),
        TemplateSeed(
            template_key="minute_rebound_fade_15m_realistic_default",
            template_name="分钟反抽+冲高回落过滤-15m 默认模板",
            strategy_kind="minute_rebound_with_fade_filter",
            interval="15m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=DEFAULT_VALIDATION_RATIO,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("minute_rebound_with_fade_filter", "15m"),
            description="15 分钟反抽过滤策略默认模板。",
        ),
        TemplateSeed(
            template_key="minute_rebound_fade_1m_realistic_default",
            template_name="分钟反抽+冲高回落过滤-1m 默认模板",
            strategy_kind="minute_rebound_with_fade_filter",
            interval="1m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=DEFAULT_VALIDATION_RATIO,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json=default_parameter_space_for_template("minute_rebound_with_fade_filter", "1m"),
            description="1 分钟反抽过滤策略默认模板。",
        ),
        TemplateSeed(
            template_key="minute_index_grid_retrace_1m_realistic_default",
            template_name="指数回落反弹网格-1m 默认模板",
            strategy_kind="minute_index_grid_retrace",
            interval="1m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=DEFAULT_VALIDATION_RATIO,
            jobs=1,
            execution_overrides_json=base_execution,
            parameter_space_json={},
            description="指数回落反弹网格的默认平台模板。",
        ),
    ]


def seed_strategy_templates(session: Session | None = None) -> int:
    owns_session = session is None
    created_or_updated = 0
    managed_session = session or open_session()
    try:
        for seed in build_seed_templates():
            payload = asdict(seed)
            existing = get_strategy_template_by_key(managed_session, seed.template_key)
            if payload["is_default"]:
                clear_default_template_flag(managed_session, seed.strategy_kind, seed.interval, exclude_id=existing.id if existing else None)
            if existing is None:
                create_strategy_template(managed_session, payload)
            else:
                update_strategy_template(managed_session, existing, payload)
            created_or_updated += 1
        if owns_session:
            managed_session.commit()
        return created_or_updated
    except Exception:
        if owns_session:
            managed_session.rollback()
        raise
    finally:
        if owns_session:
            managed_session.close()


def list_strategy_templates(
    strategy_kind: str | None = None,
    interval: str | None = None,
    active_only: bool = False,
) -> list[dict[str, object]]:
    with open_session() as session:
        templates = list_strategy_templates_repo(session, strategy_kind=strategy_kind, interval=interval, active_only=active_only)
        return [_template_to_dict(item) for item in templates]


def get_strategy_template_detail(template_id: int) -> dict[str, object] | None:
    with open_session() as session:
        template = get_strategy_template(session, template_id)
        if template is None:
            return None
        return _template_to_dict(template)


def create_strategy_template_entry(payload: dict[str, object]) -> dict[str, object]:
    with open_session() as session:
        normalized = _normalize_template_payload(payload)
        existing = get_strategy_template_by_key(session, normalized["template_key"])
        if existing is not None:
            raise ValueError(f"模板键已存在: {normalized['template_key']}")
        if normalized["is_default"]:
            clear_default_template_flag(session, normalized["strategy_kind"], normalized["interval"])
        template = create_strategy_template(session, normalized)
        session.commit()
        return _template_to_dict(template)


def update_strategy_template_entry(template_id: int, payload: dict[str, object]) -> dict[str, object]:
    with open_session() as session:
        template = get_strategy_template(session, template_id)
        if template is None:
            raise ValueError("模板不存在。")
        normalized = _normalize_template_payload(payload, existing=template)
        duplicate = get_strategy_template_by_key(session, normalized["template_key"])
        if duplicate is not None and duplicate.id != template_id:
            raise ValueError(f"模板键已存在: {normalized['template_key']}")
        if normalized["is_default"]:
            clear_default_template_flag(session, normalized["strategy_kind"], normalized["interval"], exclude_id=template_id)
        template = update_strategy_template(session, template, normalized)
        session.commit()
        return _template_to_dict(template)


def _template_snapshot(template: StrategyParameterTemplate) -> dict[str, object]:
    return {
        "id": template.id,
        "template_key": template.template_key,
        "template_name": template.template_name,
        "strategy_kind": template.strategy_kind,
        "interval": template.interval,
        "execution_profile": template.execution_profile,
        "is_default": template.is_default,
    }


def resolve_backtest_request_payload(request: Any, session: Session) -> dict[str, object]:
    template = None
    if getattr(request, "template_id", None) is not None:
        template = get_strategy_template(session, int(request.template_id))
        if template is None:
            raise ValueError("所选模板不存在。")
        if not template.is_active:
            raise ValueError("所选模板已停用，无法提交新任务。")

    symbol = _normalize_string(getattr(request, "symbol", None), "symbol").upper()
    interval = str(getattr(request, "interval", None) or (template.interval if template else DEFAULT_MINUTE_INTERVAL))
    strategy_kind = str(getattr(request, "strategy_kind", None) or (template.strategy_kind if template else "grid"))
    _validate_strategy_interval(strategy_kind, interval)

    execution_profile = str(getattr(request, "execution_profile", None) or (template.execution_profile if template else DEFAULT_TEMPLATE_EXECUTION_PROFILE))
    template_execution = template.execution_overrides_json if template else {}
    execution_overrides = {
        key: getattr(request, key, None) if getattr(request, key, None) is not None else template_execution.get(key)
        for key in EXECUTION_OVERRIDE_KEYS
    }
    parameter_space = normalize_parameter_space(
        strategy_kind,
        getattr(request, "parameter_space", None) if getattr(request, "parameter_space", None) is not None else (template.parameter_space_json if template else None),
        interval,
    )

    merged = {
        "symbol": symbol,
        "interval": interval,
        "strategy_kind": strategy_kind,
        "validation_start": getattr(request, "validation_start", None) or (template.validation_start if template else DEFAULT_VALIDATION_START),
        "lookback_days": int(getattr(request, "lookback_days", None) or (template.lookback_days if template and template.lookback_days is not None else DEFAULT_LOOKBACK_DAYS)),
        "validation_ratio": float(
            getattr(request, "validation_ratio", None)
            if getattr(request, "validation_ratio", None) is not None
            else (template.validation_ratio if template and template.validation_ratio is not None else DEFAULT_VALIDATION_RATIO)
        ),
        "execution_profile": execution_profile,
        "commission_bps": execution_overrides["commission_bps"],
        "slippage_bps": execution_overrides["slippage_bps"],
        "max_position_ratio": execution_overrides["max_position_ratio"],
        "stop_loss_pct": execution_overrides["stop_loss_pct"],
        "cooldown_bars": execution_overrides["cooldown_bars"],
        "benchmark": execution_overrides["benchmark"],
        "left_side_policy": execution_overrides["left_side_policy"],
        "force_exit_loss_pct": execution_overrides["force_exit_loss_pct"],
        "jobs": int(getattr(request, "jobs", None) or (template.jobs if template else DEFAULT_TEMPLATE_JOBS)),
        "template_id": template.id if template else None,
        "template_snapshot": _template_snapshot(template) if template else None,
        "parameter_space": parameter_space,
    }
    if merged["jobs"] <= 0:
        raise ValueError("jobs 必须是正整数。")
    if interval != "1d":
        merged["validation_start"] = ""
        merged["lookback_days"] = DEFAULT_LOOKBACK_DAYS
    return merged
