import os, json, urllib.request

API_KEY = os.environ["TWELVE_DATA_API_KEY"]
WEBHOOK = os.environ["DISCORD_WEBHOOK"]
FORCE = os.environ.get("FORCE_MESSAGE") == "true"

def ema(values, period):
    k = 2 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out

url = ("https://api.twelvedata.com/time_series?symbol=XAU/USD"
       f"&interval=15min&outputsize=100&apikey={API_KEY}")
with urllib.request.urlopen(url, timeout=20) as r:
    data = json.load(r)

if "values" not in data:
    print("Twelve Data error:", data.get("message", data))
    raise SystemExit(1)

closes = [float(v["close"]) for v in reversed(data["values"])]
fast, slow = ema(closes, 9), ema(closes, 21)
price = closes[-1]

signal = None
if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
    signal = "🟢 BUY"
elif fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
    signal = "🔴 SELL"

if signal:
    msg = f"{signal} XAUUSD at {price:.2f} (EMA 9/21 cross, 15m)"
elif FORCE:
    msg = f"ℹ️ XAUUSD {price:.2f}: no crossover right now (bot is working)"
else:
    print("No signal")
    raise SystemExit(0)

req = urllib.request.Request(
    WEBHOOK,
    data=json.dumps({"content": msg}).encode(),
    headers={"Content-Type": "application/json", "User-Agent": "gold-bot"},
)
urllib.request.urlopen(req, timeout=20)
print("Sent:", msg)
