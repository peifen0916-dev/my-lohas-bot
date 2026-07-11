import os
import sys
import logging
import pandas as pd
import yfinance as yf

from strategy_scorer import score_stock_strategy
from telegram_bot import send_telegram_message, format_scan_report

# =========================================================================
# ⚙️ 設定區：優先讀取 GitHub Secrets / 系統環境變數
# =========================================================================
TELEGRAM_TOKEN = os.environ.get("8288347537:AAHh3tAJO0DiuQEEM05iJZsJMimvmAcDWGY", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("229223968", "YOUR_CHAT_ID")

STOCK_POOL = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW",
    "3293.TWO", "2379.TW", "3037.TW", "2303.TW", "3034.TW"
]
MARKET_SYMBOL = "^TWII"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def run_daily_scan():
    logging.info("=== 開始執行尾盤量化掃描系統 (GitHub Actions) ===")
    
    try:
        df_market = yf.download(MARKET_SYMBOL, period="3mo", interval="1d", progress=False)
        if isinstance(df_market.columns, pd.MultiIndex):
            df_market.columns = df_market.columns.get_level_values(0)
    except Exception as e:
        logging.error(f"下載加權指數失敗: {e}")
        df_market = None

    candidates = []

    for symbol in STOCK_POOL:
        try:
            df_stock = yf.download(symbol, period="3mo", interval="1d", progress=False)
            if isinstance(df_stock.columns, pd.MultiIndex):
                df_stock.columns = df_stock.columns.get_level_values(0)
                
            if df_stock.empty or len(df_stock) < 30:
                continue
                
            df_scored = score_stock_strategy(df_stock, df_market)
            latest = df_scored.iloc[-1]
            
            if latest['Signal']:
                candidates.append({
                    'symbol': symbol,
                    'price': round(float(latest['Close']), 2),
                    'score': round(float(latest['Total_Score']), 1),
                    'score_trend': round(float(latest['Score_Trend']), 1),
                    'score_tail': round(float(latest['Score_Tail']), 1),
                })
                logging.info(f" 發現符合標的: {symbol} | 總分: {latest['Total_Score']:.1f}")
                
        except Exception as e:
            logging.error(f"處理 {symbol} 時發生錯誤: {e}")

    logging.info(f"掃描完成，共發現 {len(candidates)} 檔符合標的。")
    report_msg = format_scan_report(candidates)
    
    if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "YOUR_BOT_TOKEN":
        send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, report_msg)
    else:
        logging.warning("Telegram Token 未設定，跳過推播發送。")

    logging.info("=== 尾盤掃描作業結束 ===")

if __name__ == "__main__":
    run_daily_scan()