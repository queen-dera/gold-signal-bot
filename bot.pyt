import os, json, urllib.request
from datetime import datetime, timezone

API_KEY = os.environ["TWELVE_DATA_API_KEY"]
WEBHOOK = os.environ["DISCORD_WEBHOOK"]
FORCE = os.environ.get("FORCE_MESSAGE") == "true"

# If the 1h EMAs are closer than this % of price, the market is "sideways" -> WAIT
MIN_GAP_PCT = 0.05

def ema(values, period):
    k = 2 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out

def fetch(interval):
    url = ("https://api.twelvedata.com/time_series?symbol=XAU/USD"
           f"&interval={interval}&outputsize=120&timezone=UTC&apikey={API_KEY}")
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    if "values" not in data:
        print("Twelve Data error:", data.get("message", data))
        raise SystemExit(1)
    rows = list(reversed(data["values"]))
    return rows[:-1]  # drop the candle that is still forming

def send(msg):
    req = urllib.request.Request(
        WEBHOOK,
        data=json.dumps({"content": msg}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "gold-bot"},
    )
    urllib.request.urlopen(req, timeout=20)
    print("Sent:", msg)

m15 = fetch("15min")
h1 = fetch("1h")

c15 = [float(r["close"]) for r in m15]
c1 = [float(r["close"]) for r in h1]

fast, slow = ema(c15, 9), ema(c15, 21)
h_fast, h_slow = ema(c1, 20), ema(c1, 50)
price = c15[-1]

gap_pct = abs(h_fast[-1] - h_slow[-1]) / c1[-1] * 100
if gap_pct < MIN_GAP_PCT:
    trend = "SIDEWAYS"
elif h_fast[-1] > h_slow[-1]:
    trend = "UP"
else:
    trend = "DOWN"

candle_time = datetime.strptime(
    m15[-1]["datetime"], "%Y-%m-%d %H:%M:%S"
).replace(tzinfo=timezone.utc)
age_min = (datetime.now(timezone.utc) - candle_time).total_seconds() / 60

signal = None
if age_min <= 45:  # ignore stale data (e.g. weekend, market closed)
    crossed_up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
    crossed_down = fast[-2] >= slow[-2] and fast[-1] < slow[-1]
    if crossed_up and trend == "UP":
        signal = "🟢 BUY"
    elif crossed_down and trend == "DOWN":
        signal = "🔴 SELL"

if signal:
    send(f"{signal} XAUUSD at {price:.2f} | 15m EMA 9/21 cross | 1h trend {trend}")
elif FORCE:
    send(f"ℹ️ XAUUSD {price:.2f} | 1h trend {trend} | WAIT, no valid signal (bot is working)")
else:
    print(f"No signal. Trend: {trend}")
