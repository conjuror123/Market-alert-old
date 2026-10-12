"""One-off: every source tried on every instrument, and on four not in the basket yet
(the Bund, the gilt, the JGB, TTF) - which can vote, and at what cost.

    python -m tools.source_audit OUT_DIR [--only TICKER,...] [--no-keyed]

Run in GitHub Actions (.github/workflows/source-audit.yml): the keys live in its
secrets, and a source is reached from where the bot runs - one can answer here and
refuse a runner. The store's bars are the checkout's plus the live release's open
months and the not-carried fetch, as the dashboard reads them.

EACH PAIR (instrument x source): the candidates are the source's own names for the
instrument - MarketWatch's by the Dow Jones search, the FT's by its own, the rest by
their rules or from WSCN, SINA, YAHOO below - and each is fetched once over about
PROBE_DAYS and compared with the store on the hours both hold:
  hours, the hourly move's correlation overall and at its weakest local hour (with
  MIN_HOUR_BARS or more), the median level gap, how far back the one request
  reached, how long after an hour's end it is served (delay), the answer's time.
ACCEPTED as the vote itself would judge it (jump.verify.judge): 0.90 or more overall
(ACCEPT, the bar every voter passed so far), and on the store's big moves - BIG or more
of its own robust deviation - the source moves the same way at least REAL_SHARE as far
on CONFIRM of them, with no local hour of BAD_HOUR_MOVES or more confirming under half.
A source on another grid fails the last (the FT's Top 40 filed the close an hour early:
its last two hours 0.70 and 0.05); a quiet hour's noise (a pair's 21:00 UTC, its day's
turn) does not, since no big move falls there. The weakest local hour's correlation is
noted beside.

THE FOUR NOT IN THE BASKET have no store: each is set against one reference
(REFERENCE), and every other candidate against it.

KEYED PROVIDERS are asked once per pair, within what the live run leaves today: Tiingo
at most TIINGO_MAX in the run (the live run asks 27 of its 50 an hour), Twelve Data
outside the hourly batch's minutes at 8 a minute (twelvedata.archive_mode), SiftingIO
a few dozen calls.

Writes matrix.csv (every pair tried) and prints it. Deleted with its workflow once the
voters are wired (the manual's rule).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

import numpy as np
import pandas as pd
import requests

from jump import bars, futures, sessions, verify
from jump.basket import load_basket
from price_monitor import (bitfinex, bitstamp, coinbase, ft, kraken, marketwatch, sifting,
                           sina, tiingo, twelvedata, wallstreetcn, yahoo)

PROBE_DAYS = 30
ACCEPT, MIN_HOUR_BARS, BIG, CONFIRM, BAD_HOUR_MOVES = 0.90, 5, 2.5, 0.90, 3
TIINGO_MAX = 15
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
DJ_SEARCH = "https://services.dowjones.com/autocomplete/data"
WSCN_REAL = "https://api-ddc-wscn.awtmt.com/market/real"

# Wallstreetcn's codes that exist (its snapshot answers for them, 2026-10-12), and
# guesses checked the same way in the run.
WSCN = {
    "^AXJO": ["AU200.OTC"], "^KS11": ["KOSPI.OTC"], "^TWII": ["TWII.OTC", "TW50.OTC"],
    "^HSI": ["HK50.OTC", "HSI.OTC", "HKHSI.HKI"], "000300.SS": ["000300.SS", "CN50.OTC"],
    "^STOXX50E": ["EU50.OTC"], "^FTSE": ["UK100.OTC"], "^SSMI": ["SWI20.OTC", "CH20.OTC"],
    "XU100.IS": ["TR100.OTC"], "^J200.JO": ["SA40.OTC"], "^BVSP": ["IBOV.OTC"],
    "^MXX": ["IPC.OTC"], "BZ=F": ["UKOIL.OTC"], "ZC=F": ["USZC.OTC"], "ZW=F": ["USZW.OTC"],
    "ZS=F": ["USZS.OTC"], "PL=F": ["XPTUSD.OTC"], "SB=F": ["USSB.OTC"], "KC=F": ["USKC.OTC"],
    "LE=F": ["USLC.OTC"], "BTC/USDT": ["BTCUSD.OTC"], "ETH/USDT": ["ETHUSD.OTC"],
    "SPY": ["US500.OTC"], "UNG": ["USNG.OTC"],
    "BUND": ["DE10YR.OTC"], "GILT": ["UK10YR.OTC"], "JGB": ["JP10YR.OTC"],
}
# Sina's global futures (GlobalService.getMink), by the codes its pages use.
SINA = {"BZ=F": ["OIL"], "PL=F": ["XPT"], "ZC=F": ["C"], "ZW=F": ["W"], "ZS=F": ["S"],
        "SB=F": ["SB"], "KC=F": ["KC"], "CC=F": ["CC"], "CT=F": ["CT"], "LE=F": ["LHC", "LC"],
        "XAU/USD": ["XAU", "GC"], "XAG/USD": ["XAG", "SI"], "CAD": ["HG"], "UNG": ["NG"],
        "TTF": ["TTF"], "ZN=F": ["TY"], "ZB=F": ["US"]}
# Yahoo, where it is not the store's own provider.
YAHOO = {"XAU/USD": ["GC=F"], "XAG/USD": ["SI=F"], "AHD": ["ALI=F"], "CAD": ["HG=F"],
         "BTC/USDT": ["BTC-USD"], "ETH/USDT": ["ETH-USD"], "SOL/USDT": ["SOL-USD"],
         "XRP/USDT": ["XRP-USD"], "TTF": ["TTF=F"],
         "JGB": ["2561.T", "2510.T", "1482.T", "2251.T"]}
# Where the four not in the basket are searched, and their reference.
NEW = {"BUND": dict(tz="Europe/Berlin", search=["Euro Bund", "Euro-Bund Future", "Bund"]),
       "GILT": dict(tz="Europe/London", search=["Long Gilt", "Gilt Future"]),
       "JGB": dict(tz="Asia/Tokyo", search=["JGB futures", "Japan Government Bond",
                                            "10-Year JGB", "Japanese Government Bond"]),
       "TTF": dict(tz="Europe/Amsterdam", search=["Dutch TTF", "TTF Natural Gas"])}
REFERENCE = {"BUND": ("marketwatch", "FUTURE/DE/XEUR/FGBLZ26"),
             "GILT": ("marketwatch", "FUTURE/UK/IFEU/RLIZ26"),
             "TTF": ("marketwatch", "FUTURE/UK/NDEX/TFMI00"),
             "JGB": ("marketwatch", "BOND/BX/XTUP/TMBMKJP-10Y")}
# Names the searches know an instrument by, beyond its display and label.
ALIASES = {"^J200.JO": ["FTSE/JSE Top 40"], "^TWII": ["TAIEX", "Taiwan TAIEX"],
           "^KS11": ["KOSPI Composite"], "^AXJO": ["S&P/ASX 200"], "^N225": ["Nikkei 225"],
           "^HSI": ["Hang Seng"], "000300.SS": ["CSI 300"], "^NSEI": ["Nifty 50"],
           "^STOXX50E": ["Euro Stoxx 50"], "^FTSE": ["FTSE 100"], "^SSMI": ["Swiss Market"],
           "XU100.IS": ["BIST 100"], "^TASI.SR": ["Tadawul All Share"],
           "^GSPTSE": ["S&P/TSX Composite"], "^BVSP": ["Bovespa"], "^MXX": ["S&P/BMV IPC"],
           "SND": ["LME Tin"], "NID": ["LME Nickel"], "AHD": ["LME Aluminium"],
           "CAD": ["LME Copper"], "XAU/USD": ["Gold"], "XAG/USD": ["Silver"],
           "BZ=F": ["Brent Crude"], "PL=F": ["Platinum"], "ZC=F": ["Corn"], "ZW=F": ["Wheat"],
           "ZS=F": ["Soybeans"], "SB=F": ["Sugar No. 11"], "KC=F": ["Coffee"], "CC=F": ["Cocoa"],
           "CT=F": ["Cotton"], "LE=F": ["Live Cattle"], "ZT=F": ["2-Year T-Note"],
           "ZN=F": ["10-Year T-Note"], "ZB=F": ["U.S. Treasury Bond"]}
MW_KIND = {"indices": ("INDEX/",), "us_equity": ("FUND/",), "fx": ("CURRENCY/",),
           "futures": ("FUTURE/",), "softs": ("FUTURE/",), "cme_cattle": ("FUTURE/",),
           "lme": ("FUTURE/",), "metals": ("CURRENCY/", "FUTURE/"),
           "crypto_24_7": ("CRYPTOCURRENCY/",), "new": ("FUTURE/", "BOND/", "INDEX/", "FUND/")}
FT_KIND = {"indices": ("Indices",), "us_equity": ("ETFs", "Funds"), "fx": ("Currencies",),
           "futures": ("Commodities",), "softs": ("Commodities",), "cme_cattle": ("Commodities",),
           "lme": ("Commodities",), "metals": ("Commodities", "Currencies"),
           "crypto_24_7": ("Currencies",), "new": ("Commodities", "Indices", "Bonds", "ETFs")}


@dataclass
class Probe:
    source: str
    symbol: str
    fetch: Callable[[], pd.DataFrame]
    keyed: bool = False
    note: str = ""


@dataclass
class Item:
    ticker: str
    name: str
    kind: str
    tz: str
    store: pd.DataFrame
    voters: set = field(default_factory=set)
    own: str = ""


def _frame(candles) -> pd.DataFrame:
    return bars.to_hourly(bars.candles_to_frame(candles))


def _get(session, url, **params):
    return session.get(url, params=params, headers=H, timeout=30)


# --- finding names -------------------------------------------------------------------

def dj_search(session, query: str, kinds) -> "list[str]":
    try:
        got = _get(session, DJ_SEARCH, q=query, need="symbol", excludeExs="xbbg",
                   featureClass="P", type="symbol", count=8).json()
    except Exception:
        return []
    return [s["chartingSymbol"] for s in (got.get("symbols") or [])
            if str(s.get("chartingSymbol", "")).startswith(kinds)]


def ft_search(session, query: str, classes) -> "list[str]":
    try:
        got = session.get(ft.SEARCH, params={"query": query}, headers=ft.HEADERS,
                          timeout=30).json()
    except Exception:
        return []
    return [str(s["xid"]) for s in ((got.get("data") or {}).get("security") or [])
            if s.get("assetClass") in classes and s.get("xid")]


def wscn_existing(session, codes: "list[str]") -> "set[str]":
    if not codes:
        return set()
    try:
        got = _get(session, WSCN_REAL, prod_code=",".join(codes), fields="prod_name").json()
        return set(((got.get("data") or {}).get("snapshot") or {}).keys())
    except Exception:
        return set()


def _queries(item: Item) -> "list[str]":
    if item.kind == "new":
        return NEW[item.ticker]["search"]
    out = ALIASES.get(item.ticker, []) + [item.name]
    if item.kind in ("us_equity", "fx", "crypto_24_7"):
        out.insert(0, item.ticker.replace("/USDT", "").replace("/", ""))
    return list(dict.fromkeys(q for q in out if q))


# --- the probes ------------------------------------------------------------------------

def probes(item: Item, session, keys: dict, now: datetime) -> "list[Probe]":
    t, kind, out = item.ticker, item.kind, []
    days = PROBE_DAYS

    def add(source, symbol, fetch, keyed=False, note=""):
        if source != item.own and not any(p.source == source and p.symbol == symbol for p in out):
            out.append(Probe(source, symbol, fetch, keyed, note))

    # MarketWatch: today's names, then the search's.
    known = []
    if kind == "indices" and t in marketwatch.INDICES:
        known.append(marketwatch.INDICES[t])
    if kind == "futures" and t in marketwatch.FUTURES:
        known.append(marketwatch.FUTURES[t])
    if kind == "us_equity":
        known.append("FUND/US/{}/{}".format(verify.MARKETWATCH_FUND_EXCHANGE.get(t, "ARCX"), t))
    if kind == "fx":
        known.append("CURRENCY/US/XTUP/" + t.replace("/", ""))
    if t == "LE=F":
        known.append(verify.MARKETWATCH_CATTLE)
    if kind == "new":
        known.append(REFERENCE[t][1])
        if t in ("BUND", "GILT"):
            known.append({"BUND": "FUTURE/DE/XEUR/FGBL00", "GILT": "FUTURE/UK/IFEU/RLI00"}[t])
    found = [k for q in _queries(item) for k in dj_search(session, q, MW_KIND[kind])]
    for key in list(dict.fromkeys(known + found))[:6]:
        add("marketwatch", key, lambda k=key: _frame(marketwatch.fetch_hourly(k, session, now)))

    # The FT: today's names, then the search's xids.
    xids = []
    if kind == "indices" and t in ft.INDICES:
        xids.append(ft.INDICES[t])
    if kind == "futures":
        name = verify._ft_future(_asset_of(t))
        if name:
            xids.append(name)
    if t == "KC=F":
        xids.append("KC.1")
    xids += [x for q in _queries(item) for x in ft_search(session, q, FT_KIND[kind])]
    for xid in list(dict.fromkeys(xids))[:4]:
        add("ft", xid, lambda x=xid: _frame(ft.fetch_hourly(x, session, now, days=days)))

    # Wallstreetcn: its pair code, today's names, and the codes that exist.
    codes = []
    if kind in ("fx", "metals"):
        codes.append(wallstreetcn.pair_code(t))
    codes += [wallstreetcn.LME.get(t), wallstreetcn.SOFTS.get(t),
              wallstreetcn.INDICES.get(t)] + WSCN.get(t, [])
    codes = [c for c in dict.fromkeys(codes) if c]
    for code in sorted(wscn_existing(session, codes)):
        add("wallstreetcn", code,
            lambda c=code: _frame(wallstreetcn.fetch_hourly(c, session, now, days=days)))

    # Sina: US funds' half hours, China's indices, its global futures.
    if kind == "us_equity":
        add("sina", t, lambda: _frame(sina.fetch_us_bars(t, session, now)))
    if t in sina.CN_INDICES:
        add("sina", sina.CN_INDICES[t], lambda: _frame(sina.fetch_cn_bars(sina.CN_INDICES[t], session, now)))
    for code in [verify.SINA_FUTURES.get(t), verify.SINA_METALS.get(t),
                 verify.SINA_STAGE2.get(t)] + SINA.get(t, []):
        if code:
            add("sina", code, lambda c=code: _frame(sina.fetch_bars(c, session, now, url=sina.GLOBAL_URL)))

    # Yahoo, where it is not the store's.
    ysyms = list(YAHOO.get(t, []))
    if kind == "us_equity":
        ysyms.append(t)
    if kind == "fx":
        ysyms.append(t.replace("/", "") + "=X")
    for sym in dict.fromkeys(ysyms):
        add("yahoo", sym, lambda s=sym: _frame(yahoo.fetch_full_history(
            s, "1h", days=days, session=session, end=now)))

    # The coins' exchanges.
    if kind == "crypto_24_7":
        coin = t.split("/")[0]
        start, end = now - timedelta(days=days), now.replace(minute=0, second=0, microsecond=0)
        add("coinbase", coinbase.product_for(t),
            lambda: _frame(coinbase.fetch_history(coinbase.product_for(t), start, end, session)))
        add("kraken", kraken.pair_for(t),
            lambda: _frame(kraken.fetch_history(kraken.pair_for(t), start, end, session)))
        add("bitstamp", f"{coin.lower()}usd",
            lambda: _frame(bitstamp.fetch_history(f"{coin.lower()}usd", start, end, session)))
        add("bitfinex", f"t{coin}USD",
            lambda: _frame(bitfinex.fetch_history(f"t{coin}USD", start, end, session)))
        add("alpaca_crypto", f"{coin}/USD", lambda: alpaca_crypto(f"{coin}/USD", start, end, session))

    # Alpaca's tape for the funds.
    if kind == "us_equity" and keys.get("alpaca"):
        add("alpaca_sip", t, lambda: verify.fetch_verifier("alpaca_sip", t, "30min", days, session, now),
            keyed=True)

    # The keyed providers.
    if keys.get("tiingo") and kind in ("us_equity", "fx", "crypto_24_7", "metals"):
        sym = {"crypto_24_7": t.split("/")[0].lower() + "usd"}.get(kind, t)
        add("tiingo", sym, lambda s=sym: tiingo_bars(s, kind, keys["tiingo"], session, now), keyed=True)
    if keys.get("twelvedata") and kind in ("us_equity", "fx", "crypto_24_7", "metals", "indices"):
        sym = {"crypto_24_7": t.split("/")[0] + "/USD"}.get(kind, t.lstrip("^"))
        add("twelvedata", sym, lambda s=sym: _frame(twelvedata.fetch_full_history(
            s, "1h", days, "https://api.twelvedata.com", keys["twelvedata"], session,
            request_delay_seconds=9.0, end=now)), keyed=True)
    if keys.get("sifting") and kind in ("us_equity", "fx", "metals"):
        add("sifting", t, lambda: _frame(sifting.fetch_full_history(
            t, "1h", days, api_key=keys["sifting"], session=session, end=now)), keyed=True)
    if keys.get("sifting") and t == "PL=F":
        add("sifting", "XPT/USD", lambda: sifting_commodity("XPT/USD", keys["sifting"], session, now),
            keyed=True)

    # Korea and Taiwan's own.
    if t == "^KS11":
        add("naver", "KOSPI", lambda: naver_kospi(session, now))
    if t == "^TWII":
        add("twse", "MI_5MINS_INDEX", lambda: twse_index(session, now))
        add("cnyes", "TWS:TSE01:INDEX", lambda: cnyes(session, "TWS:TSE01:INDEX", now))
    return out


_ASSETS = {}


def _asset_of(ticker):
    return _ASSETS[ticker]


# --- fetches no client has yet -----------------------------------------------------------

def alpaca_crypto(symbol, start, end, session) -> pd.DataFrame:
    rows, token = [], None
    for _ in range(20):
        params = dict(symbols=symbol, timeframe="1Hour", limit=10000,
                      start=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      end=end.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if token:
            params["page_token"] = token
        got = _get(session, "https://data.alpaca.markets/v1beta3/crypto/us/bars", **params)
        got.raise_for_status()
        body = got.json()
        rows += (body.get("bars") or {}).get(symbol) or []
        token = body.get("next_page_token")
        if not token:
            break
    return pd.DataFrame([{"hour_utc": int(pd.Timestamp(r["t"]).timestamp()), "open": r["o"],
                          "high": r["h"], "low": r["l"], "close": r["c"], "volume": r["v"]}
                         for r in rows])


def tiingo_bars(symbol, kind, key, session, now) -> pd.DataFrame:
    if kind == "crypto_24_7":
        got = session.get("https://api.tiingo.com/tiingo/crypto/prices",
                          params={"tickers": symbol, "resampleFreq": "1hour", "token": key,
                                  "startDate": (now - timedelta(days=PROBE_DAYS)).strftime("%Y-%m-%d")},
                          timeout=30)
        got.raise_for_status()
        rows = (got.json() or [{}])[0].get("priceData") or []
        return pd.DataFrame([{"hour_utc": int(pd.Timestamp(r["date"]).timestamp()),
                              "open": r["open"], "high": r["high"], "low": r["low"],
                              "close": r["close"], "volume": r.get("volume", 0.0)} for r in rows])
    return _frame(tiingo.fetch_full_history(symbol, "1h", PROBE_DAYS, api_key=key,
                                            session=session, end=now))


def sifting_commodity(symbol, key, session, now) -> pd.DataFrame:
    sifting.COMMODITIES.add(symbol)
    return _frame(sifting.fetch_full_history(symbol, "1h", PROBE_DAYS, api_key=key,
                                             session=session, end=now))


def naver_kospi(session, now) -> pd.DataFrame:
    kst = now.astimezone(timezone(timedelta(hours=9)))
    got = _get(session, "https://api.stock.naver.com/chart/domestic/index/KOSPI/minute",
               startDateTime=(kst - timedelta(days=PROBE_DAYS)).strftime("%Y%m%d0900"),
               endDateTime=kst.strftime("%Y%m%d%H%M"))
    got.raise_for_status()
    m = pd.DataFrame(got.json())
    t = pd.to_datetime(m["localDateTime"], format="%Y%m%d%H%M%S").dt.tz_localize("Asia/Seoul")
    m["hour_utc"] = t.dt.tz_convert("UTC").dt.floor("h").astype("int64") // 10**9
    return m.groupby("hour_utc").agg(open=("openPrice", "first"), high=("highPrice", "max"),
                                     low=("lowPrice", "min"), close=("currentPrice", "last"),
                                     volume=("accumulatedTradingVolume", "last")).reset_index()


def twse_index(session, now) -> pd.DataFrame:
    rows = []
    for back in range(0, 14):
        day = (now - timedelta(days=back)).astimezone(timezone(timedelta(hours=8)))
        if day.weekday() >= 5:
            continue
        got = _get(session, "https://www.twse.com.tw/exchangeReport/MI_5MINS_INDEX",
                   response="json", date=day.strftime("%Y%m%d"))
        got.raise_for_status()
        for r in (got.json().get("data") or []):
            stamp = pd.Timestamp(f"{day:%Y-%m-%d} {r[0]}", tz="Asia/Taipei")
            rows.append({"t": stamp, "close": float(str(r[1]).replace(",", ""))})
        time.sleep(3)
    m = pd.DataFrame(rows)
    m["hour_utc"] = m["t"].dt.tz_convert("UTC").dt.floor("h").astype("int64") // 10**9
    g = m.sort_values("t").groupby("hour_utc")["close"]
    return pd.DataFrame({"open": g.first(), "high": g.max(), "low": g.min(), "close": g.last(),
                         "volume": 0.0}).reset_index()


def cnyes(session, symbol, now) -> pd.DataFrame:
    got = _get(session, "https://ws.api.cnyes.com/ws/api/v1/charting/history", symbol=symbol,
               resolution="60", quote=1, to=int((now - timedelta(days=PROBE_DAYS)).timestamp()),
               **{"from": int(now.timestamp())})
    got.raise_for_status()
    d = got.json().get("data") or {}
    return pd.DataFrame({"hour_utc": d.get("t", []), "open": d.get("o", []), "high": d.get("h", []),
                         "low": d.get("l", []), "close": d.get("c", []), "volume": 0.0})


# --- the comparison ------------------------------------------------------------------------

def compare(frame: pd.DataFrame, store: pd.DataFrame, tz: str) -> dict:
    """The source against the store on the hours both hold: moves between consecutive
    hours only, so a night or a hole is no move."""
    a = frame[["hour_utc", "close"]].dropna()
    b = store[["hour_utc", "close"]].dropna()
    m = a.merge(b, on="hour_utc", suffixes=("_s", "_t")).sort_values("hour_utc")
    m = m.reset_index(drop=True)
    out = {"shared": len(m), "corr": None, "big_moves": None, "confirmed": None,
           "bad_hours": "", "weakest_hour": None, "weakest_corr": None, "gap_bp": None}
    if len(m) < 10:
        return out
    step = (m["hour_utc"].diff() == 3600).to_numpy()
    rs = np.log(m["close_s"]).diff()[step]
    rt = np.log(m["close_t"]).diff()[step]
    out["gap_bp"] = round(float((1e4 * np.log(m["close_s"] / m["close_t"])).abs().median()), 1)
    if len(rs) < 10 or rs.std() == 0 or rt.std() == 0:
        return out
    out["corr"] = round(float(rs.corr(rt)), 3)
    hour = pd.to_datetime(m.loc[step, "hour_utc"], unit="s", utc=True).dt.tz_convert(tz).dt.hour
    per = {int(h): float(rs[idx].corr(rt[idx])) for h, idx in hour.groupby(hour).groups.items()
           if len(idx) >= MIN_HOUR_BARS and rs[idx].std() > 0 and rt[idx].std() > 0}
    if per:
        h = min(per, key=per.get)
        out["weakest_hour"], out["weakest_corr"] = h, round(per[h], 3)
    # The vote's own test on the store's big moves (jump.verify.judge).
    scale = 1.4826 * float((rt - rt.median()).abs().median())
    big = rt.abs() >= BIG * scale if scale > 0 else rt.abs() > 0
    ok = (np.sign(rs) == np.sign(rt)) & (rs.abs() >= verify.REAL_SHARE * rt.abs())
    out["big_moves"] = int(big.sum())
    if big.any():
        out["confirmed"] = round(float(ok[big].mean()), 3)
        bad = []
        for h, idx in hour[big].groupby(hour[big]).groups.items():
            if len(idx) >= BAD_HOUR_MOVES and ok[idx].mean() < 0.5:
                bad.append(f"{int(h):02d}h {int(ok[idx].sum())}/{len(idx)}")
        out["bad_hours"] = " ".join(bad)
    return out


def verdict(row: dict) -> str:
    if row.get("error"):
        return "no answer"
    if not row.get("hours"):
        return "no bars"
    if row.get("corr") is None:
        return "too few shared hours"
    if row["corr"] < ACCEPT:
        return f"below {ACCEPT:.2f}"
    if row.get("bad_hours"):
        return f"another grid: {row['bad_hours']} big moves confirmed"
    big, share = row.get("big_moves") or 0, row.get("confirmed")
    if big >= MIN_HOUR_BARS and share is not None and share < CONFIRM:
        return f"confirms {share:.0%} of {big} big moves"
    return "accepted"


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir")
    parser.add_argument("--only", default="")
    parser.add_argument("--no-keyed", action="store_true")
    parser.add_argument("--bars-dir", default=bars.DEFAULT_BARS_DIR)
    args = parser.parse_args(argv)
    keys = {} if args.no_keyed else {
        "tiingo": os.environ.get("TIINGO_API_KEY", "").strip(),
        "twelvedata": os.environ.get("TWELVEDATA_API_KEY", "").strip(),
        "sifting": os.environ.get("SIFTING_API_KEY", "").strip(),
        "alpaca": os.environ.get("ALPACA_KEY_ID", "").strip()}
    twelvedata.archive_mode = True                # out of the hourly batch's minutes
    from jump.usage import Usage
    usage = Usage()
    session = usage.session("manual")
    now = datetime.now(timezone.utc)
    wanted = {t.strip() for t in args.only.split(",") if t.strip()}

    items = []
    for a in load_basket().instruments:
        _ASSETS[a.ticker] = a
        kind = verify._TICKER_CLASS.get(a.ticker) or verify._CLASS.get(
            a.session_template, a.session_template)
        tz = sessions.DAILY_SESSIONS[a.session_template][0] \
            if a.session_template in sessions.DAILY_SESSIONS else \
            (sessions.EXCHANGES[a.session_template][1]
             if a.session_template in sessions.EXCHANGES else
             ("America/New_York" if a.session_template == "us_equity" else "UTC"))
        store = bars.load(bars.store_path(args.bars_dir, a.file_stem))
        items.append(Item(a.ticker, a.display or a.label or a.ticker, kind, tz, store,
                          {s.name for s in verify.sources_for(a)}, a.fetched_from))
    for t, spec in NEW.items():
        items.append(Item(t, t, "new", spec["tz"], pd.DataFrame(columns=["hour_utc", "close"])))
    if wanted:
        items = [i for i in items if i.ticker in wanted]

    rows, tiingo_used = [], 0
    for item in items:
        if item.kind == "new":
            source, key = REFERENCE[item.ticker]
            try:
                item.store = _frame(marketwatch.fetch_hourly(key, session, now))
            except Exception as exc:
                print(f"{item.ticker}: reference {key} - {exc}", file=sys.stderr)
        for p in probes(item, session, keys, now):
            if p.source == "tiingo":
                if tiingo_used >= TIINGO_MAX:
                    rows.append({"ticker": item.ticker, "source": p.source, "symbol": p.symbol,
                                 "error": "not asked: the run's Tiingo share is spent"})
                    continue
                tiingo_used += 1
            t0 = time.monotonic()
            row = {"ticker": item.ticker, "name": item.name, "kind": item.kind,
                   "source": p.source, "symbol": p.symbol, "keyed": p.keyed,
                   "voter_today": p.source in item.voters}
            try:
                try:
                    frame = p.fetch()
                except Exception as exc:          # a rate limit: once more, after a pause
                    if "429" not in str(exc):
                        raise
                    time.sleep(60)
                    frame = p.fetch()
                row["answer_s"] = round(time.monotonic() - t0, 1)
                frame = frame.dropna(subset=["close"]) if len(frame) else frame
                row["hours"] = int(len(frame))
                if len(frame):
                    first, last = int(frame["hour_utc"].min()), int(frame["hour_utc"].max())
                    row["reach_days"] = round((now.timestamp() - first) / 86400, 1)
                    row["delay_min"] = round((now.timestamp() - last - 3600) / 60)
                    row.update(compare(frame, item.store, item.tz))
            except Exception as exc:
                row["answer_s"] = round(time.monotonic() - t0, 1)
                row["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            row["verdict"] = verdict(row)
            rows.append(row)
            print(json.dumps(row, default=str), flush=True)
            time.sleep(0.5)
    cols = ["ticker", "name", "kind", "source", "symbol", "keyed", "voter_today", "verdict",
            "hours", "shared", "corr", "big_moves", "confirmed", "bad_hours", "weakest_hour",
            "weakest_corr", "gap_bp", "reach_days",
            "delay_min", "answer_s", "error"]
    table = pd.DataFrame(rows).reindex(columns=cols)
    os.makedirs(args.out_dir, exist_ok=True)
    table.to_csv(os.path.join(args.out_dir, "matrix.csv"), index=False)
    print("=== matrix ===")
    print(table.to_csv(index=False))
    print(usage.line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
