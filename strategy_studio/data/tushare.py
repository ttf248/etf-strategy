from __future__ import annotations

"""Tushare 公司行动抓取与标准化。"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

from strategy_studio.db.settings import load_platform_settings


TUSHARE_API_URL = "http://api.tushare.pro"
STOCK_BASIC_STATUSES = ("L", "D", "P")
STOCK_BASIC_FIELDS = ["ts_code", "symbol", "name", "exchange", "list_date", "list_status"]
DIVIDEND_FIELDS = [
    "ts_code",
    "end_date",
    "ann_date",
    "div_proc",
    "stk_div",
    "stk_bo_rate",
    "stk_co_rate",
    "cash_div",
    "cash_div_tax",
    "record_date",
    "ex_date",
    "pay_date",
    "imp_ann_date",
]


@dataclass(frozen=True)
class TushareClientSettings:
    token: str
    rate_limit_per_minute: int = 90
    timeout_seconds: float = 15.0
    retries: int = 3
    config_path: str = ""


class TushareClient:
    """使用 Tushare HTTP API，避免在异常里回显 token。"""

    def __init__(self, settings: TushareClientSettings) -> None:
        if not settings.token:
            raise ValueError("未配置 Tushare token。请设置 STRATEGY_STUDIO_TUSHARE_TOKEN，或在配置文件中提供 tushare.token。")
        self.settings = settings
        self._last_call_at = 0.0

    def query(
        self,
        api_name: str,
        params: dict[str, Any] | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        payload = {
            "api_name": api_name,
            "token": self.settings.token,
            "params": params or {},
            "fields": ",".join(fields or []),
        }
        response = self._post(payload)
        if int(response.get("code", -1)) != 0:
            raise RuntimeError(f"Tushare 接口 {api_name} 返回错误：{response.get('msg', '')}")
        data = response.get("data") or {}
        return pd.DataFrame(data.get("items") or [], columns=data.get("fields") or [])

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(max(self.settings.retries, 1)):
            self._throttle()
            try:
                request = Request(
                    TUSHARE_API_URL,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (OSError, URLError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Tushare 请求失败：{last_error}") from last_error

    def _throttle(self) -> None:
        rate = max(self.settings.rate_limit_per_minute, 1)
        interval = 60.0 / rate
        now = time.monotonic()
        delay = self._last_call_at + interval - now
        if delay > 0:
            time.sleep(delay)
        self._last_call_at = time.monotonic()


def load_tushare_client_settings() -> TushareClientSettings:
    """优先读环境变量，其次读本地 yaml 文本配置。"""
    platform = load_platform_settings()
    config_path_value = os.getenv("STRATEGY_STUDIO_TUSHARE_CONFIG_PATH", platform.tushare_config_path)
    config_path = Path(config_path_value).expanduser()
    file_values = _read_tushare_config(config_path)
    token = os.getenv("STRATEGY_STUDIO_TUSHARE_TOKEN", "").strip() or platform.tushare_token.strip() or file_values.get("token", "")
    rate_limit_per_minute = _to_int(
        os.getenv("STRATEGY_STUDIO_TUSHARE_RATE_LIMIT_PER_MINUTE", ""),
        file_values.get("rate_limit_per_minute"),
        90,
    )
    timeout_seconds = _to_float(
        os.getenv("STRATEGY_STUDIO_TUSHARE_TIMEOUT_SECONDS", ""),
        file_values.get("timeout_seconds"),
        15.0,
    )
    retries = _to_int(
        os.getenv("STRATEGY_STUDIO_TUSHARE_RETRIES", ""),
        file_values.get("retries"),
        3,
    )
    return TushareClientSettings(
        token=token,
        rate_limit_per_minute=max(rate_limit_per_minute, 1),
        timeout_seconds=max(timeout_seconds, 1.0),
        retries=max(retries, 1),
        config_path=str(config_path),
    )


def fetch_stock_basic(client: TushareClient) -> pd.DataFrame:
    """按上市/退市/暂停三种状态拉取股票清单。"""
    frames: list[pd.DataFrame] = []
    for list_status in STOCK_BASIC_STATUSES:
        frame = client.query(
            "stock_basic",
            params={"exchange": "", "list_status": list_status},
            fields=STOCK_BASIC_FIELDS,
        )
        if "list_status" not in frame.columns:
            frame["list_status"] = list_status
        frames.append(frame.reindex(columns=STOCK_BASIC_FIELDS))
    if not frames:
        return pd.DataFrame(columns=STOCK_BASIC_FIELDS)
    merged = pd.concat(frames, ignore_index=True)
    return merged.drop_duplicates(subset=["ts_code"], keep="first").sort_values("ts_code").reset_index(drop=True)


def normalize_dividend_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=DIVIDEND_FIELDS)
    normalized = frame.copy()
    for column in DIVIDEND_FIELDS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=DIVIDEND_FIELDS).fillna("")
    for column in DIVIDEND_FIELDS:
        normalized[column] = normalized[column].astype(str).str.strip()
    return normalized


def build_corporate_action_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """只保留已经有 ex_date 的实施事件，便于后续前复权直接复用。"""
    normalized = normalize_dividend_frame(frame)
    if normalized.empty:
        return []
    normalized = normalized[normalized["ex_date"] != ""].copy()
    if normalized.empty:
        return []

    rows: list[dict[str, object]] = []
    for item in normalized.to_dict(orient="records"):
        ts_code = str(item["ts_code"]).upper()
        rows.append(
            {
                "source_symbol": ts_code,
                "action_type": "dividend",
                "announce_date": _parse_date(item.get("ann_date")),
                "record_date": _parse_date(item.get("record_date")),
                "ex_date": _parse_date(item.get("ex_date")),
                "pay_date": _parse_date(item.get("pay_date")),
                "end_date": _parse_date(item.get("end_date")),
                "cash_dividend": _to_float(item.get("cash_div_tax"), item.get("cash_div"), 0.0),
                "stock_bonus_ratio": _to_float(item.get("stk_bo_rate"), "", 0.0),
                "stock_conversion_ratio": _to_float(item.get("stk_co_rate"), "", 0.0),
                "rights_ratio": 0.0,
                "rights_price": 0.0,
                "status": _normalize_action_status(item.get("div_proc"), ex_date=item.get("ex_date")),
                "raw_payload_json": item,
            }
        )
    deduped: dict[tuple[object, ...], dict[str, object]] = {}
    for row in rows:
        key = (
            row["source_symbol"],
            row["action_type"],
            row["ex_date"],
            row["record_date"],
            row["announce_date"],
        )
        deduped[key] = row
    return list(deduped.values())


def symbol_to_ts_code(symbol: str) -> str:
    text = str(symbol).strip().lower()
    if text.startswith("sh"):
        return f"{text[2:]}.SH"
    if text.startswith("sz"):
        return f"{text[2:]}.SZ"
    if text.startswith("bj"):
        return f"{text[2:]}.BJ"
    if text.endswith((".sh", ".sz", ".bj")):
        return text.upper()
    raise ValueError(f"无法从合约代码推断 Tushare ts_code：{symbol}")


def ts_code_to_instrument_symbol(ts_code: str) -> str:
    text = str(ts_code).strip().upper()
    if "." not in text:
        raise ValueError(f"非法的 Tushare ts_code：{ts_code}")
    code, exchange = text.split(".", maxsplit=1)
    return f"{exchange}{code}"


def ts_code_to_market(ts_code: str) -> str:
    text = str(ts_code).strip().upper()
    if "." not in text:
        raise ValueError(f"非法的 Tushare ts_code：{ts_code}")
    return text.split(".", maxsplit=1)[1]


def _read_tushare_config(config_path: Path) -> dict[str, str]:
    if not config_path.exists():
        return {}
    content = config_path.read_text(encoding="utf-8")
    block_match = re.search(r"(?ms)^tushare:\s*(\n(?:[ \t]+.+\n?)*)", content)
    if not block_match:
        return {}
    values: dict[str, str] = {}
    for key in ("token", "rate_limit_per_minute", "timeout_seconds", "retries"):
        match = re.search(rf"(?m)^[ \t]+{re.escape(key)}:\s*(.+?)\s*$", block_match.group(1))
        if match:
            values[key] = match.group(1).strip().strip("'\"")
    return values


def _normalize_action_status(div_proc: object, *, ex_date: object) -> str:
    text = str(div_proc or "").strip()
    if ex_date and str(ex_date).strip():
        return "implemented"
    if "预案" in text or "股东大会" in text:
        return "planned"
    return "unknown"


def _parse_date(value: object) -> object:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return pd.Timestamp(text).date()
    return pd.Timestamp(text).date()


def _to_int(primary: object, secondary: object, default: int) -> int:
    for value in (primary, secondary):
        if value not in (None, ""):
            return int(value)
    return default


def _to_float(primary: object, secondary: object, default: float) -> float:
    for value in (primary, secondary):
        text = str(value or "").strip()
        if text:
            return float(text)
    return default
