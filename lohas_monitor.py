import os
import sys
import json
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime

# ==============================================================================
# 📈 樂活五線譜與技術指標監控自動化腳本 (LOHAS Monitor Bot)
# 功能說明：
# 1. 透過 yfinance 爬取歷史股價資料。
# 2. 自動計算線性回歸趨勢線，並推導出正負 1、2 倍標準差之樂活五線譜。
# 3. 計算樂活通道（20日最高價平均線、20日最低價平均線）。
# 4. 判斷目前價格位階，並結合五線譜與通道給出【買進、賣出、持有】訊號。
# ==============================================================================

def calculate_lohas_lines(df):
    """
    計算樂活五線譜的核心數學邏輯
    回傳值包含：回歸中線、樂觀線(up1/up2)、悲觀線(dn1/dn2)與當前股價
    """
    if len(df) < 30:
        return None
    prices = df['Close'].values
    x = np.arange(len(prices))
    
    # 使用最小平方法計算線性回歸
    slope, intercept = np.polyfit(x, prices, 1)
    reg_line = slope * x + intercept
    
    # 計算剩餘殘差的標準差
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
    """
    計算樂活通道：20日最高價平均（通道上線）與 20日最低價平均（通道下線）
    """
    if len(df) < 20:
        return None
        
    ma20_high = df['High'].rolling(window=20).mean().iloc[-1]
    ma20_low = df['Low'].rolling(window=20).mean().iloc[-1]
    
    return {
        'top': ma20_high,
        'bottom': ma20_low
    }

def calculate_kd(df):
    """
    計算標準技術指標 KD 值 (參數採用常見的 9, 3, 3)
    """
    if len(df) < 9:
        return 50.0, 50.0
        
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    
    k = [50.0]
    d = [50.0]
    
    # 逐日演算平滑 KD
    for r in rsv.fillna(50).values[1:]:
        current_k = (1/3) * r + (2/3) * k[-1]
        current_d = (1/3) * current_k + (2/3) * d[-1]
        k.append(current_k)
        d.append(current_d)
        
    df['K'] = k
    df['D'] = d
    return df['K'].iloc[-1], df['D'].iloc[-1]

def send_telegram_message(message):
    """
    將分析結果透過 Telegram Bot API 推送到指定的聊天室或群組
    """
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
# 請保持本行 (第 106 行) 的基本宣告語法，網頁端會利用精準的正則表達式自動覆蓋此清單。
# 改用 Telegram 伺服器通知，請記得在 GitHub Secrets 設定對應的 Token 與 Chat ID。
# ==============================================================================









stock_list = ["0050.TW","2330.TW","3711.TW","8069.TWO","6953.TWO","3293.TWO","6625.TW"]

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動樂活策略多空監控排程...")
    report_msg = "\n📊 樂活盯盤量化分析報告 📊\n"
    has_valid_data = False
    
    for stock in stock_list:
        try:
            print(f" 🔍 正在處理標的: {stock} ...")
            ticker = yf.Ticker(stock)
            df = ticker.history(period="3mo")
            
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
            
            # 1. 判斷五線譜位階與多空區間屬性
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
                
            # 2. 結合樂活通道進行進階判讀 (經典薛兆亨策略)
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
                
            # 3. 組裝訊息文字
            report_msg += (
                f"\n【{stock}】\n"
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
