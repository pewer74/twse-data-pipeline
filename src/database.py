import sqlite3
from pathlib import Path

import pandas as pd


def init_db(db_path: Path) -> None:
    """建立 SQLite 資料表與複合主鍵（trade_date + stock_id）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_stock_metrics (
                trade_date      TEXT NOT NULL,
                stock_id        TEXT NOT NULL,
                stock_name      TEXT,
                open_price      REAL,
                high_price      REAL,
                low_price       REAL,
                close_price     REAL,
                price_change    REAL,
                trade_volume    INTEGER,
                foreign_net     INTEGER,
                trust_net       INTEGER,
                dealer_net      INTEGER,
                total_inst_net  INTEGER,
                updated_at      TEXT DEFAULT (datetime('now', '+8 hours')),
                PRIMARY KEY (trade_date, stock_id)
            );
            """
        )
        conn.commit()


def upsert_daily_metrics(db_path: Path, df: pd.DataFrame) -> int:
    """以 (trade_date, stock_id) 為衝突鍵執行 Upsert 寫入。"""
    if df.empty:
        return 0

    sql = """
    INSERT INTO daily_stock_metrics (
        trade_date, stock_id, stock_name,
        open_price, high_price, low_price, close_price, price_change, trade_volume,
        foreign_net, trust_net, dealer_net, total_inst_net, updated_at
    ) VALUES (
        :trade_date, :stock_id, :stock_name,
        :open_price, :high_price, :low_price, :close_price, :price_change, :trade_volume,
        :foreign_net, :trust_net, :dealer_net, :total_inst_net, datetime('now', '+8 hours')
    )
    ON CONFLICT(trade_date, stock_id) DO UPDATE SET
        stock_name     = excluded.stock_name,
        open_price     = excluded.open_price,
        high_price     = excluded.high_price,
        low_price      = excluded.low_price,
        close_price    = excluded.close_price,
        price_change   = excluded.price_change,
        trade_volume   = excluded.trade_volume,
        foreign_net    = excluded.foreign_net,
        trust_net      = excluded.trust_net,
        dealer_net     = excluded.dealer_net,
        total_inst_net = excluded.total_inst_net,
        updated_at     = datetime('now', '+8 hours');
    """
    records = df.to_dict(orient="records")
    with sqlite3.connect(db_path) as conn:
        conn.executemany(sql, records)
        conn.commit()
    return len(records)