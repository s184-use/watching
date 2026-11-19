"""技術指標與訊號(只用 pandas / numpy)。"""
import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    c = d["Close"]
    for n in (5, 10, 20, 60):
        d[f"MA{n}"] = c.rolling(n).mean()

    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    rsi[(dn == 0) & (up > 0)] = 100
    d["RSI"] = rsi

    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    d["MACD"] = ema12 - ema26
    d["MACD_signal"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACD_hist"] = d["MACD"] - d["MACD_signal"]

    low9, high9 = d["Low"].rolling(9).min(), d["High"].rolling(9).max()
    rsv = (c - low9) / (high9 - low9).replace(0, np.nan) * 100
    d["K"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d["D"] = d["K"].ewm(alpha=1 / 3, adjust=False).mean()

    sd = c.rolling(20).std()
    d["BB_up"], d["BB_lo"] = d["MA20"] + 2 * sd, d["MA20"] - 2 * sd
    d["VMA20"] = d["Volume"].rolling(20).mean()
    return d


def cross(a: pd.Series, b: pd.Series):
    """回傳 (a 上穿 b, a 下穿 b) 的布林序列。"""
    up = (a > b) & (a.shift(1) <= b.shift(1))
    down = (a < b) & (a.shift(1) >= b.shift(1))
    return up, down


def tech_summary(d: pd.DataFrame) -> dict:
    """技術面分數(0–100)與文字說明。notes = [(偏多/偏空/中性, 說明)]"""
    if d is None or d.empty or len(d) < 65 or d["MA60"].iloc[-1] != d["MA60"].iloc[-1]:
        return {"score": None, "notes": [("neutral", "歷史資料不足,無法計算技術面")], "latest": {}}

    x = d.iloc[-1]
    notes, score = [], 0

    def add(tone, text, pts=0):
        nonlocal score
        score += pts
        notes.append((tone, text))

    if x.Close > x.MA20:
        add("bull", f"股價 {x.Close:.2f} 站上 20 日線 {x.MA20:.2f}", 20)
    else:
        add("bear", f"股價 {x.Close:.2f} 跌破 20 日線 {x.MA20:.2f}")
    if x.Close > x.MA60:
        add("bull", f"股價在 60 日線 {x.MA60:.2f} 之上(中期偏多)", 15)
    else:
        add("bear", f"股價在 60 日線 {x.MA60:.2f} 之下(中期偏弱)")
    if x.MA20 > x.MA60:
        add("bull", "20 日線高於 60 日線(多頭排列)", 15)
    else:
        add("bear", "20 日線低於 60 日線(空頭排列)")
    if x.MACD_hist > 0:
        add("bull", "MACD 柱狀體為正,動能偏多", 15)
    else:
        add("bear", "MACD 柱狀體為負,動能偏空")
    if x.K > x.D:
        add("bull", f"KD 黃金排列(K {x.K:.0f} > D {x.D:.0f})", 10)
    else:
        add("bear", f"KD 死亡排列(K {x.K:.0f} < D {x.D:.0f})")

    r = x.RSI
    if 40 <= r <= 70:
        add("neutral", f"RSI {r:.0f},位於健康區間", 15)
    elif r > 80:
        add("bear", f"RSI {r:.0f},嚴重過熱,留意回檔")
    elif r > 70:
        add("neutral", f"RSI {r:.0f},偏熱", 7)
    elif r < 30:
        add("neutral", f"RSI {r:.0f},超賣,可能有技術反彈")
    else:
        add("neutral", f"RSI {r:.0f},偏弱", 7)

    if len(d) > 6 and d.Close.iloc[-1] > d.Close.iloc[-6]:
        add("bull", "近 5 日股價收高", 10)
    else:
        add("bear", "近 5 日股價收低")

    if x.VMA20 and x.VMA20 == x.VMA20:
        ratio = x.Volume / x.VMA20
        tone = "neutral" if 0.8 <= ratio <= 1.5 else ("bull" if x.Close >= d.Close.iloc[-2] else "bear")
        add(tone, f"成交量為 20 日均量的 {ratio:.1f} 倍")

    # 近 5 根內的交叉訊號
    tail = d.tail(6)
    for label, a, b in (("5 日線 × 20 日線", "MA5", "MA20"), ("MACD × 訊號線", "MACD", "MACD_signal"), ("K × D", "K", "D")):
        u, dn = cross(tail[a], tail[b])
        if u.tail(5).any():
            add("bull", f"近 5 日出現 {label} 黃金交叉")
        elif dn.tail(5).any():
            add("bear", f"近 5 日出現 {label} 死亡交叉")

    latest = {k: float(x[k]) for k in ("Close", "MA5", "MA20", "MA60", "RSI", "K", "D", "MACD", "MACD_hist") if x[k] == x[k]}
    return {"score": score, "notes": notes, "latest": latest}
