from typing import Dict, List, Optional
import requests


def send_telegram_message(
    token: str, chat_id: str, message: str
) -> Optional[Dict]:
    """透過 Telegram Bot API 發送 Markdown 格式訊息"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        if result.get("ok"):
            print(" Telegram 訊息推播成功！")
            return result
        else:
            print(
                f" Telegram 發送失敗，錯誤碼: {result.get('description')}"
            )
            return None
    except Exception as e:
        print(f" Telegram 連線例外: {e}")
        return None


def format_scan_report(candidates: List[dict]) -> str:
    """將篩選出的股票清單格式化為 Telegram 訊息"""
    if not candidates:
        return " **【台股尾盤選股通知】**\n\n今日尾盤無符合 70 分以上之標的。"

    msg = " **【台股尾盤量化選股 - 強勢標的通知】**\n"
    msg += f" 掃描時間：13:24\n"
    msg += f" 符合條件檔數：`{len(candidates)}` 檔\n"
    msg += "----------------------------------------\n\n"

    for item in candidates:
        msg += f" **{item['symbol']}** | 總分：`{item['score']:.1f}` 分\n"
        msg += f"• 當前價格：`{item['price']}` 元\n"
        msg += f"• 趨勢得分：`{item['score_trend']:.1f}` / 65\n"
        msg += f"• 尾盤動能：`{item['score_tail']:.1f}` / 25\n"
        msg += f"• 預估建議：T+1 開盤價進場，停損 `-5%`，停利 `+8%`\n\n"

    msg += "⚠️ *投資警語：本自動化訊號僅供策略研究參考，非操作建議。*"
    return msg