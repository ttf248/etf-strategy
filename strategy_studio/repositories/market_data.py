from __future__ import annotations

"""行情仓储。"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy import BOOLEAN, Select, func, literal_column, select
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from strategy_studio.db.models import (
    CorporateActionEvent,
    DataIngestionJob,
    DataIngestionJobItem,
    DataProvider,
    DataSyncRun,
    DataSyncRunItem,
    Instrument,
    InstrumentAlias,
    MarketDataBar,
    MarketDataSeries,
    PriceBar,
    PriceAdjustmentSegment,
    SourceFileManifest,
    utc_now,
)


def _format_timestamp(value: datetime | None) -> str:
    return value.isoformat(sep=" ") if value else ""


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    if isinstance(parsed, pd.Timestamp):
        return parsed.to_pydatetime()
    return None


def _normalize_string_list(values: object) -> list[str]:
    if not values:
        return []
    return sorted({str(item) for item in values if str(item or "").strip()})


def _safe_int(value: object) -> int:
    return int(value or 0)


def _safe_text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class BacktestPriceFrameSnapshot:
    """回测读取层返回的统一载体。"""

    frame: pd.DataFrame
    source_label: str
    source_kind: str
    provider_key: str
    adjustment_kind: str
    series_id: int | None


def _build_series_metadata_summary(metadata_json: dict[str, object] | None) -> dict[str, object]:
    metadata = dict(metadata_json or {})
    return {
        "source_period": _safe_text(metadata.get("period")),
        "source_file": _safe_text(metadata.get("source_file")),
        "raw_provider_key": _safe_text(metadata.get("raw_provider_key")),
        "raw_series_id": _safe_int(metadata.get("raw_series_id")) or None,
        "action_provider_key": _safe_text(metadata.get("action_provider_key")),
        "raw_frame_digest": _safe_text(metadata.get("raw_frame_digest")),
        "segment_frame_digest": _safe_text(metadata.get("segment_frame_digest")),
        "adjusted_frame_digest": _safe_text(metadata.get("adjusted_frame_digest")),
    }


def _build_qfq_series_diagnostics(
    *,
    series_rows: list[dict[str, object]],
    action_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    raw_series_by_id = {
        _safe_int(row.get("series_id")): row
        for row in series_rows
        if _safe_text(row.get("provider_key")) == "tdx"
    }
    latest_action_updated_at_by_provider: dict[str, datetime | None] = {}
    latest_action_updated_text_by_provider: dict[str, str] = {}
    for row in action_rows:
        provider_key = _safe_text(row.get("provider_key"))
        if not provider_key:
            continue
        updated_at_text = _safe_text(row.get("updated_at"))
        updated_at = _parse_timestamp(updated_at_text)
        current_latest = latest_action_updated_at_by_provider.get(provider_key)
        if updated_at is None and provider_key in latest_action_updated_at_by_provider:
            continue
        if current_latest is None or (updated_at is not None and updated_at > current_latest):
            latest_action_updated_at_by_provider[provider_key] = updated_at
            latest_action_updated_text_by_provider[provider_key] = updated_at_text

    diagnostics: list[dict[str, object]] = []
    for row in series_rows:
        if _safe_text(row.get("provider_key")) != "tdx_qfq":
            continue
        metadata_summary = dict(row.get("metadata_summary") or {})
        raw_provider_key = _safe_text(metadata_summary.get("raw_provider_key"))
        raw_series_id = _safe_int(metadata_summary.get("raw_series_id")) or None
        action_provider_key = _safe_text(metadata_summary.get("action_provider_key"))
        raw_series = raw_series_by_id.get(raw_series_id or 0)
        qfq_last_ingested_at = _safe_text(row.get("last_ingested_at"))
        raw_last_ingested_at = _safe_text(raw_series.get("last_ingested_at")) if raw_series else ""
        qfq_last_ingested_dt = _parse_timestamp(qfq_last_ingested_at)
        raw_last_ingested_dt = _parse_timestamp(raw_last_ingested_at)
        latest_action_updated_at = latest_action_updated_at_by_provider.get(action_provider_key)
        latest_action_updated_text = latest_action_updated_text_by_provider.get(action_provider_key, "")
        force_skip_cache_ready = all(
            _safe_text(metadata_summary.get(key))
            for key in ("raw_frame_digest", "segment_frame_digest", "adjusted_frame_digest")
        )
        normal_skip_reasons: list[str] = []
        if not raw_provider_key:
            normal_skip_reasons.append("缺少原始 provider 元数据")
        if raw_series_id is None:
            normal_skip_reasons.append("缺少原始序列引用")
        if raw_series is None:
            normal_skip_reasons.append("当前诊断窗口未找到对应原始序列")
        if not action_provider_key:
            normal_skip_reasons.append("缺少公司行动 provider 元数据")
        if qfq_last_ingested_dt is None:
            normal_skip_reasons.append("前复权序列还没有入库时间")
        if raw_last_ingested_dt is None:
            normal_skip_reasons.append("原始序列还没有入库时间")
        if (
            qfq_last_ingested_dt is not None
            and raw_last_ingested_dt is not None
            and raw_last_ingested_dt > qfq_last_ingested_dt
        ):
            normal_skip_reasons.append("原始序列比前复权序列更新")
        if (
            qfq_last_ingested_dt is not None
            and latest_action_updated_at is not None
            and latest_action_updated_at > qfq_last_ingested_dt
        ):
            normal_skip_reasons.append("公司行动事件比前复权序列更新")
        normal_skip_ready = not normal_skip_reasons
        force_skip_reasons: list[str] = []
        if not _safe_text(metadata_summary.get("raw_frame_digest")):
            force_skip_reasons.append("缺少原始摘要")
        if not _safe_text(metadata_summary.get("segment_frame_digest")):
            force_skip_reasons.append("缺少区间摘要")
        if not _safe_text(metadata_summary.get("adjusted_frame_digest")):
            force_skip_reasons.append("缺少前复权摘要")
        diagnostics.append(
            {
                "series_id": _safe_int(row.get("series_id")),
                "instrument_symbol": _safe_text(row.get("instrument_symbol")),
                "interval": _safe_text(row.get("interval")),
                "adjustment_kind": _safe_text(row.get("adjustment_kind")),
                "qfq_last_ingested_at": qfq_last_ingested_at,
                "raw_provider_key": raw_provider_key,
                "raw_series_id": raw_series_id,
                "raw_series_found": raw_series is not None,
                "raw_last_ingested_at": raw_last_ingested_at,
                "action_provider_key": action_provider_key,
                "latest_action_updated_at": latest_action_updated_text,
                "normal_skip_ready": normal_skip_ready,
                "normal_skip_reasons": normal_skip_reasons,
                "force_skip_cache_ready": force_skip_cache_ready,
                "force_skip_reasons": force_skip_reasons,
                "raw_frame_digest": _safe_text(metadata_summary.get("raw_frame_digest")),
                "segment_frame_digest": _safe_text(metadata_summary.get("segment_frame_digest")),
                "adjusted_frame_digest": _safe_text(metadata_summary.get("adjusted_frame_digest")),
            }
        )
    return diagnostics


def _infer_exchange(symbol: str) -> str:
    if "." in symbol:
        suffix = symbol.rsplit(".", maxsplit=1)[-1].upper()
        if suffix:
            return suffix
    return "US"


def _normalize_backtest_provider_key(value: str | None) -> str | None:
    normalized = _safe_text(value).lower()
    return normalized or None


def _normalize_backtest_adjustment_kind(value: str | None) -> str | None:
    normalized = _safe_text(value).lower()
    return normalized or None


def _default_adjustment_kind_for_provider(provider_key: str | None) -> str | None:
    if provider_key == "tdx_qfq":
        return "qfq"
    if provider_key in {"yahoo", "tdx"}:
        return "raw"
    return None


def _chunked(values: list[datetime], size: int = 5000) -> Iterable[list[datetime]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def get_instrument_by_symbol(session: Session, symbol: str) -> Instrument | None:
    return session.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))


def get_data_provider_by_key(session: Session, provider_key: str) -> DataProvider | None:
    return session.scalar(select(DataProvider).where(DataProvider.provider_key == provider_key))


def ensure_data_provider(
    session: Session,
    provider_key: str,
    provider_name: str,
    *,
    provider_type: str = "market_data",
    transport: str = "api",
    timezone: str = "UTC",
    config_json: dict[str, object] | None = None,
    status: str = "active",
) -> DataProvider:
    provider = get_data_provider_by_key(session, provider_key)
    if provider is not None:
        provider.provider_name = provider_name
        provider.provider_type = provider_type
        provider.transport = transport
        provider.timezone = timezone
        provider.status = status
        if config_json:
            provider.config_json = {**provider.config_json, **config_json}
        return provider

    provider = DataProvider(
        provider_key=provider_key,
        provider_name=provider_name,
        provider_type=provider_type,
        transport=transport,
        timezone=timezone,
        status=status,
        config_json=config_json or {},
    )
    session.add(provider)
    session.flush()
    return provider


def get_or_create_instrument(
    session: Session,
    symbol: str,
    name: str | None = None,
    asset_type: str = "equity",
    timezone: str = "UTC",
) -> Instrument:
    normalized = symbol.strip().upper()
    instrument = get_instrument_by_symbol(session, normalized)
    if instrument is not None:
        if name and instrument.name != name:
            instrument.name = name
        if instrument.asset_type != asset_type:
            instrument.asset_type = asset_type
        if instrument.timezone != timezone:
            instrument.timezone = timezone
        return instrument

    instrument = Instrument(
        symbol=normalized,
        exchange=_infer_exchange(normalized),
        asset_type=asset_type,
        name=name or normalized,
        timezone=timezone,
        is_active=True,
    )
    session.add(instrument)
    session.flush()
    return instrument


def get_or_create_instrument_alias(
    session: Session,
    instrument: Instrument,
    provider: DataProvider,
    source_symbol: str,
    *,
    source_name: str = "",
    market: str = "",
    exchange: str = "",
    security_type: str = "equity",
    currency: str = "",
    timezone: str = "UTC",
) -> InstrumentAlias:
    normalized = source_symbol.strip().upper()
    alias = session.scalar(
        select(InstrumentAlias).where(
            InstrumentAlias.provider_id == provider.id,
            InstrumentAlias.source_symbol == normalized,
        )
    )
    if alias is not None:
        alias.instrument_id = instrument.id
        alias.source_name = source_name or alias.source_name
        alias.market = market or alias.market
        alias.exchange = exchange or alias.exchange
        alias.security_type = security_type
        alias.currency = currency or alias.currency
        alias.timezone = timezone
        alias.is_primary = True
        return alias

    alias = InstrumentAlias(
        instrument_id=instrument.id,
        provider_id=provider.id,
        source_symbol=normalized,
        source_name=source_name or normalized,
        market=market,
        exchange=exchange,
        security_type=security_type,
        currency=currency,
        timezone=timezone,
        is_primary=True,
    )
    session.add(alias)
    session.flush()
    return alias


def get_or_create_market_data_series(
    session: Session,
    instrument: Instrument,
    provider: DataProvider,
    alias: InstrumentAlias,
    *,
    interval: str,
    market: str = "",
    exchange: str = "",
    adjustment_kind: str = "raw",
    session_type: str = "regular",
    price_type: str = "trade",
    bar_type: str = "time",
    currency: str = "",
    timezone: str = "UTC",
) -> MarketDataSeries:
    series = session.scalar(
        select(MarketDataSeries).where(
            MarketDataSeries.provider_id == provider.id,
            MarketDataSeries.alias_id == alias.id,
            MarketDataSeries.interval == interval,
            MarketDataSeries.adjustment_kind == adjustment_kind,
            MarketDataSeries.session_type == session_type,
            MarketDataSeries.price_type == price_type,
        )
    )
    if series is not None:
        series.instrument_id = instrument.id
        series.market = market or series.market
        series.exchange = exchange or series.exchange
        series.bar_type = bar_type
        series.currency = currency or series.currency
        series.timezone = timezone
        series.is_active = True
        return series

    series = MarketDataSeries(
        instrument_id=instrument.id,
        provider_id=provider.id,
        alias_id=alias.id,
        market=market,
        exchange=exchange,
        interval=interval,
        adjustment_kind=adjustment_kind,
        session_type=session_type,
        price_type=price_type,
        bar_type=bar_type,
        currency=currency,
        timezone=timezone,
        is_active=True,
    )
    session.add(series)
    session.flush()
    return series


def upsert_price_frame(
    session: Session,
    instrument: Instrument,
    interval: str,
    frame: pd.DataFrame,
    source: str = "yahoo",
) -> tuple[int, int]:
    """批量写入 K 线并返回新增/覆盖条数。"""
    if frame.empty:
        return 0, 0

    normalized = frame.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"]).dt.tz_localize(None)
    timestamps = [item.to_pydatetime() for item in normalized["Date"].tolist()]
    existing: set[datetime] = set()
    for batch in _chunked(timestamps):
        rows = session.scalars(
            select(PriceBar.bar_time).where(
                PriceBar.instrument_id == instrument.id,
                PriceBar.interval == interval,
                PriceBar.bar_time.in_(batch),
            )
        )
        existing.update(rows)

    all_rows = [
        {
            "instrument_id": instrument.id,
            "interval": interval,
            "bar_time": item["Date"].to_pydatetime() if hasattr(item["Date"], "to_pydatetime") else item["Date"],
            "open": float(item["Open"]),
            "high": float(item["High"]),
            "low": float(item["Low"]),
            "close": float(item["Close"]),
            "adj_close": float(item["Close"]),
            "volume": int(item["Volume"]),
            "source": source,
        }
        for item in normalized.to_dict(orient="records")
    ]
    for row_batch in _chunked(all_rows, size=1500):
        statement = insert(PriceBar).values(row_batch)
        update_columns = {
            "open": statement.excluded.open,
            "high": statement.excluded.high,
            "low": statement.excluded.low,
            "close": statement.excluded.close,
            "adj_close": statement.excluded.adj_close,
            "volume": statement.excluded.volume,
            "source": statement.excluded.source,
            "ingested_at": func.now(),
        }
        session.execute(
            statement.on_conflict_do_update(
                constraint="uq_price_bars_instrument_interval_time",
                set_=update_columns,
            )
        )
    updated_count = len(existing)
    inserted_count = len(all_rows) - updated_count
    return inserted_count, updated_count


def upsert_market_data_frame(
    session: Session,
    series: MarketDataSeries,
    frame: pd.DataFrame,
) -> tuple[int, int]:
    """把标准化 OHLCV 写入统一 K 线事实表。"""
    if frame.empty:
        return 0, 0

    normalized = frame.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"]).dt.tz_localize(None)
    timestamps = [item.to_pydatetime() for item in normalized["Date"].tolist()]
    all_rows = [
        {
            "series_id": series.id,
            "bar_time": item["Date"].to_pydatetime() if hasattr(item["Date"], "to_pydatetime") else item["Date"],
            "open": float(item["Open"]),
            "high": float(item["High"]),
            "low": float(item["Low"]),
            "close": float(item["Close"]),
            "adj_close": float(item["Close"]),
            "volume": int(item["Volume"]),
            "turnover_amount": float(item["Amount"]) if "Amount" in item and item["Amount"] is not None else None,
            "data_status": "ready",
            "payload_json": {},
        }
        for item in normalized.to_dict(orient="records")
    ]
    inserted_count = 0
    updated_count = 0
    for row_batch in _chunked(all_rows, size=1500):
        statement = insert(MarketDataBar).values(row_batch)
        update_required = (
            MarketDataBar.open.is_distinct_from(statement.excluded.open)
            | MarketDataBar.high.is_distinct_from(statement.excluded.high)
            | MarketDataBar.low.is_distinct_from(statement.excluded.low)
            | MarketDataBar.close.is_distinct_from(statement.excluded.close)
            | MarketDataBar.adj_close.is_distinct_from(statement.excluded.adj_close)
            | MarketDataBar.volume.is_distinct_from(statement.excluded.volume)
            | MarketDataBar.turnover_amount.is_distinct_from(statement.excluded.turnover_amount)
            | MarketDataBar.data_status.is_distinct_from(statement.excluded.data_status)
            | MarketDataBar.payload_json.is_distinct_from(statement.excluded.payload_json)
        )
        # 直接依赖 PostgreSQL RETURNING 回传 insert/update 数量，避免预查一轮已存在时间戳。
        result = session.execute(
            statement.on_conflict_do_update(
                constraint="uq_market_data_bars_series_time",
                set_={
                    "open": statement.excluded.open,
                    "high": statement.excluded.high,
                    "low": statement.excluded.low,
                    "close": statement.excluded.close,
                    "adj_close": statement.excluded.adj_close,
                    "volume": statement.excluded.volume,
                    "turnover_amount": statement.excluded.turnover_amount,
                    "data_status": statement.excluded.data_status,
                    "payload_json": statement.excluded.payload_json,
                    "ingested_at": func.now(),
                },
                where=update_required,
            ).returning(literal_column("xmax = 0", type_=BOOLEAN).label("inserted"))
        )
        for row in result:
            if bool(getattr(row, "inserted", False)):
                inserted_count += 1
            else:
                updated_count += 1
    series.first_bar_time = min(
        value for value in [series.first_bar_time, min(timestamps)] if value is not None
    )
    series.last_bar_time = max(
        value for value in [series.last_bar_time, max(timestamps)] if value is not None
    )
    series.last_ingested_at = utc_now()
    return inserted_count, updated_count


def get_source_file_manifest(
    session: Session,
    provider: DataProvider,
    source_path: str,
) -> SourceFileManifest | None:
    return session.scalar(
        select(SourceFileManifest).where(
            SourceFileManifest.provider_id == provider.id,
            SourceFileManifest.source_path == source_path,
        )
    )


def upsert_source_file_manifest(
    session: Session,
    provider: DataProvider,
    *,
    source_path: str,
    file_kind: str,
    market: str,
    interval: str,
    source_size: int,
    source_mtime: float,
    record_count: int,
    tail_hash: str | None,
    status: str,
    last_bar_time: str | datetime | None,
    instrument_id: int | None = None,
    series_id: int | None = None,
    payload_json: dict[str, object] | None = None,
) -> SourceFileManifest:
    manifest = get_source_file_manifest(session, provider, source_path)
    if manifest is None:
        manifest = SourceFileManifest(
            provider_id=provider.id,
            source_path=source_path,
        )
        session.add(manifest)

    manifest.instrument_id = instrument_id
    manifest.series_id = series_id
    manifest.file_kind = file_kind
    manifest.market = market
    manifest.interval = interval
    manifest.source_size = source_size
    manifest.source_mtime = source_mtime
    manifest.record_count = record_count
    manifest.tail_hash = tail_hash or ""
    manifest.status = status
    manifest.payload_json = payload_json or {}
    if last_bar_time:
        manifest.last_bar_time = pd.Timestamp(last_bar_time).to_pydatetime()
    else:
        manifest.last_bar_time = None
    manifest.updated_at = utc_now()
    session.flush()
    return manifest


def replace_corporate_action_events_for_symbol(
    session: Session,
    instrument: Instrument,
    provider: DataProvider,
    *,
    source_symbol: str,
    rows: list[dict[str, object]],
) -> tuple[int, int, int]:
    """按单个 source_symbol 全量替换公司行动，避免源端修订后留下陈旧事件。"""
    normalized_symbol = source_symbol.strip().upper()
    existing_rows = session.scalars(
        select(CorporateActionEvent).where(
            CorporateActionEvent.provider_id == provider.id,
            CorporateActionEvent.source_symbol == normalized_symbol,
        )
    ).all()
    existing_keys = {
        (
            row.source_symbol,
            row.action_type,
            row.ex_date,
            row.record_date,
            row.announce_date,
        )
        for row in existing_rows
    }
    new_keys = {
        (
            str(item["source_symbol"]).strip().upper(),
            str(item["action_type"]).strip().lower(),
            item.get("ex_date"),
            item.get("record_date"),
            item.get("announce_date"),
        )
        for item in rows
    }
    updated_count = len(existing_keys & new_keys)
    inserted_count = len(new_keys - existing_keys)
    deleted_count = len(existing_keys - new_keys)

    session.execute(
        delete(CorporateActionEvent).where(
            CorporateActionEvent.provider_id == provider.id,
            CorporateActionEvent.source_symbol == normalized_symbol,
        )
    )
    for item in rows:
        session.add(
            CorporateActionEvent(
                instrument_id=instrument.id,
                provider_id=provider.id,
                source_symbol=normalized_symbol,
                action_type=str(item["action_type"]).strip().lower(),
                announce_date=item.get("announce_date"),
                record_date=item.get("record_date"),
                ex_date=item.get("ex_date"),
                pay_date=item.get("pay_date"),
                end_date=item.get("end_date"),
                cash_dividend=float(item.get("cash_dividend") or 0.0),
                stock_bonus_ratio=float(item.get("stock_bonus_ratio") or 0.0),
                stock_conversion_ratio=float(item.get("stock_conversion_ratio") or 0.0),
                rights_ratio=float(item.get("rights_ratio") or 0.0),
                rights_price=float(item.get("rights_price") or 0.0),
                status=str(item.get("status") or "implemented"),
                raw_payload_json=dict(item.get("raw_payload_json") or {}),
            )
        )
    session.flush()
    return inserted_count, updated_count, deleted_count


def replace_price_adjustment_segments(
    session: Session,
    instrument: Instrument,
    provider: DataProvider,
    *,
    action_provider: DataProvider | None,
    adjustment_kind: str,
    rows: list[dict[str, object]],
) -> tuple[int, int, int]:
    """按单个标的全量替换前复权公式区间。"""
    existing_rows = session.execute(
        select(
            PriceAdjustmentSegment.start_date,
            PriceAdjustmentSegment.end_date,
        ).where(
            PriceAdjustmentSegment.instrument_id == instrument.id,
            PriceAdjustmentSegment.provider_id == provider.id,
            PriceAdjustmentSegment.adjustment_kind == adjustment_kind,
        )
    ).all()
    existing_keys = {
        (
            row.start_date,
            row.end_date,
        )
        for row in existing_rows
    }
    new_keys = {
        (
            item["start_date"],
            item["end_date"],
        )
        for item in rows
    }
    updated_count = len(existing_keys & new_keys)
    inserted_count = len(new_keys - existing_keys)
    deleted_count = len(existing_keys - new_keys)

    session.execute(
        delete(PriceAdjustmentSegment).where(
            PriceAdjustmentSegment.instrument_id == instrument.id,
            PriceAdjustmentSegment.provider_id == provider.id,
            PriceAdjustmentSegment.adjustment_kind == adjustment_kind,
        )
    )
    if rows:
        # 区间重建天然是整段覆盖，直接走批量 SQL 插入比逐条 ORM add 更轻。
        session.execute(
            insert(PriceAdjustmentSegment),
            [
                {
                    "instrument_id": instrument.id,
                    "provider_id": provider.id,
                    "action_provider_id": action_provider.id if action_provider is not None else None,
                    "adjustment_kind": adjustment_kind,
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
                    "adjust_a": item["adjust_a"],
                    "adjust_b": item["adjust_b"],
                    "status": str(item.get("status") or "ready"),
                    "payload_json": dict(item.get("payload_json") or {}),
                }
                for item in rows
            ],
        )
    session.flush()
    return inserted_count, updated_count, deleted_count


def create_data_ingestion_job(
    session: Session,
    *,
    provider: DataProvider | None,
    job_type: str,
    requested_via: str,
    target_scope_json: dict[str, object] | None = None,
    options_json: dict[str, object] | None = None,
    requested_by: str = "system",
    initial_status: str = "running",
) -> DataIngestionJob:
    job = DataIngestionJob(
        provider_id=provider.id if provider is not None else None,
        job_type=job_type,
        requested_by=requested_by,
        requested_via=requested_via,
        status=initial_status,
        target_scope_json=target_scope_json or {},
        options_json=options_json or {},
        summary_json={},
        started_at=utc_now() if initial_status == "running" else None,
    )
    session.add(job)
    session.flush()
    return job


def create_data_ingestion_job_item(
    session: Session,
    job: DataIngestionJob,
    *,
    item_key: str,
    source_symbol: str,
    interval: str,
    provider: DataProvider | None = None,
    initial_status: str = "running",
) -> DataIngestionJobItem:
    item = DataIngestionJobItem(
        job_id=job.id,
        provider_id=provider.id if provider is not None else None,
        item_key=item_key,
        source_symbol=source_symbol,
        interval=interval,
        stage="download",
        status=initial_status,
        details_json={},
        started_at=utc_now() if initial_status == "running" else None,
    )
    session.add(item)
    session.flush()
    return item


def claim_next_queued_ingestion_job(session: Session, *, requested_via: str = "api") -> DataIngestionJob | None:
    statement = (
        select(DataIngestionJob)
        .where(DataIngestionJob.status == "queued")
        .where(DataIngestionJob.requested_via == requested_via)
        .order_by(DataIngestionJob.priority.desc(), DataIngestionJob.requested_at, DataIngestionJob.id)
        .with_for_update(skip_locked=True)
    )
    job = session.scalars(statement).first()
    if job is None:
        return None
    job.status = "running"
    job.started_at = utc_now()
    session.flush()
    return job


def list_instrument_coverages(session: Session) -> list[dict[str, object]]:
    rows = session.execute(
        select(
            Instrument.symbol,
            Instrument.name,
            Instrument.exchange,
            PriceBar.interval,
            func.count(PriceBar.id).label("bar_count"),
            func.min(PriceBar.bar_time).label("start_time"),
            func.max(PriceBar.bar_time).label("end_time"),
            func.max(PriceBar.ingested_at).label("last_ingested_at"),
        )
        .join(PriceBar, PriceBar.instrument_id == Instrument.id)
        .group_by(Instrument.symbol, Instrument.name, Instrument.exchange, PriceBar.interval)
        .order_by(Instrument.symbol, PriceBar.interval)
    )
    return [
        {
            "symbol": row.symbol,
            "name": row.name,
            "exchange": row.exchange,
            "interval": row.interval,
            "bar_count": int(row.bar_count),
            "start_time": row.start_time.isoformat(sep=" ") if row.start_time else "",
            "end_time": row.end_time.isoformat(sep=" ") if row.end_time else "",
            "last_ingested_at": row.last_ingested_at.isoformat(sep=" ") if row.last_ingested_at else "",
        }
        for row in rows
    ]


def list_backtest_coverages(session: Session) -> list[dict[str, object]]:
    """返回当前可直接进入回测主路径的覆盖。

    选择规则与回测读取层保持一致：
    1. 旧 `price_bars` 命中时优先使用旧表。
    2. 否则尝试统一主干表；若同一标的/周期只存在唯一可用序列，则可直接进入主路径。
    3. 多条候选统一序列会被视为歧义，不进入自动推荐与首页主路径统计。
    """

    legacy_coverages = list_instrument_coverages(session)
    selected_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for row in legacy_coverages:
        key = (str(row["symbol"]), str(row["interval"]))
        selected_by_key[key] = {
            **row,
            "market_data_provider": "yahoo",
            "market_data_adjustment_kind": "raw",
            "backtest_source_kind": "legacy_price_bars",
        }

    unified_bar_stats = (
        select(
            MarketDataBar.series_id.label("series_id"),
            func.count(MarketDataBar.id).label("bar_count"),
        )
        .group_by(MarketDataBar.series_id)
        .subquery()
    )
    unified_rows = session.execute(
        select(
            MarketDataSeries.id.label("series_id"),
            Instrument.symbol.label("symbol"),
            Instrument.name.label("name"),
            Instrument.exchange.label("exchange"),
            DataProvider.provider_key.label("provider_key"),
            MarketDataSeries.interval.label("interval"),
            MarketDataSeries.adjustment_kind.label("adjustment_kind"),
            unified_bar_stats.c.bar_count.label("bar_count"),
            MarketDataSeries.first_bar_time.label("start_time"),
            MarketDataSeries.last_bar_time.label("end_time"),
            MarketDataSeries.last_ingested_at.label("last_ingested_at"),
        )
        .join(Instrument, Instrument.id == MarketDataSeries.instrument_id)
        .join(DataProvider, DataProvider.id == MarketDataSeries.provider_id)
        .join(unified_bar_stats, unified_bar_stats.c.series_id == MarketDataSeries.id)
        .where(MarketDataSeries.is_active.is_(True))
        .where(DataProvider.provider_key.in_(("yahoo", "tdx", "tdx_qfq")))
        .order_by(
            Instrument.symbol,
            MarketDataSeries.interval,
            DataProvider.provider_key,
            MarketDataSeries.adjustment_kind,
        )
    ).all()

    unified_candidates_by_key: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in unified_rows:
        key = (str(row.symbol), str(row.interval))
        if key in selected_by_key:
            continue
        unified_candidates_by_key[key].append(
            {
                "symbol": row.symbol,
                "name": row.name,
                "exchange": row.exchange,
                "interval": row.interval,
                "bar_count": _safe_int(row.bar_count),
                "start_time": _format_timestamp(row.start_time),
                "end_time": _format_timestamp(row.end_time),
                "last_ingested_at": _format_timestamp(row.last_ingested_at),
                "market_data_provider": row.provider_key,
                "market_data_adjustment_kind": row.adjustment_kind,
                "backtest_source_kind": "market_data_series",
                "series_id": _safe_int(row.series_id),
            }
        )

    for key, candidates in unified_candidates_by_key.items():
        if len(candidates) == 1:
            selected_by_key[key] = candidates[0]

    return sorted(selected_by_key.values(), key=lambda item: (str(item["symbol"]), str(item["interval"])))


def list_instruments(session: Session) -> list[dict[str, object]]:
    coverage_rows = list_instrument_coverages(session)
    grouped: dict[str, dict[str, object]] = {}
    for row in coverage_rows:
        entry = grouped.setdefault(
            str(row["symbol"]),
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "exchange": row["exchange"],
                "intervals": [],
                "last_end_time": "",
            },
        )
        entry["intervals"].append(row["interval"])
        if str(row["end_time"]) > str(entry["last_end_time"]):
            entry["last_end_time"] = row["end_time"]
    return list(grouped.values())


def list_recent_ingestion_jobs(session: Session, limit: int = 10) -> list[dict[str, object]]:
    rows = session.execute(
        select(DataIngestionJob, DataProvider.provider_key, DataProvider.provider_name)
        .outerjoin(DataProvider, DataProvider.id == DataIngestionJob.provider_id)
        .where(DataIngestionJob.requested_via != "worker_child")
        .order_by(DataIngestionJob.requested_at.desc(), DataIngestionJob.id.desc())
        .limit(limit)
    )
    jobs: list[dict[str, object]] = []
    for job, provider_key, provider_name in rows:
        target_scope = dict(job.target_scope_json or {})
        summary_json = dict(getattr(job, "summary_json", {}) or {})
        jobs.append(
            {
                "id": job.id,
                "provider_key": provider_key or "",
                "provider_name": provider_name or "",
                "job_type": job.job_type,
                "status": job.status,
                "targets_total": job.targets_total,
                "targets_completed": job.targets_completed,
                "rows_inserted": job.rows_inserted,
                "rows_updated": job.rows_updated,
                "error_count": job.error_count,
                "requested_at": _format_timestamp(job.requested_at),
                "completed_at": _format_timestamp(job.completed_at),
                "error_message": job.error_message,
                "target_symbol": str(target_scope.get("symbol") or summary_json.get("requested_symbol") or ""),
                "interval": str(target_scope.get("interval") or summary_json.get("requested_interval") or ""),
                "requested_via": job.requested_via,
                "summary_json": summary_json,
            }
        )
    return jobs


def get_ingestion_job_detail(session: Session, job_id: int) -> dict[str, object] | None:
    row_result = session.execute(
        select(DataIngestionJob, DataProvider.provider_key, DataProvider.provider_name)
        .outerjoin(DataProvider, DataProvider.id == DataIngestionJob.provider_id)
        .where(DataIngestionJob.id == job_id)
        .limit(1)
    )
    row = row_result.first() if hasattr(row_result, "first") else (row_result[0] if row_result else None)
    if row is None:
        return None

    job, provider_key, provider_name = row
    target_scope = dict(job.target_scope_json or {})
    summary_json = dict(job.summary_json or {})
    items_rows_result = session.execute(
        select(DataIngestionJobItem, Instrument.symbol)
        .outerjoin(Instrument, Instrument.id == DataIngestionJobItem.instrument_id)
        .where(DataIngestionJobItem.job_id == job.id)
        .order_by(DataIngestionJobItem.id)
    )
    items_rows = items_rows_result.all() if hasattr(items_rows_result, "all") else list(items_rows_result)
    items: list[dict[str, object]] = []
    for item, instrument_symbol in items_rows:
        items.append(
            {
                "id": item.id,
                "job_id": item.job_id,
                "item_key": item.item_key,
                "source_symbol": item.source_symbol,
                "instrument_symbol": instrument_symbol or "",
                "interval": item.interval,
                "stage": item.stage,
                "status": item.status,
                "rows_inserted": item.rows_inserted,
                "rows_updated": item.rows_updated,
                "error_message": item.error_message,
                "details_json": dict(item.details_json or {}),
                "instrument_id": item.instrument_id,
                "series_id": item.series_id,
                "started_at": _format_timestamp(item.started_at),
                "completed_at": _format_timestamp(item.completed_at),
            }
        )

    return {
        "id": job.id,
        "provider_key": provider_key or "",
        "provider_name": provider_name or "",
        "job_type": job.job_type,
        "status": job.status,
        "targets_total": job.targets_total,
        "targets_completed": job.targets_completed,
        "rows_inserted": job.rows_inserted,
        "rows_updated": job.rows_updated,
        "error_count": job.error_count,
        "requested_at": _format_timestamp(job.requested_at),
        "started_at": _format_timestamp(job.started_at),
        "completed_at": _format_timestamp(job.completed_at),
        "error_message": job.error_message,
        "target_symbol": str(target_scope.get("symbol") or summary_json.get("requested_symbol") or ""),
        "interval": str(target_scope.get("interval") or summary_json.get("requested_interval") or ""),
        "requested_via": job.requested_via,
        "target_scope_json": target_scope,
        "options_json": dict(job.options_json or {}),
        "summary_json": summary_json,
        "items": items,
    }


def list_provider_series(
    session: Session,
    *,
    provider_key: str | None = None,
    symbol: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    provider_bar_stats = (
        select(
            MarketDataBar.series_id.label("series_id"),
            func.count(MarketDataBar.id).label("bar_count"),
        )
        .group_by(MarketDataBar.series_id)
        .subquery()
    )
    statement = (
        select(
            MarketDataSeries.id,
            DataProvider.provider_key,
            DataProvider.provider_name,
            Instrument.symbol.label("instrument_symbol"),
            Instrument.name.label("instrument_name"),
            InstrumentAlias.source_symbol.label("source_symbol"),
            MarketDataSeries.market,
            MarketDataSeries.exchange,
            MarketDataSeries.interval,
            MarketDataSeries.adjustment_kind,
            MarketDataSeries.session_type,
            MarketDataSeries.price_type,
            MarketDataSeries.bar_type,
            MarketDataSeries.currency,
            MarketDataSeries.timezone,
            MarketDataSeries.first_bar_time,
            MarketDataSeries.last_bar_time,
            MarketDataSeries.last_ingested_at,
            MarketDataSeries.is_active,
            MarketDataSeries.metadata_json,
            provider_bar_stats.c.bar_count,
        )
        .join(DataProvider, DataProvider.id == MarketDataSeries.provider_id)
        .join(Instrument, Instrument.id == MarketDataSeries.instrument_id)
        .outerjoin(InstrumentAlias, InstrumentAlias.id == MarketDataSeries.alias_id)
        .outerjoin(provider_bar_stats, provider_bar_stats.c.series_id == MarketDataSeries.id)
        .order_by(
            MarketDataSeries.last_ingested_at.desc().nullslast(),
            MarketDataSeries.last_bar_time.desc().nullslast(),
            DataProvider.provider_key,
            Instrument.symbol,
            MarketDataSeries.interval,
        )
        .limit(limit)
    )
    if provider_key and provider_key.strip() and provider_key.strip().lower() != "all":
        statement = statement.where(DataProvider.provider_key == provider_key.strip().lower())
    if symbol and symbol.strip():
        normalized_symbol = symbol.strip().upper()
        statement = statement.where(
            (Instrument.symbol == normalized_symbol) | (InstrumentAlias.source_symbol == normalized_symbol)
        )

    rows = session.execute(statement).all()
    return [
        {
            "series_id": row.id,
            "provider_key": row.provider_key,
            "provider_name": row.provider_name,
            "instrument_symbol": row.instrument_symbol,
            "instrument_name": row.instrument_name or row.instrument_symbol,
            "source_symbol": row.source_symbol or "",
            "market": row.market or "",
            "exchange": row.exchange or "",
            "interval": row.interval,
            "adjustment_kind": row.adjustment_kind,
            "session_type": row.session_type,
            "price_type": row.price_type,
            "bar_type": row.bar_type,
            "currency": row.currency or "",
            "timezone": row.timezone or "",
            "bar_count": _safe_int(row.bar_count),
            "first_bar_time": _format_timestamp(row.first_bar_time),
            "last_bar_time": _format_timestamp(row.last_bar_time),
            "last_ingested_at": _format_timestamp(row.last_ingested_at),
            "is_active": bool(row.is_active),
            "metadata_summary": _build_series_metadata_summary(row.metadata_json),
        }
        for row in rows
    ]


def _list_recent_ingestion_jobs_for_symbol(
    session: Session,
    *,
    symbol: str,
    limit: int = 10,
) -> list[dict[str, object]]:
    normalized_symbol = symbol.strip().upper()
    matched_item_job_ids = {
        int(row.job_id)
        for row in session.execute(
            select(DataIngestionJobItem.job_id)
            .outerjoin(Instrument, Instrument.id == DataIngestionJobItem.instrument_id)
            .where(
                (DataIngestionJobItem.source_symbol == normalized_symbol) | (Instrument.symbol == normalized_symbol)
            )
            .distinct()
        ).all()
    }

    rows = session.execute(
        select(DataIngestionJob, DataProvider.provider_key, DataProvider.provider_name)
        .outerjoin(DataProvider, DataProvider.id == DataIngestionJob.provider_id)
        .where(DataIngestionJob.requested_via != "worker_child")
        .order_by(DataIngestionJob.requested_at.desc(), DataIngestionJob.id.desc())
        .limit(max(limit * 10, 50))
    )
    jobs: list[dict[str, object]] = []
    for job, provider_key, provider_name in rows:
        target_scope = dict(job.target_scope_json or {})
        summary_json = dict(getattr(job, "summary_json", {}) or {})
        target_symbol = str(target_scope.get("symbol") or summary_json.get("requested_symbol") or "").strip().upper()
        target_symbols = [str(item).strip().upper() for item in target_scope.get("target_symbols", []) if str(item).strip()]
        if job.id not in matched_item_job_ids and target_symbol != normalized_symbol and normalized_symbol not in target_symbols:
            continue
        jobs.append(
            {
                "id": job.id,
                "provider_key": provider_key or "",
                "provider_name": provider_name or "",
                "job_type": job.job_type,
                "status": job.status,
                "targets_total": job.targets_total,
                "targets_completed": job.targets_completed,
                "rows_inserted": job.rows_inserted,
                "rows_updated": job.rows_updated,
                "error_count": job.error_count,
                "requested_at": _format_timestamp(job.requested_at),
                "completed_at": _format_timestamp(job.completed_at),
                "error_message": job.error_message,
                "target_symbol": str(target_scope.get("symbol") or summary_json.get("requested_symbol") or ""),
                "interval": str(target_scope.get("interval") or summary_json.get("requested_interval") or ""),
                "requested_via": job.requested_via,
                "summary_json": summary_json,
            }
        )
        if len(jobs) >= limit:
            break
    return jobs


def get_symbol_diagnostics(
    session: Session,
    *,
    symbol: str,
    limit: int = 20,
) -> dict[str, object]:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("诊断标的不能为空。")

    instrument = get_instrument_by_symbol(session, normalized_symbol)
    series_rows = list_provider_series(session, symbol=normalized_symbol, limit=limit)
    action_rows = list_corporate_actions(session, symbol=normalized_symbol, limit=limit)
    segment_rows = list_adjustment_segments(session, symbol=normalized_symbol, limit=limit)
    manifest_rows = list_source_file_manifests(session, symbol=normalized_symbol, limit=limit)
    recent_jobs = _list_recent_ingestion_jobs_for_symbol(session, symbol=normalized_symbol, limit=min(limit, 12))
    qfq_series_diagnostics = _build_qfq_series_diagnostics(series_rows=series_rows, action_rows=action_rows)
    qfq_force_cache_ready_count = sum(1 for row in qfq_series_diagnostics if bool(row.get("force_skip_cache_ready")))
    qfq_normal_skip_ready_count = sum(1 for row in qfq_series_diagnostics if bool(row.get("normal_skip_ready")))

    return {
        "symbol": normalized_symbol,
        "instrument_name": instrument.name if instrument is not None else normalized_symbol,
        "exchange": instrument.exchange if instrument is not None else "",
        "series_rows": series_rows,
        "corporate_action_rows": action_rows,
        "adjustment_segment_rows": segment_rows,
        "source_file_manifest_rows": manifest_rows,
        "recent_ingestion_jobs": recent_jobs,
        "qfq_series_diagnostics": qfq_series_diagnostics,
        "summary": {
            "series_count": len(series_rows),
            "corporate_action_count": len(action_rows),
            "adjustment_segment_count": len(segment_rows),
            "manifest_count": len(manifest_rows),
            "recent_job_count": len(recent_jobs),
            "qfq_series_count": len(qfq_series_diagnostics),
            "qfq_force_cache_ready_count": qfq_force_cache_ready_count,
            "qfq_normal_skip_ready_count": qfq_normal_skip_ready_count,
        },
    }


def list_corporate_actions(
    session: Session,
    *,
    provider_key: str | None = None,
    symbol: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    statement = (
        select(
            CorporateActionEvent.id,
            DataProvider.provider_key,
            DataProvider.provider_name,
            Instrument.symbol.label("instrument_symbol"),
            Instrument.name.label("instrument_name"),
            CorporateActionEvent.source_symbol,
            CorporateActionEvent.action_type,
            CorporateActionEvent.announce_date,
            CorporateActionEvent.record_date,
            CorporateActionEvent.ex_date,
            CorporateActionEvent.pay_date,
            CorporateActionEvent.end_date,
            CorporateActionEvent.cash_dividend,
            CorporateActionEvent.stock_bonus_ratio,
            CorporateActionEvent.stock_conversion_ratio,
            CorporateActionEvent.rights_ratio,
            CorporateActionEvent.rights_price,
            CorporateActionEvent.status,
            CorporateActionEvent.ingested_at,
            CorporateActionEvent.updated_at,
        )
        .join(DataProvider, DataProvider.id == CorporateActionEvent.provider_id)
        .join(Instrument, Instrument.id == CorporateActionEvent.instrument_id)
        .order_by(
            CorporateActionEvent.ex_date.desc().nullslast(),
            CorporateActionEvent.updated_at.desc().nullslast(),
            Instrument.symbol,
        )
        .limit(limit)
    )
    if provider_key and provider_key.strip() and provider_key.strip().lower() != "all":
        statement = statement.where(DataProvider.provider_key == provider_key.strip().lower())
    if symbol and symbol.strip():
        normalized_symbol = symbol.strip().upper()
        statement = statement.where(
            (Instrument.symbol == normalized_symbol) | (CorporateActionEvent.source_symbol == normalized_symbol)
        )

    rows = session.execute(statement).all()
    return [
        {
            "event_id": row.id,
            "provider_key": row.provider_key,
            "provider_name": row.provider_name,
            "instrument_symbol": row.instrument_symbol,
            "instrument_name": row.instrument_name or row.instrument_symbol,
            "source_symbol": row.source_symbol,
            "action_type": row.action_type,
            "announce_date": str(row.announce_date or ""),
            "record_date": str(row.record_date or ""),
            "ex_date": str(row.ex_date or ""),
            "pay_date": str(row.pay_date or ""),
            "end_date": str(row.end_date or ""),
            "cash_dividend": float(row.cash_dividend or 0.0),
            "stock_bonus_ratio": float(row.stock_bonus_ratio or 0.0),
            "stock_conversion_ratio": float(row.stock_conversion_ratio or 0.0),
            "rights_ratio": float(row.rights_ratio or 0.0),
            "rights_price": float(row.rights_price or 0.0),
            "status": row.status,
            "ingested_at": _format_timestamp(row.ingested_at),
            "updated_at": _format_timestamp(row.updated_at),
        }
        for row in rows
    ]


def list_adjustment_segments(
    session: Session,
    *,
    provider_key: str | None = None,
    symbol: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    statement = (
        select(
            PriceAdjustmentSegment.id,
            DataProvider.provider_key,
            DataProvider.provider_name,
            Instrument.symbol.label("instrument_symbol"),
            Instrument.name.label("instrument_name"),
            PriceAdjustmentSegment.adjustment_kind,
            PriceAdjustmentSegment.start_date,
            PriceAdjustmentSegment.end_date,
            PriceAdjustmentSegment.adjust_a,
            PriceAdjustmentSegment.adjust_b,
            PriceAdjustmentSegment.status,
            PriceAdjustmentSegment.payload_json,
            PriceAdjustmentSegment.generated_at,
            PriceAdjustmentSegment.updated_at,
            PriceAdjustmentSegment.action_provider_id,
            DataProvider.provider_key.label("segment_provider_key"),
        )
        .join(Instrument, Instrument.id == PriceAdjustmentSegment.instrument_id)
        .join(DataProvider, DataProvider.id == PriceAdjustmentSegment.provider_id)
        .order_by(
            PriceAdjustmentSegment.updated_at.desc().nullslast(),
            PriceAdjustmentSegment.start_date.desc(),
            Instrument.symbol,
        )
        .limit(limit)
    )
    if provider_key and provider_key.strip() and provider_key.strip().lower() != "all":
        statement = statement.where(DataProvider.provider_key == provider_key.strip().lower())
    if symbol and symbol.strip():
        normalized_symbol = symbol.strip().upper()
        statement = statement.where(Instrument.symbol == normalized_symbol)

    rows = session.execute(statement).all()
    action_provider_names: dict[int, str] = {}
    action_provider_ids = sorted({int(row.action_provider_id) for row in rows if row.action_provider_id is not None})
    if action_provider_ids:
        action_provider_rows = session.execute(
            select(DataProvider.id, DataProvider.provider_name)
            .where(DataProvider.id.in_(action_provider_ids))
        ).all()
        action_provider_names = {int(row.id): str(row.provider_name) for row in action_provider_rows}

    return [
        {
            "segment_id": row.id,
            "provider_key": row.provider_key,
            "provider_name": row.provider_name,
            "instrument_symbol": row.instrument_symbol,
            "instrument_name": row.instrument_name or row.instrument_symbol,
            "adjustment_kind": row.adjustment_kind,
            "start_date": str(row.start_date or ""),
            "end_date": str(row.end_date or ""),
            "adjust_a": float(row.adjust_a or 0.0),
            "adjust_b": float(row.adjust_b or 0.0),
            "status": row.status,
            "payload_json": dict(row.payload_json or {}),
            "action_provider_name": action_provider_names.get(int(row.action_provider_id)) if row.action_provider_id is not None else "",
            "generated_at": _format_timestamp(row.generated_at),
            "updated_at": _format_timestamp(row.updated_at),
        }
        for row in rows
    ]


def list_source_file_manifests(
    session: Session,
    *,
    provider_key: str | None = None,
    symbol: str | None = None,
    interval: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    statement = (
        select(
            SourceFileManifest.id,
            DataProvider.provider_key,
            DataProvider.provider_name,
            Instrument.symbol.label("instrument_symbol"),
            Instrument.name.label("instrument_name"),
            SourceFileManifest.series_id,
            SourceFileManifest.source_path,
            SourceFileManifest.file_kind,
            SourceFileManifest.market,
            SourceFileManifest.interval,
            SourceFileManifest.source_size,
            SourceFileManifest.source_mtime,
            SourceFileManifest.record_count,
            SourceFileManifest.tail_hash,
            SourceFileManifest.status,
            SourceFileManifest.last_bar_time,
            SourceFileManifest.payload_json,
            SourceFileManifest.updated_at,
        )
        .join(DataProvider, DataProvider.id == SourceFileManifest.provider_id)
        .outerjoin(Instrument, Instrument.id == SourceFileManifest.instrument_id)
        .order_by(
            SourceFileManifest.updated_at.desc().nullslast(),
            SourceFileManifest.interval,
            SourceFileManifest.source_path,
        )
        .limit(limit)
    )
    if provider_key and provider_key.strip() and provider_key.strip().lower() != "all":
        statement = statement.where(DataProvider.provider_key == provider_key.strip().lower())
    if symbol and symbol.strip():
        normalized_symbol = symbol.strip().upper()
        statement = statement.where(
            (Instrument.symbol == normalized_symbol) | func.upper(SourceFileManifest.source_path).contains(normalized_symbol)
        )
    if interval and interval.strip() and interval.strip().lower() != "all":
        statement = statement.where(SourceFileManifest.interval == interval.strip().lower())

    rows = session.execute(statement).all()
    return [
        {
            "manifest_id": row.id,
            "provider_key": row.provider_key,
            "provider_name": row.provider_name,
            "instrument_symbol": row.instrument_symbol or "",
            "instrument_name": row.instrument_name or row.instrument_symbol or "",
            "series_id": row.series_id,
            "source_path": row.source_path,
            "file_kind": row.file_kind,
            "market": row.market or "",
            "interval": row.interval,
            "source_size": _safe_int(row.source_size),
            "source_mtime": float(row.source_mtime or 0.0),
            "record_count": _safe_int(row.record_count),
            "tail_hash": row.tail_hash or "",
            "status": row.status,
            "last_bar_time": _format_timestamp(row.last_bar_time),
            "payload_json": dict(row.payload_json or {}),
            "updated_at": _format_timestamp(row.updated_at),
        }
        for row in rows
    ]


def get_market_data_stats(session: Session) -> dict[str, object]:
    instrument_count = int(session.scalar(select(func.count(Instrument.id))) or 0)
    total_bars = int(session.scalar(select(func.count(PriceBar.id))) or 0)
    interval_rows = session.execute(
        select(PriceBar.interval, func.count(PriceBar.id).label("bar_count"))
        .group_by(PriceBar.interval)
        .order_by(PriceBar.interval)
    )
    by_interval = [{"interval": row.interval, "bar_count": int(row.bar_count)} for row in interval_rows]
    coverages = list_instrument_coverages(session)
    backtest_coverages = list_backtest_coverages(session)
    backtest_instrument_count = len({str(item["symbol"]) for item in backtest_coverages})
    backtest_total_bars = sum(_safe_int(item.get("bar_count")) for item in backtest_coverages)
    backtest_interval_totals: dict[str, int] = defaultdict(int)
    for item in backtest_coverages:
        backtest_interval_totals[str(item["interval"])] += _safe_int(item.get("bar_count"))
    backtest_by_interval = [
        {"interval": interval, "bar_count": bar_count}
        for interval, bar_count in sorted(backtest_interval_totals.items())
    ]
    latest_sync = session.scalars(select(DataSyncRun).order_by(DataSyncRun.started_at.desc()).limit(10)).all()
    provider_series_stats = (
        select(
            MarketDataSeries.provider_id.label("provider_id"),
            func.count(MarketDataSeries.id).label("series_count"),
            func.array_agg(func.distinct(MarketDataSeries.interval)).label("intervals"),
            func.array_agg(func.distinct(MarketDataSeries.adjustment_kind)).label("adjustment_kinds"),
            func.max(MarketDataSeries.last_ingested_at).label("series_last_ingested_at"),
            func.max(MarketDataSeries.last_bar_time).label("latest_bar_time"),
        )
        .group_by(MarketDataSeries.provider_id)
        .subquery()
    )
    provider_bar_stats = (
        select(
            MarketDataSeries.provider_id.label("provider_id"),
            func.count(MarketDataBar.id).label("bars_count"),
        )
        .join(MarketDataBar, MarketDataBar.series_id == MarketDataSeries.id)
        .group_by(MarketDataSeries.provider_id)
        .subquery()
    )
    provider_action_stats = (
        select(
            CorporateActionEvent.provider_id.label("provider_id"),
            func.count(CorporateActionEvent.id).label("action_count"),
            func.max(CorporateActionEvent.ingested_at).label("latest_action_at"),
        )
        .group_by(CorporateActionEvent.provider_id)
        .subquery()
    )
    provider_segment_stats = (
        select(
            PriceAdjustmentSegment.provider_id.label("provider_id"),
            func.count(PriceAdjustmentSegment.id).label("segment_count"),
            func.max(PriceAdjustmentSegment.updated_at).label("latest_segment_at"),
        )
        .group_by(PriceAdjustmentSegment.provider_id)
        .subquery()
    )
    provider_manifest_stats = (
        select(
            SourceFileManifest.provider_id.label("provider_id"),
            func.count(SourceFileManifest.id).label("manifest_count"),
            func.max(SourceFileManifest.updated_at).label("latest_manifest_at"),
        )
        .group_by(SourceFileManifest.provider_id)
        .subquery()
    )
    latest_job_ranked = (
        select(
            DataIngestionJob.provider_id.label("provider_id"),
            DataIngestionJob.id.label("job_id"),
            DataIngestionJob.status.label("status"),
            DataIngestionJob.requested_at.label("requested_at"),
            DataIngestionJob.completed_at.label("completed_at"),
            func.row_number()
            .over(
                partition_by=DataIngestionJob.provider_id,
                order_by=(DataIngestionJob.requested_at.desc(), DataIngestionJob.id.desc()),
            )
            .label("rank_index"),
        )
        .where(DataIngestionJob.provider_id.is_not(None))
        .where(DataIngestionJob.requested_via != "worker_child")
        .subquery()
    )
    latest_job_stats = (
        select(
            latest_job_ranked.c.provider_id,
            latest_job_ranked.c.job_id,
            latest_job_ranked.c.status,
            latest_job_ranked.c.requested_at,
            latest_job_ranked.c.completed_at,
        )
        .where(latest_job_ranked.c.rank_index == 1)
        .subquery()
    )
    provider_rows = session.execute(
        select(
            DataProvider.provider_key,
            DataProvider.provider_name,
            DataProvider.provider_type,
            DataProvider.status,
            provider_series_stats.c.series_count,
            provider_series_stats.c.intervals,
            provider_series_stats.c.adjustment_kinds,
            provider_series_stats.c.series_last_ingested_at,
            provider_series_stats.c.latest_bar_time,
            provider_bar_stats.c.bars_count,
            provider_action_stats.c.action_count,
            provider_action_stats.c.latest_action_at,
            provider_segment_stats.c.segment_count,
            provider_segment_stats.c.latest_segment_at,
            provider_manifest_stats.c.manifest_count,
            provider_manifest_stats.c.latest_manifest_at,
            latest_job_stats.c.job_id,
            latest_job_stats.c.status.label("latest_job_status"),
            latest_job_stats.c.requested_at.label("latest_job_requested_at"),
            latest_job_stats.c.completed_at.label("latest_job_completed_at"),
        )
        .select_from(DataProvider)
        .outerjoin(provider_series_stats, provider_series_stats.c.provider_id == DataProvider.id)
        .outerjoin(provider_bar_stats, provider_bar_stats.c.provider_id == DataProvider.id)
        .outerjoin(provider_action_stats, provider_action_stats.c.provider_id == DataProvider.id)
        .outerjoin(provider_segment_stats, provider_segment_stats.c.provider_id == DataProvider.id)
        .outerjoin(provider_manifest_stats, provider_manifest_stats.c.provider_id == DataProvider.id)
        .outerjoin(latest_job_stats, latest_job_stats.c.provider_id == DataProvider.id)
        .order_by(DataProvider.provider_key)
    )
    provider_summaries: list[dict[str, object]] = []
    for row in provider_rows:
        latest_candidates = [
            row.series_last_ingested_at,
            row.latest_action_at,
            row.latest_segment_at,
            row.latest_manifest_at,
            row.latest_job_completed_at,
            row.latest_job_requested_at,
        ]
        latest_ingestion_at = max((item for item in latest_candidates if item is not None), default=None)
        provider_summaries.append(
            {
                "provider_key": row.provider_key,
                "provider_name": row.provider_name,
                "provider_type": row.provider_type,
                "status": row.status,
                "series_count": _safe_int(row.series_count),
                "bars_count": _safe_int(row.bars_count),
                "action_count": _safe_int(row.action_count),
                "segment_count": _safe_int(row.segment_count),
                "manifest_count": _safe_int(row.manifest_count),
                "intervals": _normalize_string_list(row.intervals),
                "adjustment_kinds": _normalize_string_list(row.adjustment_kinds),
                "latest_bar_time": _format_timestamp(row.latest_bar_time),
                "latest_ingestion_at": _format_timestamp(latest_ingestion_at),
                "latest_ingestion_status": row.latest_job_status or "",
                "latest_ingestion_job_id": _safe_int(row.job_id) if row.job_id is not None else None,
            }
        )
    recent_ingestion_jobs = list_recent_ingestion_jobs(session, limit=12)
    return {
        "instrument_count": instrument_count,
        "total_bars": total_bars,
        "by_interval": by_interval,
        "coverages": coverages,
        "backtest_instrument_count": backtest_instrument_count,
        "backtest_total_bars": backtest_total_bars,
        "backtest_by_interval": backtest_by_interval,
        "backtest_coverages": backtest_coverages,
        "provider_summaries": provider_summaries,
        "recent_ingestion_jobs": recent_ingestion_jobs,
        "recent_sync_runs": [
            {
                "id": run.id,
                "job_type": run.job_type,
                "interval": run.interval,
                "status": run.status,
                "started_at": _format_timestamp(run.started_at),
                "completed_at": _format_timestamp(run.completed_at),
                "symbols_count": run.symbols_count,
                "bars_inserted": run.bars_inserted,
                "bars_updated": run.bars_updated,
                "error_message": run.error_message,
            }
            for run in latest_sync
        ],
    }


def list_price_bars(
    session: Session,
    symbol: str,
    interval: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 2000,
) -> list[dict[str, object]]:
    instrument = get_instrument_by_symbol(session, symbol)
    if instrument is None:
        return []
    statement = (
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument.id, PriceBar.interval == interval)
        .order_by(PriceBar.bar_time.desc())
        .limit(limit)
    )
    if start:
        statement = statement.where(PriceBar.bar_time >= pd.Timestamp(start).to_pydatetime())
    if end:
        statement = statement.where(PriceBar.bar_time <= pd.Timestamp(end).to_pydatetime())
    rows = list(reversed(session.scalars(statement).all()))
    return [
        {
            "symbol": instrument.symbol,
            "interval": row.interval,
            "bar_time": row.bar_time.isoformat(sep=" "),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "adj_close": row.adj_close,
            "volume": row.volume,
            "source": row.source,
        }
        for row in rows
    ]


def load_price_frame_from_database(
    session: Session,
    symbol: str,
    interval: str,
    start: str | None = None,
    end: str | None = None,
) -> BacktestPriceFrameSnapshot:
    instrument = get_instrument_by_symbol(session, symbol)
    if instrument is None:
        raise ValueError(f"数据库中不存在该标的: {symbol}")

    statement: Select[tuple[PriceBar]] = (
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument.id, PriceBar.interval == interval)
        .order_by(PriceBar.bar_time)
    )
    if start:
        statement = statement.where(PriceBar.bar_time >= pd.Timestamp(start).to_pydatetime())
    if end:
        statement = statement.where(PriceBar.bar_time <= pd.Timestamp(end).to_pydatetime())

    rows = session.scalars(statement).all()
    if not rows:
        raise ValueError(f"数据库中没有可用于回测的行情: symbol={symbol} interval={interval}")
    frame = pd.DataFrame(
        [
            {
                "Date": row.bar_time,
                "Open": row.open,
                "High": row.high,
                "Low": row.low,
                "Close": row.close,
                "Volume": row.volume,
            }
            for row in rows
        ]
    )
    frame["Date"] = pd.to_datetime(frame["Date"])
    return BacktestPriceFrameSnapshot(
        frame=frame.sort_values("Date").set_index("Date"),
        source_label=f"database://price_bars/{symbol.upper()}/{interval}",
        source_kind="legacy_price_bars",
        provider_key="yahoo",
        adjustment_kind="raw",
        series_id=None,
    )


def load_backtest_price_frame_from_database(
    session: Session,
    symbol: str,
    interval: str,
    *,
    start: str | None = None,
    end: str | None = None,
    provider_key: str | None = None,
    adjustment_kind: str | None = None,
) -> BacktestPriceFrameSnapshot:
    """优先兼容旧 price_bars，同时支持从统一主干表读取回测行情。"""

    normalized_provider = _normalize_backtest_provider_key(provider_key)
    normalized_adjustment = _normalize_backtest_adjustment_kind(adjustment_kind)
    if normalized_adjustment is None:
        normalized_adjustment = _default_adjustment_kind_for_provider(normalized_provider)

    should_try_legacy = normalized_provider in {None, "yahoo"} and normalized_adjustment in {None, "raw"}
    legacy_error: ValueError | None = None
    if should_try_legacy:
        try:
            return load_price_frame_from_database(session, symbol, interval, start=start, end=end)
        except ValueError as exc:
            legacy_error = exc

    candidate_rows = list_provider_series(
        session,
        provider_key=normalized_provider or "all",
        symbol=symbol,
        limit=200,
    )
    filtered_candidates = [
        row
        for row in candidate_rows
        if str(row.get("interval") or "") == interval
        and bool(row.get("is_active"))
        and int(row.get("bar_count") or 0) > 0
        and (
            normalized_adjustment is None
            or str(row.get("adjustment_kind") or "").strip().lower() == normalized_adjustment
        )
    ]
    if not filtered_candidates:
        if legacy_error is not None:
            raise legacy_error
        provider_text = normalized_provider or "all"
        adjustment_text = normalized_adjustment or "all"
        raise ValueError(
            "数据库中没有匹配的统一行情序列: "
            f"symbol={symbol} interval={interval} provider={provider_text} adjustment={adjustment_text}"
        )
    if len(filtered_candidates) > 1:
        candidate_summary = ", ".join(
            f"{row['provider_key']}:{row['interval']}:{row['adjustment_kind']}(series_id={row['series_id']})"
            for row in filtered_candidates[:5]
        )
        raise ValueError(
            "数据库中存在多条可用于回测的统一行情序列，请显式指定 provider 或 adjustment_kind："
            f" {candidate_summary}"
        )

    selected_series = filtered_candidates[0]
    series_id = int(selected_series["series_id"])
    statement = (
        select(MarketDataBar)
        .where(MarketDataBar.series_id == series_id)
        .order_by(MarketDataBar.bar_time)
    )
    if start:
        statement = statement.where(MarketDataBar.bar_time >= pd.Timestamp(start).to_pydatetime())
    if end:
        statement = statement.where(MarketDataBar.bar_time <= pd.Timestamp(end).to_pydatetime())
    rows = session.scalars(statement).all()
    if not rows:
        raise ValueError(
            "统一行情序列存在，但当前筛选范围没有可用于回测的 K 线: "
            f"symbol={symbol} interval={interval} series_id={series_id}"
        )

    frame = pd.DataFrame(
        [
            {
                "Date": row.bar_time,
                "Open": row.open,
                "High": row.high,
                "Low": row.low,
                "Close": row.close,
                "Volume": row.volume,
            }
            for row in rows
        ]
    )
    frame["Date"] = pd.to_datetime(frame["Date"])
    resolved_provider = str(selected_series.get("provider_key") or "")
    resolved_adjustment = str(selected_series.get("adjustment_kind") or "")
    return BacktestPriceFrameSnapshot(
        frame=frame.sort_values("Date").set_index("Date"),
        source_label=(
            "database://market_data_series/"
            f"{resolved_provider}/{symbol.upper()}/{interval}/{resolved_adjustment or 'raw'}"
        ),
        source_kind="market_data_series",
        provider_key=resolved_provider,
        adjustment_kind=resolved_adjustment or "raw",
        series_id=series_id,
    )


def create_sync_run(session: Session, job_type: str, interval: str) -> DataSyncRun:
    run = DataSyncRun(job_type=job_type, interval=interval, status="running")
    session.add(run)
    session.flush()
    return run


def create_sync_run_item(session: Session, run: DataSyncRun, symbol: str) -> DataSyncRunItem:
    item = DataSyncRunItem(run_id=run.id, symbol=symbol, status="running")
    session.add(item)
    session.flush()
    return item


def list_sync_runs(session: Session, limit: int = 50) -> list[dict[str, object]]:
    runs = session.scalars(select(DataSyncRun).order_by(DataSyncRun.started_at.desc()).limit(limit)).all()
    return [
        {
            "id": run.id,
            "job_type": run.job_type,
            "interval": run.interval,
            "status": run.status,
            "started_at": run.started_at.isoformat(sep=" "),
            "completed_at": run.completed_at.isoformat(sep=" ") if run.completed_at else "",
            "symbols_count": run.symbols_count,
            "bars_inserted": run.bars_inserted,
            "bars_updated": run.bars_updated,
            "error_message": run.error_message,
        }
        for run in runs
    ]
