import json
import os
import re
import time
from playwright.sync_api import sync_playwright


def fetch_auction_data():
    items = []

    with sync_playwright() as p:
        # 啟動無頭 Chrome 瀏覽器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for page_num in range(1, 11):
            url = f"https://deltaforcetools.gg/tw/auction-house?page={page_num}"
            try:
                # 前往網頁並等待動態 JS 渲染完畢
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # 提取卡片或表格列表元素
                cards = page.query_selector_all(
                    "div[class*='card'], div[class*='item'], tr"
                )

                for card in cards:
                    text = card.inner_text()
                    if not text:
                        continue

                    lines = [
                        line.strip()
                        for line in text.split("\n")
                        if line.strip()
                    ]

                    # 解析名稱與價格數字
                    if len(lines) >= 2:
                        name = lines[0]
                        # 搜尋包含價格的數字（例：$ 150,000 或 150000）
                        price_match = re.search(
                            r"[\$￥]?\s*([0-9,]{3,10})", text
                        )

                        if price_match:
                            raw_price = price_match.group(1).replace(",", "")
                            price = float(raw_price)

                            # 過濾無效資料或不合理低價
                            if price > 50 and len(name) < 30:
                                items.append({
                                    "name": name,
                                    "price": price,
                                    "category": "交易所物資",
                                })

            except Exception as e:
                print(f"抓取第 {page_num} 頁失敗: {e}")

        browser.close()

    # 依照物資名稱進行去重，留存最後抓到的價格
    unique_items = {item["name"]: item for item in items}
    return list(unique_items.values())


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
        print(
            "【保護機制】未成功抓取到真實價格數據，取消覆蓋以保護原資料。"
        )
        return

    print(
        f"成功抓取到 {len(new_items)} 筆真實物資價格！開始計算預測價格..."
    )

    for item in new_items:
        name = item["name"]
        price = item["price"]

        quality = "gold"
        if price >= 1000000:
            quality = "red"
        elif price >= 300000:
            quality = "purple"
        elif price < 100000:
            quality = "blue"

        if name not in existing_data:
            existing_data[name] = {
                "name": name,
                "category": item["category"],
                "quality": quality,
                "history": [price],
            }
        else:
            existing_data[name]["history"].append(price)
            if len(existing_data[name]["history"]) > 20:
                existing_data[name]["history"].pop(0)

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

    print(
        f"數據更新完美完成！目前看板共有 {len(existing_data)} 筆正確物資。"
    )


if __name__ == "__main__":
    update_dataset()
