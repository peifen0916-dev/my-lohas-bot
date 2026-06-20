import json
import os
import numpy as np
import pandas as pd
import requests
import yfinance as yf

# === 🌟 區域一：雲端股票清單 (可由 index.html 網頁端動態修改) ===
DEFAULT_STOCKS = [
    "0050.TW",
    "2330.TW",
    "3711.TW",
    "8069.TWO",
    "6953.TWO",
    "3293.TWO",
    "6625.TW",
]

# === 🔑 區域二：Telegram 機器人金鑰設定 ===
# 請在此處填入你原本測試成功的 Token 與 Chat ID
TG_TOKEN = "你的_TELEGRAM_BOT_TOKEN"
CHAT_ID = "你的_TELEGRAM_CHAT_ID"


# === 📈 區域三：樂活五線譜與 KD 計算核心邏輯 ===
def analyze_lohas(stock_code):
    # 抓取過去 1.5 年的歷史資料（用以計算 3.5 年或 1 年五線譜，此處以 1 年做精準示範）
    df = yf.Ticker(stock_code).history(period="1y")
    if df.empty:
        return f"📊 股票代號: {stock_code}\n❌ 錯誤：無法從 yfinance 取得資料。"

    close_prices = df["Close"].dropna()
    current_price = close_prices.iloc[-1]

    # 1. 計算線性迴歸線 (趨勢線)
    y = close_prices.values
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    current_trend = slope * x[-1] + intercept

    # 2. 計算標準差 (SD) 與昂貴線
    sd = np.std(y - (slope * x + intercept))
    expensive_line = current_trend + 2 * sd  # 突破極度昂貴線

    # 3. 計算日 KD 值 (標準 9, 3, 3 邏輯)
    df["Min_9"] = df["Low"].rolling(window=9).min()
    df["Max_9"] = df["High"].rolling(window=9).max()
    df["RSV"] = (
        (df["Close"] - df["Min_9"]) / (df["Max_9"] - df["Min_9"]) * 100
    )
    df["RSV"] = df["RSV"].fillna(50)

    k = 50
    k_list = []
    for rsv in df["RSV"]:
        k = (2 / 3) * k + (1 / 3) * rsv
        k_list.append(k)
    current_k = k_list[-1]

    # 4. 判斷訊號提示
    if current_price >= expensive_line and current_k >= 80:
        signal = "📢 訊號提示：【⚠️ 極度昂貴＋過熱區間】股價突破昂貴線且KD高檔，建議獲利了結！"
    elif current_price <= (current_trend - 2 * sd) and current_k <= 20:
        signal = "📢 訊號提示：【買進機會 ✨ 極度便宜＋低檔超賣】股價跌破便宜線且KD低檔，適合佈局！"
    else:
        signal = "📢 訊號提示：【盤整觀望 💤】目前處於正常波動區間，持續追蹤。"

    report = (
        f"📊 股票代號: {stock_code}\n"
        f"最新收盤價: {current_price:.2f} (目前日K值: {current_k:.1f})\n"
        f"{signal}\n"
    )
    return report


# === 🚀 區域四：主程式執行 (GitHub Actions 自動觸發點) ===
if __name__ == "__main__":
    print("🤖 正在計算樂活五線譜與KD值...")
    final_message = "🤖 樂活五線譜監控報告\n\n"

    for stock in DEFAULT_STOCKS:
        try:
            stock_report = analyze_lohas(stock)
            final_message += stock_report + "\n"
        except Exception as e:
            final_message += f"❌ 股票 {stock} 計算失敗: {str(e)}\n\n"

    # 發送訊息至 Telegram
    url = f"https://api.telegram.com/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": final_message}

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ 報告已成功發送到您的手機 Telegram！")
    else:
        print(f"❌ 發送失敗，錯誤碼: {response.status_code}")
