"""行情、五檔、籌碼、基本面資料來源(皆為公開免費 API)。

- 歷史 K 線 / 公司資訊 / 國際指數:yfinance
- 五檔報價:臺灣證券交易所 MIS(約 5 秒更新)
- 三大法人、融資融券、月營收、EPS、股利:FinMind(免費,可在 secrets 放 FINMIND_TOKEN 提高額度)
"""
import re
import time
import datetime as dt

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from core.config import secret

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
UA = {"User-Agent": "Mozilla/5.0 (compatible; StockApp/1.0)"}

_SYMBOLS: dict[str, str] = {}  # 只快取成功的結果


def clean_code(s: str) -> str:
    return re.sub(r"\.(TW|TWO)$", "", (s or "").strip().upper())


def resolve_symbol(code: str):
    """2330 → 2330.TW;上櫃股票 → .TWO;查不到回傳 None。"""
    code = clean_code(code)
    if not code:
        return None
    if code in _SYMBOLS:
        return _SYMBOLS[code]
    for suffix in (".TW", ".TWO"):
        try:
            if not yf.Ticker(code + suffix).history(period="5d").empty:
                _SYMBOLS[code] = code + suffix
                return _SYMBOLS[code]
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- 價量
@st.cache_data(ttl=300, show_spinner=False)
def get_history(code: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    sym = resolve_symbol(code)
    if not sym:
        return pd.DataFrame()
    try:
        df = yf.Ticker(sym).history(period=period, interval=interval, auto_adjust=False)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def get_info(code: str) -> dict:
    sym = resolve_symbol(code)
    if not sym:
        return {}
    try:
        return yf.Ticker(sym).info or {}
    except Exception:
        return {}


# ---------------------------------------------------------------- FinMind
@st.cache_data(ttl=3600, show_spinner=False)
def finmind(dataset: str, code: str = "", start: str = "", end: str = "") -> pd.DataFrame:
    params = {"dataset": dataset}
    if code:
        params["data_id"] = code
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    token = secret("FINMIND_TOKEN")
    if token:
        params["token"] = token
    try:
        j = requests.get(FINMIND_URL, params=params, headers=UA, timeout=15).json()
        if j.get("status") == 200 and j.get("data"):
            return pd.DataFrame(j["data"])
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def stock_table() -> pd.DataFrame:
    df = finmind("TaiwanStockInfo")
    if df.empty:
        return df
    return df.drop_duplicates("stock_id").set_index("stock_id")


def stock_name(code: str) -> str:
    t = stock_table()
    if not t.empty and code in t.index:
        return str(t.loc[code, "stock_name"])
    return get_info(code).get("shortName") or code


def stock_industry(code: str) -> str:
    t = stock_table()
    if not t.empty and code in t.index:
        return str(t.loc[code, "industry_category"])
    return get_info(code).get("sector") or "未分類"


# ---------------------------------------------------------------- 五檔
def _split(v) -> list[str]:
    return [x for x in str(v or "").split("_") if x]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=4, show_spinner=False)
def get_five_levels(code: str) -> dict:
    sym = resolve_symbol(code)
    if not sym:
        return {"error": "找不到這個代號"}
    ex = "otc" if sym.endswith(".TWO") else "tse"
    try:
        s = requests.Session()
        s.headers.update(UA)
        s.get("https://mis.twse.com.tw/stock/index.jsp", timeout=8)
        r = s.get(
            MIS_URL,
            params={"ex_ch": f"{ex}_{code}.tw", "json": 1, "delay": 0, "_": int(time.time() * 1000)},
            timeout=8,
        )
        arr = r.json().get("msgArray") or []
    except Exception as e:
        return {"error": f"即時報價暫時無法取得({type(e).__name__})"}
    if not arr:
        return {"error": "查無即時資料"}
    m = arr[0]
    return {
        "name": m.get("n"),
        "last": _f(m.get("z")),
        "prev": _f(m.get("y")),
        "open": _f(m.get("o")),
        "high": _f(m.get("h")),
        "low": _f(m.get("l")),
        "volume": _f(m.get("v")),
        "limit_up": _f(m.get("u")),
        "limit_down": _f(m.get("w")),
        "time": m.get("t"),
        "date": m.get("d"),
        "asks": list(zip(map(_f, _split(m.get("a"))), map(_f, _split(m.get("f"))))),
        "bids": list(zip(map(_f, _split(m.get("b"))), map(_f, _split(m.get("g"))))),
    }


# ---------------------------------------------------------------- 籌碼
def get_institutional(code: str, days: int = 60) -> pd.DataFrame:
    """三大法人買賣超(張),欄位:外資 / 投信 / 自營商 / 三大法人。"""
    start = (dt.date.today() - dt.timedelta(days=days * 2)).isoformat()
    df = finmind("TaiwanStockInstitutionalInvestorsBuySell", code, start)
    if df.empty:
        return df
    who = {
        "Foreign_Investor": "外資",
        "Foreign_Dealer_Self": "外資",
        "Investment_Trust": "投信",
        "Dealer_self": "自營商",
        "Dealer_Hedging": "自營商",
    }
    df["who"] = df["name"].map(who)
    df["net"] = (df["buy"] - df["sell"]) / 1000
    p = df.dropna(subset=["who"]).groupby(["date", "who"])["net"].sum().unstack(fill_value=0)
    for col in ("外資", "投信", "自營商"):
        if col not in p:
            p[col] = 0.0
    p["三大法人"] = p[["外資", "投信", "自營商"]].sum(axis=1)
    p.index = pd.to_datetime(p.index)
    return p.sort_index().tail(days)


