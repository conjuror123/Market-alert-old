"""One-off: the Bund's and the long gilt's history below MarketWatch's bars.

    PYTHONPATH=. python -m tools.bonds_history TICKER [TICKER ...] [--dry-run] [--cache DIR]

ABOVE THE SEAM, THE STORE'S OWN: MarketWatch's bars of the contract held now, from
its first stored hour (the store seeded 2026-10-13: the Bund from 09-29, the gilt
from 10-05). BELOW IT, Dukascopy's CFD (BUNDTREUR, UKGILTTRGBP, from 2018-05): the
future's own price in thousandths, one contract at a time, each switch once -
its whole months from the monthly files, the month not yet ended from its daily
minute files. Inside the session's hours only (the gate drops the rest).

THE SPLICE is made only if, over the hours both hold since the seam, the CFD
passes the gates every splice passes (jump.backfill.verify_alignment).

ITS SWITCHES. The CFD changes contract on its own day each quarter; the step is
the calendar spread, a few bp now and up to SPREAD_SEEN in the years of negative
yields. Found against MarketWatch's daily continuous series (the settlement):
the CFD's close at the settlement hour over that day's settlement, whose step
from one session to the next is the spread when either changes contract, and
nothing else. In the weeks before each expiry (WINDOW), the session the CFD's
own night carries a step of the ratio at least STEP_BP and half its night is
the CFD's switch: a roll night, written to data/jump/rolls.csv and left
unscored (jump.futures.roll_sessions). A window with no such step is kept as it
is: a switch there moved the price by less than STEP_BP.

Its stray closes - a close far from both its own bar's open and the next open,
the next bar taking it back - are set to the next open, as stage 2's were. Its
tick counts are not volume: the store holds none, as MarketWatch serves none.

Rewrites the named stores whole, and their rows of rolls.csv. Deleted once its
work is committed (the manual's rule).
"""
from __future__ import annotations

import argparse
import json
import lzma
import os
import shutil
import struct
import sys
import time
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from jump import bars, futures, sessions
from jump.backfill import verify_alignment
from jump.basket import load_basket
from price_monitor import dukascopy, marketwatch
from price_monitor.models import Candle, ExchangeError

CFD = {"FGBL=F": "BUNDTREUR", "RLI=F": "UKGILTTRGBP"}
FIRST = date(2018, 5, 1)
# MarketWatch's continuous series, daily, with its settlement's local hour.
DAILY = {"FGBL=F": ("FUTURE/DE/XEUR/FGBL00", "Europe/Berlin", 17),
         "RLI=F": ("FUTURE/UK/IFEU/RLI00", "Europe/London", 16)}
WINDOW_BEFORE, WINDOW_AFTER = 15, 3      # business days around each last trading day
STEP_BP, STEP_SHARE = 8.0, 0.5
STRAY_MULT, STRAY_FLOOR = 8.0, 0.002
MIN_HOURS = 50
MONTH_TRIES, MONTH_PAUSE = 6, 60
DAY = 86400
RECORD = struct.Struct(">iiiiif")


def _frame(candles) -> pd.DataFrame:
    return bars.to_hourly(bars.candles_to_frame(candles))


