import numpy as np
import pandas as pd
import yfinance as yf


def calculate_atr(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """計算 20 日 True Range (ATR)"""
    high = df["High"]
    low = df["Low"]
    close = df["Close"].shift(1)

    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def score_stock_strategy(
    df_stock: pd.DataFrame, df_market: pd.DataFrame = None
) -> pd.DataFrame:
    """計算個股硬性篩選與量化計分卡

    df_stock: 個股日線 DataFrame (需包含 Open, High, Low, Close, Volume)
    df_market: 大盤日線 DataFrame (用於計算相對強勢)
    """
    df = df_stock.copy()

    # =========================================================================
    # 基礎指標計算
    # =========================================================================
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA20_Slope"] = df["MA20"].diff()

    # 成交值 (億元) = (成交量 * 收盤價) / 100,000,000
    df["Turnover_100M"] = (df["Volume"] * df["Close"]) / 1e8

    # 20 日 ATR & ATR 佔比
    df["ATR20"] = calculate_atr(df, period=20)
    df["ATR_Ratio"] = df["ATR20"] / df["Close"]

    # 20 日最高收盤價 (不含今日)
    df["High_Close_20D"] = df["Close"].shift(1).rolling(20).max()

    # 成交量能比值 (今日量 / 5日均量)
    df["Vol_MA5"] = df["Volume"].rolling(5).mean().shift(1)
    df["Vol_Ratio"] = df["Volume"] / df["Vol_MA5"]

    # 當日報酬率 (%)
    df["Stock_Return"] = df["Close"].pct_change() * 100

    if df_market is not None:
        market_return = df_market["Close"].pct_change() * 100
        # 依據日期對齊大盤報酬
        df["Market_Return"] = market_return.reindex(df.index)
        df["RS_Diff"] = df["Stock_Return"] - df["Market_Return"]
    else:
        df["RS_Diff"] = 0.0

    # =========================================================================
    # 【一、股票池硬性篩選】(全符合為 True)
    # =========================================================================
    c1 = df["Close"] > 30  # 股價 > 30
    c2 = df["Turnover_100M"] >= 2.0  # 日成交值 >= 2 億
    c3 = df["ATR_Ratio"] <= 0.06  # ATR / 股價 <= 6%
    # 注：處置股篩選將在即時 API 模組或黑名單中剔除
    df["Pass_Hard_Filter"] = c1 & c2 & c3

    # =========================================================================
    # 【二、趨勢與強勢度計分】(滿分 65 分)
    # =========================================================================
    # 1. 均線排列 (30分)
    score_ma20 = np.where(df["Close"] > df["MA20"], 10, 0)
    score_ma60 = np.where(df["MA20"] > df["MA60"], 10, 0)
    score_slope = np.where(df["MA20_Slope"] > 0, 10, 0)
    df["Score_MA"] = score_ma20 + score_ma60 + score_slope

    # 2. 突破強度 (15分)
    df["Score_Breakout"] = np.where(df["Close"] >= df["High_Close_20D"], 15, 0)

    # 3. 成交量能 (15分)：連續給分，1.5倍得滿分15分 (比值 <= 1.0 給 0分)
    vol_score = (df["Vol_Ratio"] - 1.0) / (1.5 - 1.0) * 15
    df["Score_Volume"] = np.clip(vol_score, 0, 15)

    # 4. 相對強勢 (15分)：差距 >= 3% 得滿分15分 (差距 <= 0% 給 0分)
    rs_score = (df["RS_Diff"] / 3.0) * 15
    df["Score_RS"] = np.clip(rs_score, 0, 15)

    df["Score_Trend"] = (
        df["Score_MA"]
        + df["Score_Breakout"]
        + df["Score_Volume"]
        + df["Score_RS"]
    )

    # =========================================================================
    # 【三、尾盤動能計分 - 日線替代邏輯】(滿分 25 分)
    # =========================================================================
    # 1. 尾盤價格力道 (15分)：以 收盤價 / 當日最高價 替代
    price_ratio = df["Close"] / df["High"]
    # >= 99% 滿分 15分；低於 99% 每差 1% 扣 5分；低於 96% (差距 > 3%) 給 0分
    p_score = 15 - (0.99 - price_ratio) * 100 * 5
    df["Score_Tail_Price"] = np.where(
        price_ratio >= 0.99, 15, np.where(price_ratio < 0.96, 0, p_score)
    )

    # 2. 尾盤籌碼集壓 (10分)：歷史日線缺乏分線資料時，以基礎權重替代 (或設為 5分 中性值)
    df["Score_Tail_Volume"] = 5.0

    df["Score_Tail"] = df["Score_Tail_Price"] + df["Score_Tail_Volume"]

    # =========================================================================
    # 【總分計算】
    # =========================================================================
    df["Total_Score"] = df["Score_Trend"] + df["Score_Tail"]

    # 最終訊號觸發條件
    df["Signal"] = df["Pass_Hard_Filter"] & (df["Total_Score"] >= 70)

    return df