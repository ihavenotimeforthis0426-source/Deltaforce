import requests
from bs4 import BeautifulSoup
import json
import os

def fetch_auction_data():
    items = []
    # 爬取 Delta Force Tools 拍賣場前 5 頁（可依需求調整）
    for page in range(1, 6):
        url = f"https://deltaforcetools.gg/tw/auction-house?page={page}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                print(f"Page {page} fetch failed: {res.status_code}")
                continue
            
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.select("table tr")
            if not rows:
                rows = soup.select(".auction-item-row")

            for row in rows:
                cols = [c.text.strip() for c in row.select("td")]
                if len(cols) >= 5:
                    name = cols[0]
                    # 清理價格格式
                    price_str = cols[1].replace(",", "").replace("$", "").replace("哈夫幣", "").strip()
                    try:
                        price = float(price_str)
                    except ValueError:
                        continue
                        
                    category = cols[4] if len(cols) > 4 else "通用"

                    items.append({
                        "name": name,
                        "price": price,
                        "category": category
                    })
        except Exception as e:
            print(f"Error fetching page {page}: {e}")

    return items

def update_dataset():
    data_file = "data.json"
    existing_data = {}
    
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Read existing data error: {e}")

    new_items = fetch_auction_data()
    
    for item in new_items:
        name = item["name"]
        price = item["price"]
        
        # 決定物資品質分類 (預設品級標籤)
        quality = "gold"
        if "紅色" in name or "海洋之淚" in name:
            quality = "red"
        elif "紫色" in name or price < 500000:
            quality = "purple"
        if price < 150000:
            quality = "blue"

        if name not in existing_data:
            existing_data[name] = {
                "name": name,
                "category": item["category"],
                "quality": quality,
                "history": [price]
            }
        else:
            # 追加最新價格（最多保留 20 筆歷史數據）
            existing_data[name]["history"].append(price)
            if len(existing_data[name]["history"]) > 20:
                existing_data[name]["history"].pop(0)

        # AI 趨勢預測算法 (時間加權移動平均)
        history = existing_data[name]["history"]
        if len(history) >= 2:
            diffs = [(history[i] - history[i-1]) / history[i-1] for i in range(1, len(history))]
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

    print("Data successfully updated!")

if __name__ == "__main__":
    update_dataset()
