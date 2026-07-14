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
    """從證交所抓取上市股票清單"""
    logging.info("正在從證交所抓取最新上市股票清單...")
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    try:
        res = requests.get(url, timeout=10)
        df = pd.read_html(res.text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        
        df_stocks = df[df['CFICode'] == 'ESVUFR'].copy()
        stock_pool = []
        for item in df_stocks['有價證券代號及名稱']:
            if '　' in item:
                code = item.split('　')[0].strip()
                if len(code) == 4 and code.isdigit():
                    stock_pool.append(f"{code}.TW")
        logging.info(f"成功取得 {len(stock_pool)} 檔上市股票代碼。")
        return stock_pool
    except Exception as e:
        logging.error(f"抓取股票清單失敗: {e}，改用備用預設清單。")
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "3037.TW", "2303.TW", "2379.TW"]

def run_daily_scan():
    logging.info("=== 開始執行全台股尾盤量化掃描系統 (Top 4 模式) ===")
    
    # 1. 下載加權指數
    try:
        df_market = yf.download(MARKET_SYMBOL, period="3mo", interval="1d", progress=False)
        if isinstance(df_market.columns, pd.MultiIndex):
            df_market.columns = df_market.columns.get_level_values(0)
    except Exception as e:
        logging.error(f"下載加權指數失敗: {e}")
        df_market = None

    # 2. 取得股票池
    stock_pool = get_twse_stock_pool()
    
    batch_size = 100
    all_scored_stocks = [] # 用來儲存所有計算出分數的股票
    
    logging.info("開始批次下載與計算量化分數...")
    
    for i in range(0, len(stock_pool), batch_size):
        batch_symbols = stock_pool[i:i + batch_size]
        try:
            data = yf.download(batch_symbols, period="3mo", interval="1d", group_by='ticker', progress=False)
            
            for symbol in batch_symbols:
                try:
                    if len(batch_symbols) > 1:
                        if symbol not in data.columns.levels[0]:
                            continue
                        df_stock = data[symbol].dropna(how='all').copy()
                    else:
                        df_stock = data.copy()
                        
                    if df_stock.empty or len(df_stock) < 30:
                        continue

                    if isinstance(df_stock.columns, pd.MultiIndex):
                        df_stock.columns = df_stock.columns.get_level_values(0)

                    # 流動性過濾：近 20 日平均成交張數 > 1,000 張
                    avg_volume_20d = df_stock['Volume'].tail(20).mean()
                    if avg_volume_20d < 1000 * 1000:
                        continue

                    # 計算策略分數
                    df_scored = score_stock_strategy(df_stock, df_market)
                    latest = df_scored.iloc[-1]
                    
                    # 只要計算成功就先存入清單，不在此處用 Signal 擋死
                    all_scored_stocks.append({
                        'symbol': symbol,
                        'price': round(float(latest['Close']), 2),
                        'score': round(float(latest['Total_Score']), 1),
                        'score_trend': round(float(latest['Score_Trend']), 1),
                        'score_tail': round(float(latest['Score_Tail']), 1),
                        'is_signal': bool(latest['Signal']) # 標記是否達到 70 分門檻
                    })
                        
                except Exception:
                    continue
                    
        except Exception as batch_e:
            logging.error(f"批次 {i} ~ {i+batch_size} 處理失敗: {batch_e}")

    # 3. 排序：依據『總得分 (score)』由高到低排序，並取前 4 名
    all_scored_stocks.sort(key=lambda x: x['score'], reverse=True)
    top_4_candidates = all_scored_stocks[:4]

    logging.info(f"掃描完成！全台股共有 {len(all_scored_stocks)} 檔符合流動性。")
    for idx, item in enumerate(top_4_candidates, 1):
        logging.info(f"Top {idx}: {item['symbol']} | 分數: {item['score']} | 出訊號: {item['is_signal']}")

    # 4. 美化格式並發送 Telegram 訊息
    report_msg = format_scan_report(top_4_candidates)
    
    if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "YOUR_BOT_TOKEN":
        send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, report_msg)
    else:
        logging.warning("Telegram Token 未設定，跳過推播發送。")

    logging.info("=== 掃描作業結束 ===")

if __name__ == "__main__":
    run_daily_scan()
