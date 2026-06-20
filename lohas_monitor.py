import yfinance as yf
import pandas as pd
import numpy as np
import requests

# ⚠️ 請填入您的 Telegram 密鑰與 Chat ID（記得保留雙引號）
TG_TOKEN = "8288347537:AAHh3tAJO0DiuQEEM05iJZsJMimvmAcDWGY"
TG_CHAT_ID = "229223968"

def get_stock_data(stock_id):
    """使用 yfinance 抓取歷史 K 線資料，並嚴格截取 3.5 年區間（約 840 個交易日）"""
    ticker = yf.Ticker(stock_id)
    df = ticker.history(period="5y")  # 先抓取足夠的歷史資料
    df = df[['High', 'Low', 'Close']].dropna()
    
    # 🌟 樂活五線譜核心修正：只取最後 840 筆資料（約 3.5 年的中短期經濟循環）
    df = df.tail(840)
    return df

def calculate_five_lines(df):
    """計算線性迴歸趨勢線與正負 1, 2 倍標準差（五線譜）"""
    df['X'] = np.arange(len(df))
    y = df['Close'].values.astype(float)
    x = df['X'].values
    
    # 計算 3.5 年的線性迴歸斜率 a 與截距 b (y = ax + b)
    a, b = np.polyfit(x, y, 1)
    df['Trend'] = a * df['X'] + b
    
    # 計算 3.5 年殘差的標準差 (SD)
    residuals = y - df['Trend'].values
    sd = np.std(residuals)
    
    # 畫出五條線
    df['Too_Expensive'] = df['Trend'] + 2 * sd  # 昂貴線
    df['Optimistic'] = df['Trend'] + 1 * sd     # 相對樂觀線
    df['Pessimistic'] = df['Trend'] - 1 * sd    # 相對悲觀線
    df['Cheap'] = df['Trend'] - 2 * sd          # 便宜線
    return df

def calculate_kd(df, n=9):
    """計算日 KD 值 (9, 3, 3)"""
    df['Min_Low'] = df['Low'].rolling(window=n).min()
    df['Max_High'] = df['High'].rolling(window=n).max()
    
    # 計算 RSV 值
    df['RSV'] = ((df['Close'] - df['Min_Low']) / (df['Max_High'] - df['Min_Low'])) * 100
    df['RSV'] = df['RSV'].fillna(50)
    
    k_list, d_list = [], []
    k, d = 50, 50
    for rsv in df['RSV']:
        k = (2/3) * k + (1/3) * rsv
        d = (2/3) * d + (1/3) * k
        k_list.append(k)
        d_list.append(d)
        
    df['K'] = k_list
    df['D'] = d_list
    return df

def check_signal(df, stock_id):
    """綜合判斷五線譜位置與樂活 KD 區間"""
    latest = df.iloc[-1]
    current_price = float(latest['Close'])
    k_value = float(latest['K'])
    
    pessimistic_line = float(latest['Pessimistic'])
    cheap_line = float(latest['Cheap'])
    optimistic_line = float(latest['Optimistic'])
    expensive_line = float(latest['Too_Expensive'])
    
    report = f"\n📊 股票代號: {stock_id}\n最新收盤價: {current_price:.2f} (目前日K值: {k_value:.1f})\n"
    
    # 樂活區間買進邏輯
    if current_price <= pessimistic_line and k_value <= 20:
        if current_price <= cheap_line:
            report += "📢 ⚠️【🔥 極度便宜＋安全區間】股價跌破便宜線且KD低檔，建議分批買進！"
        else:
            report += "📢 ⚠️【✨ 相對悲觀＋安全區間】股價落入悲觀區且KD低檔，適合分批佈局！"
    # 樂活區間賣出邏輯
    elif current_price >= optimistic_line and k_value >= 80:
        if current_price >= expensive_line:
            report += "📢 ⚠️【⚠️ 極度昂貴＋過熱區間】股價突破昂貴線且KD高檔，建議獲利了結！"
        else:
            report += "📢 ⚠️【🔔 相對樂觀＋過熱區間】股價到達樂觀區且KD高檔，可考慮部分減碼！"
    # 價位與KD未同步的觀望訊號
    elif current_price <= pessimistic_line and k_value > 20:
        report += "📢 ⏳【⏳ 價格便宜但跌勢未止】股價雖低，但 KD 未達低檔區間，建議先觀望勿接刀。"
    elif current_price >= optimistic_line and k_value < 80:
        report += "📢 ⏳【⏳ 價格高檔但動能未歇】股價雖高，但 KD 未達高檔區間，可讓獲利再跑一下。"
    else:
        report += "📢 ☕ 目前處於常態波動區間，無特殊買賣訊號。"
        
    return report

def send_telegram_msg(token, chat_id, text):
    """發送訊息至 Telegram"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=payload)
    return response.status_code

if __name__ == "__main__":
    # 這裡可以自由增減您想追蹤的股票清單（台股、美股皆可）
    stock_list = ["0050.TW", "2330.TW", "3711.TW","8069.TWO","6953.TWO","3293.TWO" , "6625.TW"]
    
    total_report = "🤖 【樂活五線譜 3.5年版每日追蹤報告】\n"
    print("🤖 正在計算並發送 Telegram 報告...")
    
    for stock in stock_list:
        try:
            data = get_stock_data(stock)
            data = calculate_five_lines(data)
            data = calculate_kd(data)
            total_report += check_signal(data, stock) + "\n"
        except Exception as e:
            total_report += f"\n❌ {stock} 計算失敗: {e}\n"
            
    # 執行發送
    status = send_telegram_msg(TG_TOKEN, TG_CHAT_ID, total_report)
    if status == 200:
        print("✅ 報告已成功發送到您的手機 Telegram！")
    else:
        print(f"❌ 發送失敗，錯誤碼: {status}")
