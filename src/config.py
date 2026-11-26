from pathlib import Path

# 自訂觀察股票代碼清單
WATCHLIST = ["2330", "2377", "3189"]

# 資料庫路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "twse_stocks.db"

# TWSE 官方資料接口
TWSE_OPENAPI_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_OPENAPI_FMTQIK = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
TWSE_JSON_T86 = "https://www.twse.com.tw/rwd/zh/fund/T86"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TWSE-DataPipeline/1.0)",
    "Accept": "application/json",
}