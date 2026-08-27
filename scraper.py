import json
import os
import time
from bs4 import BeautifulSoup

# 使用 curl_cffi 繞過 Cloudflare 檢測
try:
    from curl_cffi import requests
except ImportError:
    import requests


def fetch_auction_data():
    items = []
    # 模擬真實 Chrome 120 的請求標頭與 TLS 密碼套件
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://deltaforcetools.gg/",
    }

    session = requests.Session()

    for page in range(1, 15):
        url = f"https://deltaforcetools.gg/tw/auction-house?page={page}"
        try:
            # impersonate="chrome120" 模擬真實瀏覽器 TLS 指紋
            if hasattr(session, "get") and "impersonate" in session.get.__code__.co_varnames:
                res = session.get(url, headers=headers, impersonate="chrome120", timeout=15)
            else:
                res = session.get(url, headers=headers, timeout=15)

            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")

                # 解析 Next.js 頁面內嵌的 __NEXT_DATA__ JSON 數據（最準確，不受 DOM 結構改變影響）
                next_data_script = soup.find("script", id="__NEXT_DATA__")
                if next_data_script and next_data_script.string:
                    try:
                        json_data = json.loads(next_data_script.string)
                        page_props = json_data.get("props", {}).get("pageProps", {})
                        raw_items = (
                            page_props.get("auctionItems", [])
                            or page_props.get("items", [])
                            or page_props.get("data", [])
                        )

                        for item in raw_items:
                            name = item.get("name") or item.get("itemName")
                            price = item.get("price") or item.get("avgPrice") or item.get("lastPrice")
                            category = item.get("category") or item.get("type", "通用物資")

                            if name and price:
                                items.append({
                                    "name": str(name).strip(),
                                    "price": float(price),
                                    "category": str(category).strip()
                                })
                    except Exception as json_err:
                        print(f"解析 __NEXT_DATA__ 失敗: {json_err}")

                # 如果 Next.js 數據未包含，回退解析 HTML 表格
                if not items:
                    rows = soup.select("table tr, div[class*='ItemCard'], div[class*='auction']")
                    for row in rows:
                        text_cols = [c.text.strip() for c in row.select("td, span, p, div") if c.text.strip()]
                        if len(text_cols) >= 2:
                            name = text_cols[0]
                            # 提取數字價格
                            price_digits = "".join(filter(str.isdigit, text_cols[1]))
                            if price_digits:
                                items.append({
                                    "name": name,
                                    "price": float(price_digits),
                                    "category": "通用物資"
                                })

            time.sleep(1)
        except Exception as e:
            print(f"抓取頁面 {page} 失敗: {e}")

    return items


def update_dataset():
    data_file = "data.json"
    existing_data = {}

    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"讀取舊數據失敗: {e}")

    new_items = fetch_auction_data()

    # 絕對防空保護：若未抓到新資料，堅決不覆蓋原有 data.json
    if not new_items:
        print("【系統保護】本次未抓取到有效數據（可能觸發防爬牆），取消覆蓋更新以保護原有資料庫。")
        return

    print(f"成功抓取到 {len(new_items)} 筆真實物資資料！開始演算趨勢...")

    for item in new_items:
        name = item["name"]
        price = item["price"]

        quality = "gold"
        if "紅色" in name or "機密" in name or price >= 1000000:
            quality = "red"
        elif "紫色" in name or price >= 300000:
            quality = "purple"
        elif price < 100000:
            quality = "blue"

        if name not in existing_data:
            existing_data[name] = {
                "name": name,
                "category": item["category"],
                "quality": quality,
                "history": [price]
            }
        else:
            existing_data[name]["history"].append(price)
            if len(existing_data[name]["history"]) > 20:
                existing_data[name]["history"].pop(0)

        history = existing_data[name]["history"]
        if len(history) >= 2:
            diffs = [(history[i] - history[i - 1]) / history[i - 1] for i in range(1, len(history))]
            weights = [i + 1 for i in range(len(diffs))]
            weighted_rate = sum(d * w for d, w in zip(diffs, weights)) / sum(weights)
            predicted_price = round(price * (1 + weighted_rate))
            predicted_rate = round(weighted_rate * 100, 1)
        else:
            predicted_price = price
            predicted_rate = 0.0

        existing_data[name]["predictedPrice"] = predicted_price
        existing_data[name]["predictedRate"] = predicted_rate

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"更新成功！資料庫目前共有 {len(existing_data)} 筆物資。")


if __name__ == "__main__":
    update_dataset()