def get_margin(code: str, days: int = 60) -> pd.DataFrame:
    start = (dt.date.today() - dt.timedelta(days=days * 2)).isoformat()
    df = finmind("TaiwanStockMarginPurchaseShortSale", code, start)
    if df.empty or "MarginPurchaseTodayBalance" not in df:
        return pd.DataFrame()
    out = df[["date", "MarginPurchaseTodayBalance", "ShortSaleTodayBalance"]].copy()
    out.columns = ["date", "融資餘額", "融券餘額"]
    out["date"] = pd.to_datetime(out["date"])
    return out.set_index("date").sort_index().tail(days)


# ---------------------------------------------------------------- 基本面
def get_month_revenue(code: str) -> pd.DataFrame:
    start = (dt.date.today() - dt.timedelta(days=365 * 3)).isoformat()
    df = finmind("TaiwanStockMonthRevenue", code, start)
    if df.empty or "revenue" not in df:
        return pd.DataFrame()
    df = df.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    df["期間"] = df["revenue_year"].astype(str) + "-" + df["revenue_month"].astype(int).astype(str).str.zfill(2)
    df["年增率%"] = df["revenue"].pct_change(12) * 100
    df["營收(億)"] = df["revenue"] / 1e8
    return df[["期間", "營收(億)", "年增率%"]]


def get_eps(code: str) -> pd.DataFrame:
    start = (dt.date.today() - dt.timedelta(days=365 * 3)).isoformat()
    df = finmind("TaiwanStockFinancialStatements", code, start)
    if df.empty or "type" not in df:
        return pd.DataFrame()
    e = df[df["type"] == "EPS"][["date", "value"]].copy()
    e.columns = ["季底", "EPS"]
    return e.sort_values("季底").reset_index(drop=True)


def get_dividend_events(code: str) -> pd.DataFrame:
    """除息 / 發放日。欄位:symbol, kind, date, detail。"""
    df = finmind("TaiwanStockDividend", code, "2024-01-01")
    rows = []
    if not df.empty:
        for _, r in df.iterrows():
            cash = float(r.get("CashEarningsDistribution") or 0) + float(r.get("CashStatutorySurplus") or 0)
            stock = float(r.get("StockEarningsDistribution") or 0) + float(r.get("StockStatutorySurplus") or 0)
            parts = []
            if cash:
                parts.append(f"現金股利 {cash:.2f} 元")
            if stock:
                parts.append(f"股票股利 {stock:.2f} 元")
            detail = "、".join(parts) or "—"
            for col, kind in (
                ("CashExDividendTradingDate", "除息"),
                ("StockExDividendTradingDate", "除權"),
                ("CashDividendPaymentDate", "現金股利發放"),
            ):
                d = pd.to_datetime(r.get(col), errors="coerce")
                if pd.notna(d):
                    rows.append({"symbol": code, "kind": kind, "date": d.date(), "detail": detail})
    return pd.DataFrame(rows, columns=["symbol", "kind", "date", "detail"])


# ---------------------------------------------------------------- 國際
WORLD = {
    "加權指數": "^TWII",
    "S&P 500": "^GSPC",
    "那斯達克": "^IXIC",
    "道瓊工業": "^DJI",
    "費城半導體": "^SOX",
    "日經 225": "^N225",
    "恆生指數": "^HSI",
    "VIX 恐慌指數": "^VIX",
    "美元/台幣": "TWD=X",
    "美國 10 年期殖利率": "^TNX",
    "黃金": "GC=F",
    "原油 WTI": "CL=F",
}


@st.cache_data(ttl=300, show_spinner=False)
def get_world(period: str = "3mo") -> dict:
    try:
        raw = yf.download(
            list(WORLD.values()), period=period, group_by="ticker",
            progress=False, auto_adjust=False, threads=True,
        )
    except Exception:
        return {}
    out = {}
    for name, t in WORLD.items():
        try:
            s = raw[t]["Close"].dropna()
            if len(s) >= 2:
                s.index = pd.to_datetime(s.index).tz_localize(None)
                out[name] = s
        except Exception:
            pass
    return out


@st.cache_data(ttl=900, show_spinner=False)
def get_news(tickers=("^GSPC", "^TWII", "^IXIC"), limit: int = 15) -> list[dict]:
    items, seen = [], set()
    for t in tickers:
        try:
            raw = yf.Ticker(t).news or []
        except Exception:
            raw = []
        for it in raw:
            c = it.get("content", it)
            title = c.get("title")
            if not title or title in seen:
                continue
            seen.add(title)
            url = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link")
            pub = c.get("pubDate") or c.get("providerPublishTime") or ""
            if isinstance(pub, (int, float)):
                pub = dt.datetime.fromtimestamp(pub).strftime("%Y-%m-%d %H:%M")
            source = (c.get("provider") or {}).get("displayName") or c.get("publisher") or ""
            items.append({"title": title, "url": url, "source": source, "time": str(pub)[:16].replace("T", " ")})
    items.sort(key=lambda x: x["time"], reverse=True)
    return items[:limit]
