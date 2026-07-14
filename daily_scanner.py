import os
import sys
import logging
import requests
import pandas as pd
import yfinance as yf

from strategy_scorer import score_stock_strategy
from telegram_bot import send_telegram_message, format_scan_report

# =========================================================================
# ⚙️ 設定區
# =========================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
MARKET_SYMBOL = "^TWII"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def get_twse_stock_pool():
    """
    從台灣證券交易所 ISIN 頁面動態抓取所有『上市普通股』代碼
    """
    logging.info("正在從證交所抓取最新上市股票清單...")
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2" # 2 表示上市
    try:
        res = requests.get(url, timeout=10)
        df = pd.read_html(res.text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        
        # 篩選 CFiCode 為 ESVUFR (普通股)
        df_stocks = df[df['CFICode'] == 'ESVUFR'].copy()
        
        stock_pool = []
        for item in df_stocks['有價證券代號及名稱']:
            if '　' in item:
                code = item.split('　')[0].strip()
                # 確保是 4 位數純數字股票代號（排除憑證、權證等）
                if len(code) == 4 and code.isdigit():
                    stock_pool.append(f"{code}.TW")
                    
        logging.info(f"成功取得 {len(stock_pool)} 檔上市股票代碼。")
        return stock_pool
    except Exception as e:
        logging.error(f"抓取股票清單失敗: {e}，改用備用預設清單。")
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "3037.TW", "2303.TW", "2379.TW"]

def run_daily_scan():
    logging.info("=== 開始執行全台股尾盤量化掃描系統 ===")
    
    # 1. 取得大盤數據
    try:
        df_market = yf.download(MARKET_SYMBOL, period="3mo", interval="1d", progress=False)
        if isinstance(df_market.columns, pd.MultiIndex):
            df_market.columns = df_market.columns.get_level_values(0)
    except Exception as e:
        logging.error(f"下載加權指數失敗: {e}")
        df_market = None

    # 2. 取得全台股上市股票清單
    stock_pool = get_twse_stock_pool()
    
    # 3. 批次下載歷史資料 (每批次 100 檔，避免 API 阻擋並大幅加速)
    batch_size = 100
    candidates = []
    
    logging.info("開始批次下載股票歷史數據並進行策略計分...")
    
    for i in range(0, len(stock_pool), batch_size):
        batch_symbols = stock_pool[i:i + batch_size]
        try:
            # 批次下載 (一次下載 100 檔)
            data = yf.download(batch_symbols, period="3mo", interval="1d", group_by='ticker', progress=False)
            
            for symbol in batch_symbols:
                try:
                    # 提取單檔股票的多層級 Dataframe
                    if len(batch_symbols) > 1:
                        if symbol not in data.columns.levels[0]:
                            continue
                        df_stock = data[symbol].dropna(how='all').copy()
                    else:
                        df_stock = data.copy()
                        
                    if df_stock.empty or len(df_stock) < 30:
                        continue

                    # 移除 MultiIndex 欄位 (若存在)
                    if isinstance(df_stock.columns, pd.MultiIndex):
                        df_stock.columns = df_stock.columns.get_level_values(0)

                    # 💡 關鍵流動性過濾：近 20 日平均成交張數需 > 1,000 張 (量太小不考慮)
                    avg_volume_20d = df_stock['Volume'].tail(20).mean()
                    if avg_volume_20d < 1000 * 1000: # Volume 單位為股數
                        continue

                    # 計算策略分數
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
                        logging.info(f" 發現強勢標的: {symbol} | 總分: {latest['Total_Score']:.1f}")
                        
                except Exception as inner_e:
                    continue
                    
        except Exception as batch_e:
            logging.error(f"批次下載 {i} ~ {i+batch_size} 時發生錯誤: {batch_e}")

    logging.info(f"掃描完成，共發現 {len(candidates)} 檔符合條件標的。")
    report_msg = format_scan_report(candidates)
    
    # 發送 Telegram 訊息
    if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "YOUR_BOT_TOKEN":
        send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, report_msg)
    else:
        logging.warning("Telegram Token 未設定，跳過推播發送。")

    logging.info("=== 尾盤掃描作業結束 ===")

if __name__ == "__main__":
    run_daily_scan()
