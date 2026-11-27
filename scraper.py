import json, os, re, time, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))
CAT_MAP = {
    "COLLECTIBLES": "收集品", "KEYCARDS": "門卡", "GEAR": "裝備",
    "ATTACHMENTS": "配件", "FIREARMS": "槍械", "AMMO": "彈藥",
    "CONSUMABLES": "消耗品", "PROVISIONS": "消耗品", "MEDICAL": "消耗品"
}

def has_cyrillic(t): return bool(re.search(r'[\u0400-\u04FF]', t))

def parse_price(s):
    s = str(s or "").replace(",", "").strip().upper()
    for k, m in [("M", 1_000_000), ("萬", 10_000), ("K", 1_000)]:
        if k in s:
            n = re.sub(r"[^\d.]", "", s.split(k))
            return float(n) * m if n else 0.0
    d = re.sub(r"[^\d.]", "", s)
    return float(d) if d else 0.0

def fetch_all():
    items = {}
    url = "https://deltaforcetools.gg"
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-TW,zh;q=0.9"}
    try:
        soup = BeautifulSoup(requests.get(f"{url}?page=1", headers=headers, timeout=15).text, "html.parser")
        pages = [int(a["href"].split("page=").split("&")) for a in soup.find_all("a", href=True) if "page=" in a["href"] and a["href"].split("page=").split("&").isdigit()]
        max_p = max(pages) if pages else 52
        for p in range(1, max_p + 1):
            if p > 1:
                time.sleep(0.4)
                soup = BeautifulSoup(requests.get(f"{url}?page={p}", headers=headers, timeout=15).text, "html.parser")
            table = soup.find("table")
            if not table: continue
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) < 8: continue
                name = re.sub(r"\s+", " ", cols.get_text(strip=True)).strip()
                if not name or has_cyrillic(name): continue
                price = parse_price(cols.get_text())
                if price > 0:
                    items[name] = {
                        "name": name,
                        "price": int(price) if price.is_integer() else price,
                        "category": CAT_MAP.get(cols.get_text(strip=True).upper(), "收集品")
                    }
    except Exception as e:
        print("Error:", e)
    return list(items.values())

def run():
    now = datetime.now(TW_TZ).strftime("%m/%d %H:%M")
    db = {}
    if os.path.exists("data.json"):
        try:
            raw = json.load(open("data.json", encoding="utf-8"))
            for k, v in raw.items():
                if not has_cyrillic(k):
                    v["history"] = [h if isinstance(h, dict) else {"time": "早期紀錄", "price": x if isinstance(x := h, (int, float)) else 0} for h in v.get("history", [])]
                    db[k] = v
        except Exception: pass

    for item in fetch_all():
        name, price = item["name"], item["price"]
        if "海洋之淚" in name and price < 10000000: price = 62000000
        q = "red" if price >= 10_000_000 else "purple" if price >= 1_000_000 else "blue" if price < 100_000 else "gold"
        rec = {"time": now, "price": price}

        if name in db:
            h = db[name]["history"]
            if h and h[-1]["time"] == now: h[-1]["price"] = price
            else: h.append(rec)
            if len(h) > 30: h.pop(0)
            db[name].update({"price": price, "quality": q, "category": item["category"]})
        else:
            db[name] = {"name": name, "category": item["category"], "quality": q, "price": price, "history": [rec]}

        ps = [x["price"] for x in db[name]["history"]]
        if len(ps) >= 2:
            diffs = [(ps[i] - ps[i-1]) / ps[i-1] for i in range(1, len(ps)) if ps[i-1] > 0]
            w = [i + 1 for i in range(len(diffs))]
            rate = sum(d * wt for d, wt in zip(diffs, w)) / sum(w) if diffs else 0.0
            db[name]["predictedPrice"], db[name]["predictedRate"] = round(price * (1 + rate)), round(rate * 100, 1)
        else:
            db[name]["predictedPrice"], db[name]["predictedRate"] = price, 0.0

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run()
