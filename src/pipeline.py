import logging
import sys

import pandas as pd

from config import DB_PATH, WATCHLIST
from database import init_db, upsert_daily_metrics
from fetcher import (
    fetch_daily_quotes,
    fetch_institutional_net,
    fetch_latest_trading_date,
    get_taipei_today,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    # 確保資料庫與資料表在一開始就建立完成
    init_db(DB_PATH)

    today_str = get_taipei_today().strftime("%Y-%m-%d")
    logger.info("啟動台股盤後數據管線 | 執行日期（台北時間）: %s", today_str)

    # 1. 假日與休市防呆檢查
    latest_trading_date = fetch_latest_trading_date()
    if not latest_trading_date:
        logger.warning("無法取得 TWSE 最新交易日資訊，安全結束本次任務。")
        return

    if latest_trading_date != today_str:
        logger.info(
            "今日 (%s) 非交易日或盤後資料尚未更新（最新交易日為 %s），自動跳過。",
            today_str,
            latest_trading_date,
        )
        return

    # 2. 抓取收盤行情與三大法人買賣超
    quotes_df = fetch_daily_quotes(WATCHLIST)
    if quotes_df.empty:
        logger.warning("觀察清單 %s 今日無收盤行情資料，跳過寫入。", WATCHLIST)
        return

    inst_df = fetch_institutional_net(latest_trading_date, WATCHLIST)

    # 3. 合併行情與法人籌碼（若法人資料尚未公布則補 0，不中斷流程）
    if not inst_df.empty:
        merged_df = pd.merge(quotes_df, inst_df, on="stock_id", how="left")
    else:
        merged_df = quotes_df.copy()
        for col in ["foreign_net", "trust_net", "dealer_net", "total_inst_net"]:
            merged_df[col] = 0

    for col in ["foreign_net", "trust_net", "dealer_net", "total_inst_net"]:
        merged_df[col] = merged_df[col].fillna(0).astype(int)

    merged_df.insert(0, "trade_date", latest_trading_date)

    # 4. 寫入 SQLite（Upsert）
    affected = upsert_daily_metrics(DB_PATH, merged_df)
    logger.info("成功寫入/更新 %d 筆資料至 %s", affected, DB_PATH)
    logger.info("\n%s", merged_df.to_string(index=False))


if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as exc:
        logger.exception("管線執行發生非預期錯誤: %s", exc)
        sys.exit(1)