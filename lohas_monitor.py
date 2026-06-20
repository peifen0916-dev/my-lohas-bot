import json
import os
import streamlit as st

# 定義儲存股票的檔案名稱
STOCK_FILE = "stocks.json"
DEFAULT_STOCKS = [
    "0050.TW",
    "2330.TW",
    "3711.TW",
    "8069.TWO",
    "6953.TWO",
    "3293.TWO",
    "6625.TW",
]


# --- 功能函數：讀取與寫入檔案 ---
def load_stocks():
    """從 JSON 檔案讀取股票清單，若檔案不存在則建立預設清單"""
    if os.path.exists(STOCK_FILE):
        with open(STOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_STOCKS


def save_stocks(stocks):
    """將目前的股票清單寫入 JSON 檔案"""
    with open(STOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, indent=4)


# --- 網頁介面 UI 初始化 ---
st.set_page_config(page_title="LOHAS 股票監控後台", layout="centered")
st.title("📈 LOHAS 股票監控管理面板")

# 載入目前的股票清單
stock_list = load_stocks()

# --- 區域一：目前清單股票 ---
st.subheader("📋 目前監控中的股票清單")
if stock_list:
    # 用美觀的標籤（Tags）方式顯示目前清早
    st.write("、".join([f"`{stock}`" for stock in stock_list]))
else:
    st.info("目前清單空空如也，請從下方新增股票。")

st.markdown("---")

# --- 區域二與區域三：並排版面 (新增與刪除) ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("➕ 加入股票")
    new_stock = st.text_input(
        "輸入股票代碼", placeholder="例如: 2454.TW", key="add_input"
    ).upper()

    if st.button("確認加入", type="primary"):
        if not new_stock:
            st.error("請輸入正確的股票代碼！")
        elif new_stock in stock_list:
            st.warning(f" `{new_stock}` 已經在清單中囉！")
        else:
            stock_list.append(new_stock)
            save_stocks(stock_list)
            st.success(f"✅ 已成功加入 `{new_stock}`！")
            st.invalidate_pages()  # 重新整理網頁顯示最新狀態

with col2:
    st.subheader("❌ 刪除股票")
    # 刪除功能用「下拉選單」讓使用者選，體驗最好，也能防止打錯字
    if stock_list:
        delete_target = st.selectbox(
            "選擇要刪除的股票", ["請選擇"] + stock_list, key="delete_select"
        )

        if st.button("確認刪除", type="secondary"):
            if delete_target == "請选择":
                st.error("請先選擇一檔股票！")
            else:
                stock_list.remove(delete_target)
                save_stocks(stock_list)
                st.success(f"🗑️ 已成功刪除 `{delete_target}`！")
                st.invalidate_pages()
    else:
        st.text("暫無股票可供刪除")

# --- 區域四：執行原本的監控邏輯 ---
st.markdown("---")
if st.button("🚀 立即執行 Lohas 監控分析"):
    st.info("正在分析清單中的股票，請稍候...")
    # 這裡可以放你原本 lohas_monitor.py 的核心抓取與分析程式碼
    # 例如：你的分析函數(stock_list)
    st.success("分析完成！")
