import json
import os
import re
from playwright.sync_api import sync_playwright


def parse_price(price_str):
    if not price_str:
        return 0.0

    s = str(price_str).replace(",", "").strip().upper()

    # 處理英文 M (Million = 百萬) e.g., 60M = 60,000,000
    if "M" in s:
        num = re.sub(r"[^\d.]", "", s.split("M")[0])
        return float(num) * 1_000_000 if num else 0.0

    # 處理英文 K (Thousand = 千) e.g., 600K = 600,000
    if "K" in s:
        num = re.sub(r"[^\d.]", "", s.split("K")[0])
        return float(num) * 1_000 if num else 0.0

    # 處理中文「萬」
    if "萬" in s:
        num = re.sub(r"[^\d.]", "", s.split("萬")[0])
        return float(num) * 10_000 if num else 0.0

    # 處理中文「億」
    if "億" in s:
        num = re.sub(r"[^\d.]", "", s.split("億")[0])
        return float(num) * 100_000_000 if num else 0.0

    # 純數字
    digits = re.sub(r"[^\d.]", "", s)
    return float(digits) if digits else 0.0


def fetch_auction_data():
    all_items = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        # 1. API 網絡監聽攔截（優先使用，避免 DOM 解析錯誤）
        def handle_response(response):
            if (
                "auction" in response.url or "items" in response.url
            ) and response.status == 200:
                try:
                    data = response.json()
                    raw_items = (
                        data.get("data", [])
                        or data.get("items", [])
                        or (data if isinstance(data, list) else [])
                    )

                    for item in raw_items:
                        name = item.get("name") or item.get("itemName")
                        raw_p = (
                            item.get("price")
                            or item.get("avgPrice")
                            or item.get("lastPrice")
                        )
                        category = item.get("category") or item.get(
                            "type", "交易所物資"
                        )

                        if name and raw_p is not None:
                            clean_name = re.sub(r"\s+", " ", str(name)).strip()
                            price = parse_price(raw_p)
                            if price > 0:
                                all_items[clean_name] = {
                                    "name": clean_name,
                                    "price": price,
                                    "category": str(category).strip(),
                                }
                except Exception:
                    pass

        page.on("response", handle_response)

        # 遍歷頁面
        for page_num in range(1, 16):
            url = f"https://deltaforcetools.gg/tw/auction-house?page={page_num}"
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

                # 2. 如果 API 攔截沒有拿到該頁資料，使用精確的 DOM 節點導航解析
                # 尋找個別物資卡片/表格列，確保「名稱」與「價格」綁定在同一卡片內
                item_nodes = page.query_selector_all(
                    "div[class*='card'], div[class*='AuctionItem'], tr"
                )

                for node in item_nodes:
                    try:
                        # 在當前卡片/列內部找名稱與價格
                        text_content = node.inner_text()
                        if not text_content:
                            continue

                        lines = [
                            l.strip()
                            for l in text_content.split("\n")
                            if l.strip()
                        ]
                        if len(lines) < 2:
                            continue

                        # 取卡片內的第一行為物資名稱
                        name_candidate = lines[0]
                        if (
                            len(name_candidate) > 40
                            or "頁" in name_candidate
                            or "價格" in name_candidate
                        ):
                            continue

                        clean_name = re.sub(
                            r"\s+", " ", name_candidate
                        ).strip()

                        # 只在當前卡片內尋找價格字串
                        price_val = 0.0
                        for line in lines[1:]:
                            # 優先尋找帶有貨幣符號或 M/K/萬 的數字
                            m = re.search(
                                r"[\$￥]?\s*([0-9.,]+\s*[萬億MKmk]?)", line
                            )
                            if m:
                                val = parse_price(m.group(1))
                                if val > 0:
                                    price_val = val
                                    break

                        if price_val > 50 and clean_name not in all_items:
                            all_items[clean_name] = {
                                "name": clean_name,
                                "price": price_val,
                                "category": "交易所物資",
                            }
                    except Exception:
                        continue

            except Exception as e:
                print(f"爬取第 {page_num} 頁發生異常: {e}")

        browser.close()

    return list(all_items.values())


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

    if not new_items:
        print("【防護機制】未成功擷取資料，取消覆蓋。")
        return

    print(
        f"抓取完成！共取得 {len(new_items)} 筆正確對應物資，開始寫入歷史紀錄..."
    )

    for item in new_items:
        name = item["name"]
        price = item["price"]

        quality = "gold"
        if price >= 10_000_000:  # 1000萬以上為紅色高價值物資
            quality = "red"
        elif price >= 1_000_000:  # 100萬以上為紫色
            quality = "purple"
        elif price < 100_000:
            quality = "blue"

        # 存在舊資料時，追加歷史紀錄
        if name in existing_data:
            existing_data[name]["history"].append(price)
            if len(existing_data[name]["history"]) > 20:
                existing_data[name]["history"].pop(0)

            existing_data[name]["price"] = price
            existing_data[name]["quality"] = quality
        else:
            existing_data[name] = {
                "name": name,
                "category": item["category"],
                "quality": quality,
                "price": price,
                "history": [price],
            }

        # 計算 AI 漲跌預測
        history = existing_data[name]["history"]
        if len(history) >= 2:
            diffs = [
                (history[i] - history[i - 1]) / history[i - 1]
                for i in range(1, len(history))
            ]
            weights = [i + 1 for i in range(len(diffs))]
            weighted_rate = sum(d * w for d, w in zip(diffs, weights)) / sum(
                weights
            )
            predicted_price = round(price * (1 + weighted_rate))
            predicted_rate = round(weighted_rate * 100, 1)
        else:
            predicted_price = price
            predicted_rate = 0.0

        existing_data[name]["predictedPrice"] = predicted_price
        existing_data[name]["predictedRate"] = predicted_rate

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"數據更新完成！目前總物資數：{len(existing_data)}")


if __name__ == "__main__":
    update_dataset()
