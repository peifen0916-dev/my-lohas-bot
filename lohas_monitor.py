import os
import sys
import json
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime

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
# ⚠️ 核心注意：下方的 stock_dict 變數會被前端管理網頁 (GitHub Pages) 動態識別與修改。
# 網頁端會將資料儲存為："代碼": "中文名,時間區間"
# ==============================================================================









stock_dict = {"3711.TW":"日月光投控,6mo","8069.TWO":"元太,6mo","6953.TWO":"家碩,6mo","3293.TWO":"鈊象,6mo","2645.TW":"長榮航太,6mo","6176.TW":"瑞儀,1y"}

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動樂活策略多空監控排程...")
    report_msg = "\n📊 樂活盯盤量化分析報告 📊\n"
    has_valid_data = False
    
    for stock, raw_val in stock_dict.items():
        try:
            # 🔥 核心優化：從網頁傳回的打包數值中，拆解出中文名稱與自訂區間
            if "," in raw_val:
                stock_name, current_period = raw_val.split(',')
            else:
                stock_name = raw_val
                current_period = "1y" # 防呆兜底：若無舊資料則預設1年
                
            print(f" 🔍 正在處理標的: {stock_name} ({stock}) | 採用區間: {current_period} ...")
            ticker = yf.Ticker(stock)
            
            # 🔥 100% 聽從網頁指示的動態時間區間！
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
            reg_middle = lohas['reg']
            
            # 判斷五線譜區與數字位階 (1 ~ 6)
            if current_price >= lohas['up2']:
                position_status = "⚠️ 超漲 (高於極度樂觀線)"
                lohas_line_level = 6
                price_zone = "high"
            elif current_price >= lohas['up1']:
                position_status = "📈 偏高 (高於相對樂觀線)"
                lohas_line_level = 5
                price_zone = "high"
            elif current_price >= reg_middle:
                position_status = "⚖️ 正常 (均值~相對樂觀區間)"
                lohas_line_level = 4
                price_zone = "normal"
            elif current_price >= lohas['dn1']:
                position_status = "⚖️ 正常 (相對悲觀~均值區間)"
                lohas_line_level = 3
                price_zone = "normal"
            elif current_price >= lohas['dn2']:
                position_status = "📉 偏低 (低於相對悲觀線)"
                lohas_line_level = 2
                price_zone = "low"
            else:
                position_status = "🔥 超跌 (低於極度悲觀線)"
                lohas_line_level = 1
                price_zone = "low"
                
            # 判斷樂活通道區間與數字位階 (1 ~ 4)
            if current_price >= channel_top:
                channel_level = 4
            elif current_price >= reg_middle:
                channel_level = 3
            elif current_price >= channel_bottom:
                channel_level = 2
            else:
                channel_level = 1
                
            # 結合樂活雙指標進行操盤訊號判讀
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
                
            report_msg += (
                f"\n【{stock_name} / {stock}】({current_period}區間)\n"
                f" 💰 當前收盤: {current_price:.2f}\n"
                f" 🎯 五線位階: {position_status} ［區間：{lohas_line_level}］\n"
                f" 🔮 通道範圍: {channel_bottom:.2f} ~ {channel_top:.2f} ［區間：{channel_level}］\n"
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
