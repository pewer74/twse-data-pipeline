import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config import (
    HEADERS,
    TWSE_JSON_T86,
    TWSE_OPENAPI_FMTQIK,
    TWSE_OPENAPI_STOCK_DAY_ALL,
    WATCHLIST,
)

logger = logging.getLogger(__name__)


def _parse_float(val: str | float | int | None) -> float | None:
    """清洗數值字串（移除千分位逗號，處理 '--' 或除權息 'X' 符號）。"""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if s in ("", "--", "---", "N/A"):
        return None
    # 處理漲跌欄位可能出現的 'X0.00'
    if s.startswith("X"):
        s = s[1:]
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(val: str | float | int | None) -> int:
    """清洗整數字串（成交股數、法人買賣超股數）。"""
    parsed = _parse_float(val)
    return int(round(parsed)) if parsed is not None else 0


def _roc_to_iso_date(roc_date: str) -> str:
    """將民國年字串（如 '1151126' 或 '115/11/26'）轉為 'YYYY-MM-DD'。"""
    clean = roc_date.replace("/", "").strip()
    year = int(clean[:-4]) + 1911
    month = int(clean[-4:-2])
    day = int(clean[-2:])
    return f"{year:04d}-{month:02d}-{day:02d}"


def get_taipei_today() -> datetime:
    return datetime.now(ZoneInfo("Asia/Taipei"))


def fetch_latest_trading_date() -> str | None:
    """從 TWSE OpenAPI 取得最新交易日（ISO 格式 YYYY-MM-DD）。"""
    resp = requests.get(TWSE_OPENAPI_FMTQIK, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    latest_roc = data[-1].get("Date", "")
    return _roc_to_iso_date(latest_roc) if latest_roc else None


def fetch_daily_quotes(watchlist: list[str] = WATCHLIST) -> pd.DataFrame:
    """抓取 TWSE OpenAPI 每日收盤行情，並篩選目標個股。"""
    resp = requests.get(TWSE_OPENAPI_STOCK_DAY_ALL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    raw_list = resp.json()

    records = []
    target_set = set(watchlist)
    for row in raw_list:
        code = str(row.get("Code", "")).strip()
        if code not in target_set:
            continue
        records.append(
            {
                "stock_id": code,
                "stock_name": str(row.get("Name", "")).strip(),
                "open_price": _parse_float(row.get("OpeningPrice")),
                "high_price": _parse_float(row.get("HighestPrice")),
                "low_price": _parse_float(row.get("LowestPrice")),
                "close_price": _parse_float(row.get("ClosingPrice")),
                "price_change": _parse_float(row.get("Change")),
                "trade_volume": _parse_int(row.get("TradeVolume")),
            }
        )
    return pd.DataFrame(records)


def fetch_institutional_net(
    trade_date_iso: str, watchlist: list[str] = WATCHLIST
) -> pd.DataFrame:
    """抓取指定日期之個股三大法人買賣超股數（T86 JSON 接口）。"""
    yyyymmdd = trade_date_iso.replace("-", "")
    params = {
        "response": "json",
        "date": yyyymmdd,
        "selectType": "ALLBUT0999",
    }
    time.sleep(1.5)  # 禮貌性間隔，避免連續請求過快
    resp = requests.get(TWSE_JSON_T86, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    # 休市或尚未公布資料時，stat 不會是 'OK'
    if payload.get("stat") != "OK" or "data" not in payload:
        logger.warning("日期 %s 無三大法人資料（stat=%s）", trade_date_iso, payload.get("stat"))
        return pd.DataFrame()

    fields: list[str] = payload.get("fields", [])
    rows: list[list[str]] = payload.get("data", [])

    # 動態定位欄位索引，避免證交所微調欄位順序導致錯位
    idx_code = fields.index("證券代號")
    idx_foreign = next(i for i, f in enumerate(fields) if "外陸資買賣超股數" in f)
    idx_trust = next(i for i, f in enumerate(fields) if "投信買賣超股數" in f)
    idx_dealer = next(i for i, f in enumerate(fields) if "自營商買賣超股數" in f and "避險" not in f and "自行" not in f)
    idx_total = next(i for i, f in enumerate(fields) if "三大法人買賣超股數" in f)

    records = []
    target_set = set(watchlist)
    for r in rows:
        code = str(r[idx_code]).strip()
        if code not in target_set:
            continue
        records.append(
            {
                "stock_id": code,
                "foreign_net": _parse_int(r[idx_foreign]),
                "trust_net": _parse_int(r[idx_trust]),
                "dealer_net": _parse_int(r[idx_dealer]),
                "total_inst_net": _parse_int(r[idx_total]),
            }
        )
    return pd.DataFrame(records)