def _month(symbol: str, start: date, cache: "str | None") -> pd.DataFrame:
    path = os.path.join(cache, f"{symbol}-{start:%Y-%m}.parquet") if cache else None
    if path and os.path.exists(path):
        return pd.read_parquet(path)
    stop = date(start.year + start.month // 12, start.month % 12 + 1, 1)
    for attempt in range(MONTH_TRIES):
        try:
            frame = _frame(dukascopy.fetch_history(symbol, start, stop, None, tick_volume=True))
            break
        except ExchangeError as exc:
            if attempt == MONTH_TRIES - 1:
                raise
            print(f"   {exc}; again in {MONTH_PAUSE} s", flush=True)
            time.sleep(MONTH_PAUSE)
    if path:
        os.makedirs(cache, exist_ok=True)
        frame.to_parquet(path, index=False)
    return frame


def _minute_day(symbol: str, day: date, side: str, session) -> "dict[int, tuple] | None":
    """One day's minute candles of one side, by their epoch second; None when the
    archive has no file for it."""
    url = (f"{dukascopy.BASE_URL}/{symbol}/{day.year}/{day.month - 1:02d}/"
           f"{day.day:02d}/{side}_candles_min_1.bi5")
    for attempt in range(dukascopy.MAX_ATTEMPTS):
        try:
            resp = session.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        except requests.RequestException:
            time.sleep(dukascopy.BACKOFF_SECONDS)
            continue
        if resp.status_code == 404 or (resp.status_code == 200 and not resp.content):
            return None
        if resp.status_code != 200:
            time.sleep(dukascopy.BACKOFF_SECONDS * (attempt + 1))
            continue
        raw = lzma.decompress(resp.content, format=lzma.FORMAT_ALONE)
        base = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
        point = dukascopy.point_for(symbol)
        out = {}
        for k in range(0, len(raw) - RECORD.size + 1, RECORD.size):
            t, o, c, low, h, v = RECORD.unpack_from(raw, k)
            if v > 0:
                out[base + t] = (o * point, h * point, low * point, c * point)
        return out
    raise ExchangeError(f"{symbol} {day}: no answer for its {side} minutes")


def this_month(symbol: str, today: date, session) -> pd.DataFrame:
    """The month not yet ended, from its daily minute files to yesterday: each
    minute's mid of the bid and ask, folded to the hour."""
    candles = []
    day = today.replace(day=1)
    while day < today:
        sides = [_minute_day(symbol, day, s, session) for s in dukascopy.SIDES]
        time.sleep(dukascopy.REQUEST_DELAY_SECONDS)
        if all(sides):
            bid, ask = sides
            for t in sorted(set(bid) & set(ask)):
                o, h, low, c = ((b + a) / 2 for b, a in zip(bid[t], ask[t]))
                candles.append(Candle(open_time=t, open=o, high=h, low=low, close=c,
                                      volume=0.0, close_time=t + 60))
        day += timedelta(days=1)
    return _frame(candles)


def archive(ticker: str, today: date, session, cache: "str | None") -> pd.DataFrame:
    """The CFD's record to yesterday, priced positive."""
    symbol, month, parts = CFD[ticker], FIRST, []
    while month < today.replace(day=1):
        parts.append(_month(symbol, month, cache))
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    parts.append(this_month(symbol, today, session))
    frame = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    frame = frame.drop_duplicates("hour_utc", keep="last").sort_values("hour_utc")
    prices = frame[["open", "high", "low", "close"]]
    return frame[(prices > 0).all(axis=1)].reset_index(drop=True)


def daily_settlements(ticker: str, session) -> pd.Series:
    """MarketWatch's daily continuous closes, by the session date."""
    key = DAILY[ticker][0]
    query = marketwatch._query(key, "P10Y")
    query["Step"] = "P1D"
    got = session.get(marketwatch.URL, params={"json": json.dumps(query),
                                                "ckey": marketwatch.CKEY},
                      headers=marketwatch.HEADERS, timeout=60).json()
    ticks, points = got["TimeInfo"]["Ticks"], got["Series"][0]["DataPoints"]
    return pd.Series({datetime.fromtimestamp(t // 1000, timezone.utc).date().isoformat(): p[3]
                      for t, p in zip(ticks, points) if p and p[3] is not None})


def reset_stray_closes(frame: pd.DataFrame) -> "tuple[pd.DataFrame, int]":
    """Closes past STRAY_MULT times the series' median hourly move from their
    own open, which the next open takes back to within a third, set to that
    next open."""
    out = frame.sort_values("hour_utc").reset_index(drop=True)
    line = max(STRAY_FLOOR, STRAY_MULT * float(np.log(out["close"]).diff().abs().median()))
    nxt = out["open"].shift(-1)
    move = np.log(out["close"] / out["open"])
    back = np.log(nxt / out["close"])
    stray = (move.abs() > line) & ((move + back).abs() < move.abs() / 3)
    out.loc[stray, "close"] = nxt[stray]
    out.loc[stray, "low"] = out.loc[stray, ["low", "open", "close"]].min(axis=1)
    out.loc[stray, "high"] = out.loc[stray, ["high", "open", "close"]].max(axis=1)
    return out, int(stray.sum())


def switches(ticker: str, template: str, record: pd.DataFrame, daily: pd.Series,
             first: date, last: date) -> "tuple[list[str], list[str]]":
    """The CFD's switch nights (session dates), and a line per window."""
    _, zone, hour = DAILY[ticker]
    local = pd.to_datetime(record["hour_utc"], unit="s", utc=True).dt.tz_convert(zone)
    key = record["hour_utc"].map(lambda h: sessions.session_key(int(h), template))
    at = record.assign(key=key)[local.dt.hour == hour].dropna(subset=["key"])
    mine = at.groupby("key")["close"].last()
    both = pd.concat([mine.rename("cfd"), daily.rename("mw")], axis=1, join="inner").dropna()
    step = np.log(both["cfd"] / both["mw"]).diff()
    ordered = record.assign(key=key).dropna(subset=["key"]).sort_values("hour_utc")
    opens = ordered.groupby("key").first()
    closes = ordered.groupby("key")["close"].last()
    night = np.log(opens["open"] / closes.shift(1).reindex(opens.index))
    nights, lines = [], []
    for ltd in futures.last_trading_days(ticker, first.year, last.year):
        lo = futures._business_days_before(ltd, WINDOW_BEFORE)
        hi = ltd + timedelta(days=WINDOW_AFTER + 2)
        if hi < first or lo > last:
            continue
        inside = [k for k in step.index if lo.isoformat() <= k <= hi.isoformat()]
        w = step.reindex(inside).dropna()
        if w.empty:
            lines.append(f"{lo}..{hi}: no settlements")
            continue
        top = w.abs().idxmax()
        size, moved = float(w[top]), float(night.get(top, np.nan))
        if abs(size) * 1e4 >= STEP_BP and np.isfinite(moved) and \
                np.sign(moved) == np.sign(size) and abs(moved) >= STEP_SHARE * abs(size):
            nights.append(top)
            lines.append(f"{lo}..{hi}: a switch, {top} ({1e4 * size:+.0f} bp, the night "
                         f"{1e4 * moved:+.0f})")
        else:
            lines.append(f"{lo}..{hi}: none at {STEP_BP:.0f} bp (largest step "
                         f"{1e4 * size:+.0f} bp at {top})")
    return nights, lines


def build(asset, today: date, session, bars_dir: str, dry_run: bool,
          cache: "str | None") -> int:
    ticker, template = asset.ticker, asset.session_template
    own = bars.load(bars.store_path(bars_dir, asset.file_stem))
    if own.empty:
        print(f"{ticker}: no stored bars to splice under")
        return 1
    seam_day = sessions.daily_session_of(int(own["hour_utc"].min()), template)
    seam = sessions.daily_session_open(seam_day, template)
    record = archive(ticker, today, session, cache)
    print(f"{ticker}: MarketWatch from {seam_day} ({len(own)} hours); Dukascopy "
          f"{len(record)} hours from "
          f"{pd.to_datetime(record['hour_utc'].min(), unit='s'):%Y-%m-%d} to "
          f"{pd.to_datetime(record['hour_utc'].max(), unit='s'):%Y-%m-%d %H:%M}")
    check = verify_alignment(record[record["hour_utc"] >= seam], own, min_hours=MIN_HOURS)
    print(f"   since the seam: {check['hours']} hours shared, correlation "
          f"{check['correlation']:.4f}, median gap {check['median_bp']:.1f} bp")
    if not check["ok"]:
        print(f"   refused: {check['why']}")
        return 1
    below = record[record["hour_utc"] < seam].copy()
    below["volume"] = 0.0
    below, strays = reset_stray_closes(below)
    print(f"   {strays} stray closes set to the next open")
    first = pd.Timestamp(int(below["hour_utc"].min()), unit="s").date()
    nights, lines = switches(ticker, template, below, daily_settlements(ticker, session),
                             first, seam_day)
    for line in lines:
        print(f"   {line}")
    store = pd.concat([below, own], ignore_index=True)
    print(f"   {len(below)} hours below the seam, {len(own)} above, {len(nights)} roll nights")
    if dry_run:
        return 0
    path = bars.store_path(bars_dir, asset.file_stem)
    shutil.rmtree(path, ignore_errors=True)
    bars.merge(path, store)
    table = pd.read_csv(futures.ROLLS_PATH, dtype=str) if os.path.exists(futures.ROLLS_PATH) \
        else pd.DataFrame(columns=["ticker", "date", "source"])
    table = table[table["ticker"] != ticker]
    table = pd.concat([table, pd.DataFrame({"ticker": ticker, "date": nights,
                                            "source": "dukascopy"})], ignore_index=True)
    table.sort_values(["ticker", "date"]).to_csv(futures.ROLLS_PATH, index=False,
                                                 lineterminator="\n")
    print(f"   stored {len(bars.load(path))} hours")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="The Bund's and gilt's history (rewrites their stores)")
    parser.add_argument("tickers", nargs="+", choices=tuple(CFD), metavar="TICKER")
    parser.add_argument("--bars-dir", default=bars.DEFAULT_BARS_DIR)
    parser.add_argument("--dry-run", action="store_true", help="report, write nothing")
    parser.add_argument("--cache", default=None, help="a folder for the CFD's whole months")
    parser.add_argument("--months-of", type=int, default=None,
                        help="only fetch that year's whole months into --cache")
    args = parser.parse_args(argv)
    today = datetime.now(timezone.utc).date()
    if args.months_of:
        for ticker in args.tickers:
            for m in range(1, 13):
                month = date(args.months_of, m, 1)
                if FIRST <= month < today.replace(day=1):
                    print(ticker, month, len(_month(CFD[ticker], month, args.cache)), flush=True)
        return 0
    basket = {a.ticker: a for a in load_basket().instruments}
    session = requests.Session()
    failed = [t for t in args.tickers
              if build(basket[t], today, session, args.bars_dir, args.dry_run, args.cache)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
