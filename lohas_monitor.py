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
# 3. 計算 9 日 RSV 與技術指標 KD 值。
# 4. 判斷目前價格位階是否處於超跌或超漲區間，並輸出分析報告。
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

def send_line_notify(message):
    """
    將分析結果透過 LINE Notify API 推送到指定的群組或對話框
    需在 GitHub Secrets 或系統環境變數中設定 LINE_TOKEN
    """
    token = os.environ.get("LINE_TOKEN")
    if not token:
        print("💡 提示：未偵測到 LINE_TOKEN 環境變數，分析報告將僅於控制台輸出。")
        return
        
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}
    
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            print("🚀 LINE Notify 報告推送成功！")
        else:
            print(f"❌ 推送失敗，API 回報狀態碼: {response.status_code}")
    except Exception as e:
        print(f"❌ 推送時發生異常網路錯誤: {e}")

# ==============================================================================
# ⚠️ 核心注意：下方的 stock_list 變數會被前端管理網頁 (GitHub Pages) 動態識別與修改。
# 請保持本行 (第 106 行) 的基本宣告語法，網頁端會利用精準的正則表達式自動覆蓋此清單。
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
            # 取近三個月日線資料計算五線譜與 KD
            df = ticker.history(period="3mo")
            
            if df.empty:
                print(f"  ⚠️ 無法取得 {stock} 的歷史股價，請檢查代碼是否正確。")
                continue
                
            lohas = calculate_lohas_lines(df)
            k_val, d_val = calculate_kd(df)
            
            if not lohas:
                continue
                
            has_valid_data = True
            
            # 位階判斷邏輯
            current_price = lohas['current']
            if current_price <= lohas['dn2']:
                position_status = "🔥 超跌 (低於極度悲觀線)"
            elif current_price <= lohas['dn1']:
                position_status = "📉 偏低 (低於相對悲觀線)"
            elif current_price >= lohas['up2']:
                position_status = "⚠️ 超漲 (高於極度樂觀線)"
            elif current_price >= lohas['up1']:
                position_status = "📈 偏高 (高於相對樂觀線)"
            else:
                position_status = "⚖️ 正常 (常態均值區間)"
                
            report_msg += f"\n【{stock}】\n 💰 當前收盤: {current_price:.2f}\n 🎯 樂活位階: {position_status}\n 📊 技術指標: K={k_val:.1f} / D={d_val:.1f}\n"
            
        except Exception as e:
            print(f"❌ 處理標的 {stock} 時發生非預期錯誤: {e}")
            
    if has_valid_data:
        print("\n=== 本地端報告預覽 ===")
        print(report_msg)
        # 如果您有設定 LINE 機器人，此行會自動把報告發到您手機上
        send_line_notify(report_msg)
    else:
        print("❌ 本次執行未成功分析任何股票標的。")

if __name__ == "__main__":
    main()
