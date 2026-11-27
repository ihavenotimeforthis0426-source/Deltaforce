import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup

# 1. 預設備用物資庫（完全保留你原本的設定）
DEFAULT_ITEMS = {
    "曼德爾磚": {
        "name": "曼德爾磚",
        "category": "高價值物品",
        "quality": "red",
        "price": 1850000,
        "history":,
        "predictedPrice": 1850000,
        "predictedRate": 0.0,
    },
    "海洋之淚": {
        "name": "海洋之淚",
        "category": "高價值物品",
        "quality": "red",
        "price": 62000000,
        "history":,
        "predictedPrice": 62000000,
        "predictedRate": 0.0,
    },
    "絕密文件": {
        "name": "絕密文件",
        "category": "高價值物品",
        "quality": "red",
        "price": 3500000,
        "history":,
        "predictedPrice": 3500000,
        "predictedRate": 0.0,
    },
    "通用防彈衣 (6級)": {
        "name": "通用防彈衣 (6級)",
        "category": "護甲裝備",
        "quality": "purple",
        "price": 450000,
        "history":,
        "predictedPrice": 450000,
        "predictedRate": 0.0,
    },
    "戰術頭盔 (6級)": {
        "name": "戰術頭盔 (6級)",
        "category": "護甲裝備",
        "quality": "purple",
        "price": 380000,
        "history":,
        "predictedPrice": 380000,
        "predictedRate": 0.0,
    },
    "M4A1 突擊步槍": {
        "name": "M4A1 突擊步槍",
        "category": "武器配件",
        "quality": "blue",
        "price": 85000,
        "history":,
        "predictedPrice": 85000,
        "predictedRate": 0.0,
    },
}

# 自動對應網站分類到你原本的分類名稱
CATEGORY_MAP = {
    "COLLECTIBLES": "高價值物品",
    "KEYCARDS": "門禁卡",
    "GEAR": "護甲裝備",
    "ATTACHMENTS": "武器配件",
    "FIREARMS": "武器配件",
    "AMMO": "彈藥補給",
    "CONSUMABLES": "消耗品",
    "PROVISIONS": "補給品",
    "MEDICAL": "醫療用品"
}

def parse_price(price_str):
    if not price_str:
        return 0.0
    s = str(price_str).replace(",", "").strip().upper()
    if "M" in s:
        num = re.sub(r"[^\d.]", "", s.split("M")[0])
        return float(num) * 1_000_000 if num else 0.0
    if "萬" in s:
        num = re.sub(r"[^\d.]", "", s.split("萬")[0])
        return float(num) * 10_000 if num else 0.0
    if "K" in s:
        num = re.sub(r"[^\d.]", "", s.split("K")[0])
        return float(num) * 1_000 if num else 0.0
    digits = re.sub(r"[^\d.]", "", s)
    return float(digits) if digits else 0.0

def fetch_auction_data():
    fetched_items = {}
    base_url = "https://deltaforcetools.gg/tw/auction-house"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
    }

    try:
        # 先抓取第 1 頁並自動偵測總頁數（目前約 52 頁）
        resp = requests.get(f"{base_url}?page=1", headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        max_page = 1
        for a in soup.find_all("a", href=True):
            if "page=" in a["href"]:
                try:
                    p = int(a["href"].split("page=").split("&"))
                    if p > max_page:
                        max_page = p
                except ValueError:
                    pass
        print(f"偵測到交易所共有 {max_page} 頁，開始全量爬取...")

        for page_num in range(1, max_page + 1):
            if page_num > 1:
                time.sleep(0.5)  # 禮貌性延遲，防止被鎖 IP
                resp = requests.get(f"{base_url}?page={page_num}", headers=headers, timeout=15)
                if resp.status_code != 200:
                    print(f"第 {page_num} 頁狀態碼異常: {resp.status_code}")
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")

            table = soup.find("table")
            if not table:
                continue

            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) < 8:
                    continue

                # 精準對應表格欄位：cols=物品名稱, cols=目前價格, cols=英文分類
                raw_name = cols.get_text(strip=True)
                clean_name = re.sub(r"\s+", " ", raw_name).strip()
                if not clean_name:
                    continue

                price = parse_price(cols.get_text())
                raw_cat = cols.get_text(strip=True).upper()
                category = CATEGORY_MAP.get(raw_cat, "交易所物資")

                if price > 0:
                    fetched_items[clean_name] = {
                        "name": clean_name,
                        "price": int(price) if price.is_integer() else price,
                        "category": category,
                    }

            if page_num % 10 == 0 or page_num == max_page:
                print(f"進度：已完成 {page_num}/{max_page} 頁 (累計 {len(fetched_items)} 筆)")

    except Exception as e:
        print(f"爬取過程發生錯誤: {e}")

    return list(fetched_items.values())

def update_dataset():
    data_file = "data.json"
    existing_data = {}

    # 1. 讀取你原本的 data.json（完整保留所有歷史價格與舊物資）
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    existing_data = json.loads(content)
        except Exception as e:
            print(f"舊資料讀取失敗，將使用預設初始化: {e}")

    if not existing_data:
        existing_data = DEFAULT_ITEMS.copy()

    # 2. 爬取最新全站數據
    new_items = fetch_auction_data()

    if new_items:
        print(f"成功爬取到 {len(new_items)} 筆即時物資數據！")
        for item in new_items:
            name = item["name"]
            price = item["price"]

            # 保留你原本的特殊高級物資防錯機制
            if "海洋之淚" in name and price < 10000000:
                price = 62000000

            quality = "gold"
            if price >= 10_000_000:
                quality = "red"
            elif price >= 1_000_000:
                quality = "purple"
            elif price < 100_000:
                quality = "blue"

            if name in existing_data:
                # 保留原本的歷史陣列，把新價格加在最後面
                existing_data[name]["history"].append(price)
                if len(existing_data[name]["history"]) > 30:  # 幫你從 20 筆放寬到保留最近 30 筆歷史紀錄
                    existing_data[name]["history"].pop(0)
                existing_data[name]["price"] = price
                existing_data[name]["quality"] = quality
                if item["category"] != "交易所物資":
                    existing_data[name]["category"] = item["category"]
            else:
                existing_data[name] = {
                    "name": name,
                    "category": item["category"],
                    "quality": quality,
                    "price": price,
                    "history": [price],
                }

            # 完整保留你原本的 AI 加權漲幅預測公式
            history = existing_data[name]["history"]
            if len(history) >= 2:
                diffs = [
                    (history[i] - history[i - 1]) / history[i - 1]
                    for i in range(1, len(history))
                    if history[i - 1] > 0
                ]
                if diffs:
                    weights = [i + 1 for i in range(len(diffs))]
                    weighted_rate = sum(d * w for d, w in zip(diffs, weights)) / sum(weights)
                    predicted_price = round(price * (1 + weighted_rate))
                    predicted_rate = round(weighted_rate * 100, 1)
                else:
                    predicted_price = price
                    predicted_rate = 0.0
            else:
                predicted_price = price
                predicted_rate = 0.0

            existing_data[name]["predictedPrice"] = predicted_price
            existing_data[name]["predictedRate"] = predicted_rate
    else:
        print("【提示】線上爬取未獲取到資料，維持現有物資庫。")

    # 3. 寫回你原本的 data.json
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"寫入完成！目前 data.json 共有 {len(existing_data)} 筆完整物資數據。")

if __name__ == "__main__":
    update_dataset()
