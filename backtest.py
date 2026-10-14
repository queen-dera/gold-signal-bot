import os, json, urllib.request
from datetime import datetime, timedelta

API_KEY = os.environ["TWELVE_DATA_API_KEY"]

# KEEP THESE THE SAME AS bot.py
MIN_GAP_PCT = 0.05
ATR_MULT = 1.5
RR = 2
SPREAD = 0.30  # assumed cost per trade in $ of gold price

def ema(values, period):
    k = 2 / (period + 1)
    out = [None] * (period - 1) + [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out

def fetch(interval):
    url = ("https://api.twelvedata.com/time_series?symbol=XAU/USD"
           f"&interval={interval}&outputsize=5000&timezone=UTC&apikey={API_KEY}")
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    if "values" not in data:
        print("Twelve Data error:", data.get("message", data))
        raise SystemExit(1)
    return list(reversed(data["values"]))[:-1]  # closed candles only

m15 = fetch("15min")
h1 = fetch("1h")
fmt = "%Y-%m-%d %H:%M:%S"
t15 = [datetime.strptime(r["datetime"], fmt) for r in m15]
t1 = [datetime.strptime(r["datetime"], fmt) for r in h1]
c15 = [float(r["close"]) for r in m15]
hi15 = [float(r["high"]) for r in m15]
lo15 = [float(r["low"]) for r in m15]
c1 = [float(r["close"]) for r in h1]

f9, s21 = ema(c15, 9), ema(c15, 21)
hf, hs = ema(c1, 20), ema(c1, 50)

def atr_at(i, period=14):
    trs = [max(hi15[k] - lo15[k], abs(hi15[k] - c15[k - 1]), abs(lo15[k] - c15[k - 1]))
           for k in range(i - period + 1, i + 1)]
    return sum(trs) / period

results = []
i, j = 60, -1
while i < len(m15) - 1:
    ref = t15[i] + timedelta(minutes=15)
    while j + 1 < len(t1) and t1[j + 1] + timedelta(minutes=60) <= ref:
        j += 1
    if j < 0 or hs[j] is None:
        i += 1
        continue
    gap = abs(hf[j] - hs[j]) / c1[j] * 100
    trend = "SIDEWAYS" if gap < MIN_GAP_PCT else ("UP" if hf[j] > hs[j] else "DOWN")
    up = f9[i - 1] <= s21[i - 1] and f9[i] > s21[i]
    down = f9[i - 1] >= s21[i - 1] and f9[i] < s21[i]
    side = "BUY" if (up and trend == "UP") else "SELL" if (down and trend == "DOWN") else None
    if not side:
        i += 1
        continue
    entry = c15[i]
    risk = ATR_MULT * atr_at(i)
    sl = entry - risk if side == "BUY" else entry + risk
    tp = entry + RR * risk if side == "BUY" else entry - RR * risk
    outcome, nxt = None, len(m15)
    for k in range(i + 1, len(m15)):
        if side == "BUY":
            hit_sl, hit_tp = lo15[k] <= sl, hi15[k] >= tp
        else:
            hit_sl, hit_tp = hi15[k] >= sl, lo15[k] <= tp
        if hit_sl:  # stop assumed first if both hit
            outcome, nxt = -risk - SPREAD, k + 1
            break
        if hit_tp:
            outcome, nxt = RR * risk - SPREAD, k + 1
            break
    if outcome is not None:
        results.append(outcome)
    i = nxt

n = len(results)
print(f"Data: {t15[0]} to {t15[-1]} UTC ({len(m15)} candles)")
if n == 0:
    print("No completed trades in this period.")
    raise SystemExit(0)
wins = [r for r in results if r > 0]
cum, peak, dd = 0, 0, 0
for r in results:
    cum += r
    peak = max(peak, cum)
    dd = max(dd, peak - cum)
print(f"Trades: {n} | Wins: {len(wins)} | Win rate: {len(wins) / n * 100:.1f}%")
print(f"Net result at 0.01 lot: ${sum(results):.2f}")
print(f"Max drawdown at 0.01 lot: ${dd:.2f}")
print(f"Average trade: ${sum(results) / n:.2f}")
print("Break-even win rate with RR 2 and spread is about 34-36%")
