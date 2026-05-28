from __future__ import annotations
"""上交所港股通沪名单抓取与快照加载。

这里把“官方抓取”和“仓库内可复现快照”分开处理：
- 平时 CLI 直接读取仓库内快照，避免解析参数时联网
- 需要更新名单时，再显式调用官方接口刷新快照
"""

import csv
import json
import re
from pathlib import Path

import requests

from strategy_studio.config import DEFAULT_SOUTHBOUND_SHANGHAI_SNAPSHOT_PATH


SSE_SOUTHBOUND_SHANGHAI_PAGE_URL = "https://www.sse.com.cn/services/hkexsc/disclo/eligible/"
SSE_SOUTHBOUND_QUERY_URL = "https://query.sse.com.cn/commonQuery.do"
SSE_SOUTHBOUND_SQL_ID = "COMMON_SSE_JYFW_HGT_XXPL_BDZQQD_L"
SSE_JSONP_CALLBACK = "jsonpCallback"
SNAPSHOT_COLUMNS = ["SecurityCode", "AbbrEn", "AbbrCn", "SecurityType", "UpdateDate"]


def _clean_security_name(value: str) -> str:
    return value.replace("\u3000", " ").strip()


def _parse_jsonp_payload(text: str, callback: str = SSE_JSONP_CALLBACK) -> dict[str, object]:
    match = re.fullmatch(rf"{re.escape(callback)}\((.*)\)\s*", text, flags=re.DOTALL)
    if match is None:
        raise ValueError("未能解析上交所港股通沪名单 JSONP 响应。")
    return json.loads(match.group(1))


def normalize_southbound_security_code(code: str) -> str:
    normalized = code.strip()
    if not normalized.isdigit():
        raise ValueError(f"港股通沪证券代码格式不正确: {code}")
    return normalized.zfill(5)


def normalize_southbound_symbol(code: str) -> str:
    """把上交所 5 位快照代码转换成 Yahoo 可识别的港股代码。

    上交所快照会把港股代码统一补齐成 5 位，例如：
    - `00001` 表示 `0001.HK`
    - `02800` 表示 `2800.HK`
    - `09988` 表示 `9988.HK`

    Yahoo 侧使用的是“去掉额外前导 0 后，至少保留 4 位”的写法，
    所以这里不能直接把 5 位快照代码拼成 `.HK`。
    """
    normalized = normalize_southbound_security_code(code)
    significant_code = normalized.lstrip("0") or "0"
    yahoo_code = significant_code.zfill(4) if len(significant_code) <= 4 else significant_code
    return f"{yahoo_code}.HK"


def fetch_southbound_shanghai_eligible_rows(timeout: int = 20) -> list[dict[str, str]]:
    """从上交所官方接口抓取当前港股通沪合资格证券名单。"""
    response = requests.get(
        SSE_SOUTHBOUND_QUERY_URL,
        params={
            "jsonCallBack": SSE_JSONP_CALLBACK,
            "sqlId": SSE_SOUTHBOUND_SQL_ID,
            "isPagination": "true",
            "pageHelp.pageSize": "2000",
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": "1",
            "keyword": "",
        },
        headers={
            "Referer": SSE_SOUTHBOUND_SHANGHAI_PAGE_URL,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = _parse_jsonp_payload(response.text)
    page_help = payload.get("pageHelp") or {}
    data = page_help.get("data") or []
    if not data:
        raise ValueError("上交所港股通沪名单返回为空，无法刷新快照。")
    rows: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "SecurityCode": normalize_southbound_security_code(str(item.get("SECURITY_CODE", ""))),
                "AbbrEn": _clean_security_name(str(item.get("ABBR_EN", ""))),
                "AbbrCn": _clean_security_name(str(item.get("ABBR_CN", ""))),
                "SecurityType": _clean_security_name(str(item.get("SECURITY_TYPE", ""))),
                "UpdateDate": str(item.get("UPDATE_DATE", "")).strip(),
            }
        )
    if not rows:
        raise ValueError("上交所港股通沪名单没有可用证券记录。")
    return rows


def refresh_southbound_shanghai_snapshot(
    snapshot_path: str | Path = DEFAULT_SOUTHBOUND_SHANGHAI_SNAPSHOT_PATH,
    timeout: int = 20,
) -> Path:
    """抓取官方名单并刷新仓库内默认快照。"""
    target = Path(snapshot_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = fetch_southbound_shanghai_eligible_rows(timeout=timeout)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return target


def load_southbound_shanghai_snapshot(
    snapshot_path: str | Path = DEFAULT_SOUTHBOUND_SHANGHAI_SNAPSHOT_PATH,
) -> list[dict[str, str]]:
    """读取仓库内的港股通沪名单快照。"""
    target = Path(snapshot_path)
    if not target.exists():
        raise FileNotFoundError(f"港股通沪名单快照不存在: {target}")
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{column: str(row.get(column, "")).strip() for column in SNAPSHOT_COLUMNS} for row in reader]
    if not rows:
        raise ValueError(f"港股通沪名单快照为空: {target}")
    return rows


def build_southbound_source_label(update_date: str) -> str:
    return f"上交所港股通沪名单，数据截至 {update_date}"
