import os
import sys
import json
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime

# ==============================================================================
# ⚙️ 策略參數自訂區（客製化個股看盤區間）
# ==============================================================================
# 1. 預設區間：如果網頁新增了「下方對照表沒寫到」的股票，一律採用這個預設區間
DEFAULT_PERIOD = "1y" 

# 2. 個股專屬對照表：在這裡指定每檔股票想要觀看的特殊區間
# 可選：'3mo', '6mo', '1y', '2y', '3y', '5y'
STOCK_PERIOD_MAP = {
    "0050.TW": "3y",     # 元大台灣50：大盤型適合 3 年長線位階
    "2330.TW": "3y",     # 台積電：長期發展大廠適合 3 年長線位階
    "3293.TWO": "3mo",   # 鈊象：遊戲股高波動，適合 3 個月短線波段
    "8069.TWO": "6mo",   # 元太：中短期題材波動，適合 6 個月波段
    # 💡 未來有新想法，可以直接在下方依照格式手動新增，例如 "2454.TW": "1y",
}

# ==============================================================================
# 📈 樂活五線譜與技術指標監控自動化腳本 (LOHAS Monitor Bot)
# ==============================================================================

def calculate_lohas_lines(df):
    """ 計算樂活五線譜的核心數學邏輯 """
    if len(df) < 30:
        return None
    prices = df['Close'].values
    x = np.arange(len(prices))
    
    slope, intercept = np.polyfit(x, prices, 1)
    reg_line = slope * x + intercept
    std_dev = np.std(prices - reg_line)
    
    return {
        'reg': reg_line[-1],
        'up2': reg_line[-1] + 2 * std_dev,
        'up1': reg_line[-1] + 1 * std_dev,
        'dn1': reg_line[-1] - 1 * std_dev,
        'dn2': reg_line[-1] - 2 * std_dev,
        'current': prices[-1]
    }

def calculate_lohas_channel(df):
    """ 計算樂活通道（20日最高/最低價平均） """
    if len(df) < 20:
        return None
    ma20_high = df['High'].rolling(window=20).mean().iloc[-1]
    ma20_low = df['Low'].rolling(window=20).mean().iloc[-1]
    return {'top': ma20_high, 'bottom': ma20_low}

def calculate_kd(df):
    """ 計算標準技術指標 KD 值 (9, 3, 3) """
    if len(df) < 9:
        return 50.0, 50.0
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    
    k, d = [50.0], [50.0]
    for r in rsv.fillna(50).values[1:]:
        current_k = (1/3) * r + (2/3) * k[-1]
        current_d = (1/3) * current_k + (2/3) * d[-1]
        k.append(current_k)
        d.append(current_d)
    return k[-1], d[-1]

def send_telegram_message(message):
    """ 將分析結果透過 Telegram Bot API 推送 """
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("💡 提示：未偵測到 Telegram 設定，分析報告將僅於控制台輸出。")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("🚀 Telegram 報告推送成功！")
        else:
            print(f"❌ 推送失敗，API 回報狀態碼: {response.status_code}")
    except Exception as e:
        print(f"❌ 推送時發生異常網路錯誤: {e}")

# ==============================================================================
# ⚠️ 核心注意：下方的 stock_list 變數會被前端管理網頁 (GitHub Pages) 動態識別與修改。
# ==============================================================================









stock_list = ["0050.TW", "2330.TW", "3711.TW", "8069.TWO", "6953.TWO", "3293.TWO", "6625.TW"]

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動樂活策略多空監控排程...")
    report_msg = "\n📊 樂活盯盤量化分析報告 📊\n"
    has_valid_data = False
    
    for stock in stock_list:
        try:
            print(f" 🔍 正在處理標的: {stock} ...")
            ticker = yf.Ticker(stock)
            
            # 🔥 核心改動：檢查對照表，有設定就用專屬區間，沒有就用預設值
            current_period = STOCK_PERIOD_MAP.get(stock, DEFAULT_PERIOD)
            df = ticker.history(period=current_period)
            
            if df.empty:
                print(f"  ⚠️ 無法取得 {stock} 的歷史股價，請檢查代碼是否正確。")
                continue
                
            lohas = calculate_lohas_lines(df)
            channel = calculate_lohas_channel(df)
            k_val, d_val = calculate_kd(df)
            
            if not lohas or not channel:
                continue
                
            has_valid_data = True
            current_price = lohas['current']
            channel_top = channel['top']
            channel_bottom = channel['bottom']
            
            if current_price <= lohas['dn2']:
                position_status = "🔥 超跌 (低於極度悲觀線)"
                price_zone = "low"
            elif current_price <= lohas['dn1']:
                position_status = "📉 偏低 (低於相對悲觀線)"
                price_zone = "low"
            elif current_price >= lohas['up2']:
                position_status = "⚠️ 超漲 (高於極度樂觀線)"
                price_zone = "high"
            elif current_price >= lohas['up1']:
                position_status = "📈 偏高 (高於相對樂觀線)"
                price_zone = "high"
            else:
                position_status = "⚖️ 正常 (常態均值區間)"
                price_zone = "normal"
                
            if price_zone == "low":
                if current_price > channel_top:
                    trade_signal = "🟢 買進訊號 (低檔轉強，突破通道上線)"
                else:
                    trade_signal = "🟡 低檔觀望 (悲觀區徘徊，尚未突破通道上線)"
            elif price_zone == "high":
                if current_price < channel_bottom:
                    trade_signal = "🔴 賣出訊號 (高檔轉弱，跌破通道下線)"
                else:
                    trade_signal = "🔵 續抱持有 (樂觀區讓獲利奔跑，未跌破通道)"
            else:
                trade_signal = "⚪ 持有觀望 (常態均值區，無強烈買賣訊號)"
                
            # 💡 訊息呈現優化：在股票名稱後方加上它本次採用的計算區間 (例如：3y)
            report_msg += (
                f"\n【{stock}】({current_period}區間)\n"
                f" 💰 當前收盤: {current_price:.2f}\n"
                f" 🎯 五線位階: {position_status}\n"
                f" 🔮 通道範圍: {channel_bottom:.2f} ~ {channel_top:.2f}\n"
                f" ⚡ 操盤訊號: {trade_signal}\n"
                f" 📊 技術指標: K={k_val:.1f} / D={d_val:.1f}\n"
            )
            
        except Exception as e:
            print(f"❌ 處理標的 {stock} 時發生非預期錯誤: {e}")
            
    if has_valid_data:
        print("\n=== 本地端報告預覽 ===")
        print(report_msg)
        send_telegram_message(report_msg)
    else:
        print("❌ 本次執行未成功分析任何股票標的。")

if __name__ == "__main__":
    main()
