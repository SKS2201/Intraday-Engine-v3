import os
import datetime
import requests
import pandas as pd

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram secrets not set (TG_BOT_TOKEN / TG_CHAT_ID).")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()

def is_weekday() -> bool:
    return datetime.datetime.now().weekday() <= 4  # Mon=0 ... Sun=6

def fetch_nse_preopen_nifty() -> pd.DataFrame:
    url = "https://www.nseindia.com/api/market-data-pre-open?key=NIFTY"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
        "Connection": "keep-alive",
    }
    s = requests.Session()
    s.get("https://www.nseindia.com", headers=headers, timeout=30)  # warm-up for cookies
    r = s.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()

    rows = []
    for item in j.get("data", []):
        meta = (item or {}).get("metadata", {}) or {}
        sym = meta.get("symbol")
        if not sym:
            continue
        rows.append({
            "symbol": sym,
            "pChange": float(meta.get("pChange") or 0),
            "open": float(meta.get("openPrice") or 0),
            "high": float(meta.get("highPrice") or 0),
            "low": float(meta.get("lowPrice") or 0),
            "prevClose": float(meta.get("previousClose") or 0),
        })
    return pd.DataFrame(rows)

def build_trade_plan(df: pd.DataFrame) -> str:
    top5 = df.sort_values("pChange", ascending=False).head(5)

    msg = "📊 NSE PRE-OPEN TOP 5 (NIFTY) — Intraday Watchlist\n\n"
    for _, r in top5.iterrows():
        entry = round(r["high"] * 1.002, 2)     # Entry slightly above PDH proxy
        sl = round(r["low"] * 0.998, 2)         # SL slightly below PDL proxy
        target = round(entry + (entry - sl) * 2, 2)  # ~2R target

        msg += (
            f"🔹 {r['symbol']} (Pre-open %Chg: {r['pChange']:.2f}%)\n"
            f"Entry > {entry} (15m sustain above PDH)\n"
            f"SL: {sl}\n"
            f"Target: {target}\n\n"
        )

    msg += "⚠️ Only take trade if 15-min candle sustains above Entry.\n"
    msg += "❌ If not sustained → NO TRADE on that stock.\n"
    msg += "📱 Execute manually on Groww."
    return msg

def main() -> None:
    if not is_weekday():
        send_telegram("📴 NO TRADE DAY (Weekend)")
        return

    try:
        df = fetch_nse_preopen_nifty()
    except Exception as e:
        send_telegram(f"⚠️ NSE Pre-open fetch failed\n{e}")
        raise

    if df.empty:
        send_telegram("⚠️ NSE pre-open returned no data. NO TRADE.")
        return

    send_telegram(build_trade_plan(df))
    print("Telegram alert sent")

if __name__ == "__main__":
    main()
