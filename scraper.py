import json
import os
import re
from playwright.sync_api import sync_playwright

# 1. 預設備用物資庫（確保就算爬蟲被網路波動影響，data.json 也絕不為空）
DEFAULT_ITEMS = {
    "曼德爾磚": {
        "name": "曼德爾磚",
        "category": "高價值物品",
        "quality": "red",
        "price": 1850000,
        "history": [1850000],
        "predictedPrice": 1850000,
        "predictedRate": 0.0,
    },
    "海洋之淚": {
        "name": "海洋之淚",
        "category": "高價值物品",
        "quality": "red",
        "price": 62000000,
        "history": [62000000],
        "predictedPrice": 62000000,
        "predictedRate": 0.0,
    },
    "絕密文件": {
        "name": "絕密文件",
        "category": "高價值物品",
        "quality": "red",
        "price": 3500000,
        "history": [3500000],
        "predictedPrice": 3500000,
        "predictedRate": 0.0,
    },
    "通用防彈衣 (6級)": {
        "name": "通用防彈衣 (6級)",
        "category": "護甲裝備",
        "quality": "purple",
        "price": 450000,
        "history": [450000],
        "predictedPrice": 450000,
        "predictedRate": 0.0,
    },
    "戰術頭盔 (6級)": {
        "name": "戰術頭盔 (6級)",
        "category": "護甲裝備",
        "quality": "purple",
        "price": 380000,
        "history": [380000],
        "predictedPrice": 380000,
        "predictedRate": 0.0,
    },
    "M4A1 突擊步槍": {
        "name": "M4A1 突擊步槍",
        "category": "武器配件",
        "quality": "blue",
        "price": 85000,
        "history": [85000],
        "predictedPrice": 85000,
        "predictedRate": 0.0,
    },
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

  try:
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

      for page_num in range(1, 11):
        url = f"https://deltaforcetools.gg/tw/auction-house?page={page_num}"
        try:
          page.goto(url, wait_until="domcontentloaded", timeout=20000)
          page.wait_for_timeout(3000)

          # 抓取頁面所有文字卡片塊
          cards = page.query_selector_all(
              "div[class*='card'], div[class*='item'], tr"
          )
          for card in cards:
            text = card.inner_text()
            if not text:
              continue
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            if len(lines) >= 2:
              name = lines[0]
              # 避開非物資的標頭文字
              if (
                  len(name) > 30
                  or "頁" in name
                  or "價格" in name
                  or "搜尋" in name
              ):
                continue

              price = 0.0
              for line in lines[1:]:
                p_val = parse_price(line)
                if p_val > 0:
                  price = p_val
                  break

              if price > 100:
                clean_name = re.sub(r"\s+", " ", name).strip()
                fetched_items[clean_name] = {
                    "name": clean_name,
                    "price": price,
                    "category": "交易所物資",
                }
        except Exception as e:
          print(f"爬取第 {page_num} 頁出錯: {e}")

      browser.close()
  except Exception as e:
    print(f"Playwright 執行失敗: {e}")

  return list(fetched_items.values())


def update_dataset():
  data_file = "data.json"
  existing_data = {}

  # 1. 讀取舊資料（若存在且非空）
  if os.path.exists(data_file):
    try:
      with open(data_file, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if content:
          existing_data = json.loads(content)
    except Exception as e:
      print(f"舊資料讀取失敗，將使用預設初始化: {e}")

  # 若完全無舊資料，帶入預設基礎資料庫
  if not existing_data:
    existing_data = DEFAULT_ITEMS.copy()

  # 2. 爬取最新數據
  new_items = fetch_auction_data()

  if new_items:
    print(f"成功爬取到 {len(new_items)} 筆即時物資數據！")
    for item in new_items:
      name = item["name"]
      price = item["price"]

      # 特殊高級物資修正海洋之淚金額防錯機制
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

      # 計算 AI 預測
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
  else:
    print("【提示】線上爬取未獲取到資料，維持預設物資庫更新。")

  # 3. 寫回 data.json
  with open(data_file, "w", encoding="utf-8") as f:
    json.dump(existing_data, f, ensure_ascii=False, indent=2)

  print(f"寫入完成！目前共有 {len(existing_data)} 筆物資數據。")


if __name__ == "__main__":
  update_dataset()
