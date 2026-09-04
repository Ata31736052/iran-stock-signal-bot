import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import os

# ======== تنظیمات تلگرام ========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ================================

# ======== لیست نمادهای بورس ایران ========
SYMBOLS = [
    {"symbol": "خودرو", "isin": "IRO1KHRZ0001"},
    {"symbol": "فولاد", "isin": "IRO1FOLD0001"},
    {"symbol": "شستا", "isin": "IRO1SSTA0001"},
    {"symbol": "پارس", "isin": "IRO1PARS0001"},
    {"symbol": "ملی", "isin": "IRO1MILI0001"},
    {"symbol": "کگل", "isin": "IRO1KGOL0001"},
    {"symbol": "فملی", "isin": "IRO1FMLI0001"},
    {"symbol": "آریا", "isin": "IRO1ARYA0001"},
    {"symbol": "خگستر", "isin": "IRO1KHGS0001"},
    {"symbol": "سایپا", "isin": "IRO1SAIP0001"}
]

TIMEFRAME = "1d"
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
PE_MAX = 15
PROFIT_MIN = 100

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("خطا در ارسال تلگرام:", e)

def get_fundamental_data(symbol, isin):
    try:
        url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{isin}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "pe": data.get("pE", 20),
                "net_profit": data.get("netProfit", 50),
                "eps": data.get("eps", 50)
            }
    except:
        pass
    return {"pe": 20, "net_profit": 50, "eps": 50}

def get_ohlcv(symbol, isin, timeframe="1d", limit=60):
    try:
        url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{isin}/0"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            prices = []
            for item in data.get("closingPriceDailyList", []):
                prices.append({
                    "timestamp": item.get("date"),
                    "open": item.get("priceOpen", 0),
                    "high": item.get("priceHigh", 0),
                    "low": item.get("priceLow", 0),
                    "close": item.get("priceClose", 0),
                    "volume": item.get("volume", 0)
                })
            df = pd.DataFrame(prices)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df
    except Exception as e:
        print(f"خطا در دریافت داده {symbol}:", e)
    
    # داده تستی
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
    return pd.DataFrame({
        "timestamp": dates,
        "open": [15000 + i*10 for i in range(60)],
        "high": [15500 + i*12 for i in range(60)],
        "low": [14800 + i*8 for i in range(60)],
        "close": [15200 + i*11 for i in range(60)],
        "volume": [1000000 + i*1000 for i in range(60)]
    })

def calculate_indicators(df):
    df["rsi"] = ta.rsi(df["close"], length=RSI_PERIOD)
    macd = ta.macd(df["close"])
    df = pd.concat([df, macd], axis=1)
    df["ema9"] = ta.ema(df["close"], length=9)
    df["ema21"] = ta.ema(df["close"], length=21)
    df["ema9_slope"] = df["ema9"].diff()
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(14).mean()
    df["is_green"] = df["close"] > df["open"]
    df["buy_volume"] = df["volume"].where(df["is_green"], 0)
    df["sell_volume"] = df["volume"].where(~df["is_green"], 0)
    recent = df.tail(20)
    total_buy = recent["buy_volume"].sum()
    total_sell = recent["sell_volume"].sum()
    buyer_power = total_buy / (total_buy + total_sell + 1e-9) * 100
    return df, buyer_power

def check_signal(symbol, isin):
    try:
        fundamental = get_fundamental_data(symbol, isin)
        pe = fundamental["pe"]
        net_profit = fundamental["net_profit"]
        eps = fundamental["eps"]
        
        df = get_ohlcv(symbol, isin, TIMEFRAME)
        if df.empty:
            return
        
        df, buyer_power = calculate_indicators(df)
        last = df.iloc[-1]
        
        rsi = last["rsi"]
        macd = last["MACD_12_26_9"]
        macd_signal = last["MACDs_12_26_9"]
        macd_hist = last["MACDh_12_26_9"]
        price = last["close"]
        ema9 = last["ema9"]
        ema21 = last["ema21"]
        ema9_slope = last["ema9_slope"]
        volume_ratio = last["volume_ratio"]
        
        persian_name = {
            "خودرو": "ایران خودرو",
            "فولاد": "ذوب آهن",
            "شستا": "سرمایه‌گذاری تأمین اجتماعی",
            "پارس": "پارس خودرو",
            "ملی": "مس سرچشمه",
            "کگل": "گل گهر",
            "فملی": "فولاد مبارکه",
            "آریا": "آریا",
            "خگستر": "خگستر",
            "سایپا": "سایپا"
        }.get(symbol, symbol)
        
        strong_long = (
            pe < PE_MAX and
            net_profit > PROFIT_MIN and
            rsi < RSI_OVERSOLD and
            macd > macd_signal and
            macd_hist > 0 and
            buyer_power > 55 and
            ema9 > ema21 and
            ema9_slope > 0 and
            volume_ratio > 1.2
        )
        
        if strong_long:
            sl = price * 0.95
            tp = price * 1.10
            message = f"""
🟢 <b>سیگنال قوی خرید (کف تکنیکال + بنیادی)</b>

نماد: <b>{symbol}</b> ({persian_name})
زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}
قیمت: {price:,.0f} ریال

<b>📊 داده‌های بنیادی:</b>
• P/E: {pe:.1f} (حداکثر مجاز: {PE_MAX})
• سود خالص: {net_profit:,.0f} میلیارد تومان
• EPS: {eps:,.0f} ریال

<b>📈 داده‌های تکنیکال:</b>
• RSI: {rsi:.2f}
• MACD: {macd:.2f}
• EMA9: {ema9:.0f} | EMA21: {ema21:.0f}
• قدرت خریداران: {buyer_power:.1f}%

✅ شرایط احراز شده:
✓ P/E پایین
✓ سودآوری بالا
✓ RSI اشباع فروش
✓ MACD صعودی
✓ روند صعودی

🛑 حد ضرر: {sl:,.0f} ریال
🎯 حد سود: {tp:,.0f} ریال
"""
            send_telegram(message)
            print(f"✅ خرید قوی → {symbol}")

    except Exception as e:
        print(f"خطا در {symbol}:", e)

print("🤖 ربات بورس ایران شروع به کار کرد...")
send_telegram("🚀 ربات بورس ایران (تکنیکال + بنیادی) راه‌اندازی شد!")

for item in SYMBOLS:
    check_signal(item["symbol"], item["isin"])

print("✅ بررسی تمام شد.")
