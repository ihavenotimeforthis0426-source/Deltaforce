import json
import os
import time
import requests


def fetch_auction_data():
    items = []
    # 使用 Delta Force Tools 內部拍賣場 API / 數據請求標頭
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://deltaforcetools.gg/tw/auction-house",
    }

    # 嘗試抓取前 10 頁（可依需求擴充頁數）
    for page in range(1, 11):
        # Delta Force Tools 底層 JSON API 端點
        api_url = f"https://deltaforcetools.gg/api/auction-house?page={page}&limit=50&lang=tw"
        try:
            res = requests.get(api_url, headers=headers, timeout=10)

            # 如果直接請求 API 成功且回傳 JSON
            if res.status_code == 200:
                try:
                    data = res.json()
                    # 處理 API 回傳之物資陣列
                    raw_items = (
                        data.get("data", [])
                        or data.get("items", [])
                        or (data if isinstance(data, list) else [])
                    )

                    for item in raw_items:
                        name = item.get("name") or item.get("itemName")
                        price = item.get("price") or item.get("avgPrice") or 0
                        category = item.get("category") or item.get(
                            "type", "通用物資"
                        )

                        if name and price:
                            items.append({
                                "name": str(name).strip(),
                                "price": float(price),
                                "category": str(category).strip(),
                            })
                except Exception as json_e:
                    print(f"API JSON 解析失敗 (Page {page}): {json_e}")

            time.sleep(0.5)  # 避免過度頻繁請求
        except Exception as e:
            print(f"抓取第 {page} 頁時發生錯誤: {e}")

    return items


def update_dataset():
    data_file = "data.json"
    existing_data = {}

    # 1. 讀取舊有完整資料
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"讀取舊資料失敗: {e}")

    # 2. 爬取最新物資
    new_items = fetch_auction_data()

    # 安全機制：如果 API 未回傳任何資料，堅決不清空原本的 data.json
    if not new_items:
        print(
            "【警告】未抓取到任何新資料！為保護舊有物資數據，已停止覆蓋更新。"
        )
        return

    print(f"成功抓取到 {len(new_items)} 筆最新物資資料！開始更新數據...")

    # 3. 更新與計算 AI 趨勢
    for item in new_items:
        name = item["name"]
        price = item["price"]

        # 根據價格與名稱自動分類品質顏色
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
                "history": [price],
            }
        else:
            # 更新歷史價格 (最多記錄 20 筆)
            existing_data[name]["history"].append(price)
            if len(existing_data[name]["history"]) > 20:
                existing_data[name]["history"].pop(0)

        # AI 時間加權移動平均計算
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

    # 4. 存回 data.json
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(
        f"資料更新完成！目前資料庫共有 {len(existing_data)} 筆物資。"
    )


if __name__ == "__main__":
    update_dataset()
