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

ITS SWITCHES. The CFD changes contract on its own day each quarter: the Bund's
in an hour of the business day before its last trading day, the gilt's around
its first notice day. The step is the calendar spread - 50-200 bp in 2018-25, a
few bp in some quarters - so a switch is a large hourly move in those days that
the yield does not explain: the CFD's move between two of the yield's daily
fixings, less what the yield's change makes of it (the Bundesbank's 10-year Bund
yield, fixed near 11:00 Frankfurt; the Bank of England's 10-year gilt yield, near
16:00 London). Neither rolls, as MarketWatch's continuous series does - on the
CFD's own day in some quarters, which hid the switch from a check against it.
Dropped inside a session, a roll night at or outside its start (written to
data/jump/rolls.csv, left unscored by jump.futures.roll_sessions). Where none is
confirmed, the spread was too small to tell, and to matter.

Its stray closes - a close far from both its own bar's open and the next open,
the next bar taking it back - are set to the next open, as stage 2's were. Its
tick counts are not volume: the store holds none, as MarketWatch serves none.

Rewrites the named stores whole, and their rows of rolls.csv. Deleted once its
work is committed (the manual's rule).
"""
from __future__ import annotations

import argparse
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
from price_monitor import dukascopy
from price_monitor.models import Candle, ExchangeError

CFD = {"FGBL=F": "BUNDTREUR", "RLI=F": "UKGILTTRGBP"}
FIRST = date(2018, 5, 1)
# Where each CFD changes contract: the Bund's in an hour of the business day before
# its last trading day, or at that day's open (2018-09-05 -156 bp at 14:00 UTC,
# 2019-06-05 +147 bp, 2021-09-07 -174 bp at the open); the gilt's from three
# business days before its first notice day to the delivery month's first business
# day, in an hour or at the open (2018-08-28 -65 bp at 15:00 London, 2020-05-28
# -82 bp at the open, 2021-12-01 -119 bp at the open, 2025-11-26 -201 bp); looked
# for from SWITCH_DAYS business days before to after each edge (switch_edges).
SWITCH_DAYS = {"FGBL=F": (2, 0), "RLI=F": (3, 2)}
SWITCH_TYPICAL, TOP_HOURS = 4.0, 3
# The daily 10-year yields, and the local hour whose bar closes nearest their
# fixing: there the CFD's daily move follows the yield's most closely, 2018-26
# outside the switch windows (the Bund's 10:00 bar -0.97, its residual 6.8 bp at
# the median deviation; the gilt's 15:00 bar -0.94, 11 bp).
YIELDS = {
    "FGBL=F": ("https://api.statistiken.bundesbank.de/rest/data/BBSIS/"
               "D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A", "Europe/Berlin", 10),
    "RLI=F": ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp",
              "Europe/London", 15)}
# A switch is confirmed where the residual over the fixings around its hour is
# the hour's way, at least CONFIRM_SHARE of it and CONFIRM_BP.
CONFIRM_SHARE, CONFIRM_BP = 0.5, 30.0
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


def this_month(symbol: str, today: date, session, cache: "str | None" = None) -> pd.DataFrame:
    """The month not yet ended, from its daily minute files to yesterday: each
    minute's mid of the bid and ask, folded to the hour. Kept in `cache` as
    SYMBOL-YYYY-MM-days.parquet, and read from there when it is."""
    path = os.path.join(cache, f"{symbol}-{today:%Y-%m}-days.parquet") if cache else None
    if path and os.path.exists(path):
        return pd.read_parquet(path)
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
    frame = _frame(candles)
    if path:
        os.makedirs(cache, exist_ok=True)
        frame.to_parquet(path, index=False)
    return frame


def archive(ticker: str, today: date, session, cache: "str | None") -> pd.DataFrame:
    """The CFD's record to yesterday, priced positive."""
    symbol, month, parts = CFD[ticker], FIRST, []
    while month < today.replace(day=1):
        parts.append(_month(symbol, month, cache))
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    parts.append(this_month(symbol, today, session, cache))
    frame = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    frame = frame.drop_duplicates("hour_utc", keep="last").sort_values("hour_utc")
    prices = frame[["open", "high", "low", "close"]]
    return frame[(prices > 0).all(axis=1)].reset_index(drop=True)


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


def daily_yields(ticker: str, session) -> pd.Series:
    """The 10-year yield in percent, by local date, from 2018."""
    import io

    url = YIELDS[ticker][0]
    if ticker == "FGBL=F":
        text = session.get(url, params={"startPeriod": "2018-01-01", "format": "csv"},
                           timeout=60).text
        rows = [line.split(";") for line in text.lstrip("\ufeff").splitlines()
                if line[:2] == "20"]
        return pd.Series({r[0]: float(r[1].replace(",", ".")) for r in rows
                          if r[1] not in ("", ".")}, dtype=float)
    text = session.get(url, params={"csv.x": "yes", "Datefrom": "01/Jan/2018", "Dateto": "now",
                                    "SeriesCodes": "IUDMNZC", "CSVF": "TN", "UsingCodes": "Y",
                                    "VPD": "Y", "VFD": "N"},
                       headers={"User-Agent": "curl/8.5.0"}, timeout=60).text   # refuses requests
    got = pd.read_csv(io.StringIO(text))
    got["DATE"] = pd.to_datetime(got["DATE"], format="%d %b %Y").dt.date.astype(str)
    return got.set_index("DATE")["IUDMNZC"].astype(float)


def yield_steps(ticker: str, record: pd.DataFrame, yields: pd.Series) -> pd.Series:
    """By each bar's hour_utc, the CFD's log move between the yield's fixings
    around it - the fixing hour's bar close before the bar and the first at or
    after its end - less what the yield's change makes of it (fitted on every
    such interval, the outliers left out)."""
    _, zone, hour = YIELDS[ticker]
    rec = record.sort_values("hour_utc")
    local = pd.to_datetime(rec["hour_utc"], unit="s", utc=True).dt.tz_convert(zone)
    fix = rec.assign(d=local.dt.date.astype(str))[local.dt.hour == hour] \
        .groupby("d").last()
    fix = fix.join(yields.rename("y"), how="inner").dropna(subset=["y"])
    move, dy = np.log(fix["close"]).diff(), fix["y"].diff()
    ok = move.notna() & dy.notna()
    beta = np.polyfit(dy[ok], move[ok], 1)[0]
    res = move - beta * dy
    keep = ok & ((res - res[ok].median()).abs() < 5 * (res[ok] - res[ok].median()).abs().median())
    beta = np.polyfit(dy[keep], move[keep], 1)[0]
    res = (move - beta * dy).to_numpy()
    ends = (fix["hour_utc"] + 3600).to_numpy()
    at = np.searchsorted(ends, rec["hour_utc"].to_numpy() + 3600, side="left")
    inside = (at > 0) & (at < len(ends))
    out = np.full(len(rec), np.nan)
    out[inside] = res[at[inside]]
    return pd.Series(out, index=rec["hour_utc"].astype(int).to_numpy())


def switches(ticker: str, template: str, record: pd.DataFrame, first: date, last: date,
             steps: pd.Series) -> "tuple[pd.DataFrame, list[str], list[str]]":
    """The CFD's switches: in each SWITCH_DAYS window, the largest hourly move
    from the bar before (of the TOP_HOURS largest, at least SWITCH_TYPICAL
    times the record's median) that the yield does not explain - the residual
    over the fixings around it (`steps`, yield_steps, by hour_utc) the same
    way, at least CONFIRM_SHARE of the move and CONFIRM_BP. Inside a session that bar is dropped, so the next
    is measured from its own open; on a session's first bar, or outside the
    session (its step then falls in the next session's night), that night is a
    roll night. Returns the record without the dropped bars, the roll nights
    (session dates) and a line per window."""
    out = record.sort_values("hour_utc").reset_index(drop=True)
    move = np.log(out["close"] / out["close"].shift(1))
    typical = float(move.abs().median())
    key = out["hour_utc"].map(lambda h: sessions.session_key(int(h), template))
    day = pd.to_datetime(out["hour_utc"], unit="s", utc=True).dt.tz_convert(
        sessions.DAILY_SESSIONS[template][0]).dt.date
    before, after = SWITCH_DAYS[ticker]
    keep = np.ones(len(out), dtype=bool)
    nights, lines = [], []
    for edge in switch_edges(ticker, first.year, last.year):
        lo = futures._business_days_before(edge, before) if before else edge
        hi = edge
        for _ in range(after):
            hi += timedelta(days=1)
            while hi.weekday() >= 5:
                hi += timedelta(days=1)
        if hi < first or lo >= last:
            continue
        w = move[((day >= lo) & (day <= hi)).to_numpy()].dropna()
        w = w.reindex(w.abs().sort_values(ascending=False).index)[:TOP_HOURS]
        found = None
        for at, size in w.items():
            if abs(size) < SWITCH_TYPICAL * typical:
                break
            step = steps.get(int(out.loc[at, "hour_utc"]), np.nan)
            if np.isfinite(step) and np.sign(step) == np.sign(size) and \
                    abs(step) >= max(CONFIRM_SHARE * abs(size), CONFIRM_BP / 1e4):
                found = (int(at), float(size), float(step))
                break
        if found is None:
            top = f"{1e4 * float(w.iloc[0]):+.0f} bp" if len(w) else "no bars"
            lines.append(f"{lo}..{hi}: none confirmed (largest {top})")
            continue
        at, size, step = found
        when = pd.Timestamp(int(out.loc[at, "hour_utc"]), unit="s", tz="UTC")
        said = f"{1e4 * size:+.0f} bp at {when:%Y-%m-%d %H:%M} UTC, the residual {1e4 * step:+.0f}"
        if key.iloc[at] is not None and key.iloc[at] == key.iloc[at - 1]:
            keep[at] = False
            lines.append(f"{lo}..{hi}: an hour, {said}: dropped")
            continue
        later = [k for k in key.iloc[at:] if k is not None]
        if later:
            nights.append(later[0])
            lines.append(f"{lo}..{hi}: a night, {later[0]} ({said})")
    return out[keep].reset_index(drop=True), sorted(set(nights)), lines


def switch_edges(ticker: str, first_year: int, last_year: int) -> "list[date]":
    """The days each CFD changes contract near: the Bund's last trading days,
    the gilt's first notice days (two business days before the delivery
    month's first)."""
    if ticker == "FGBL=F":
        return futures.last_trading_days(ticker, first_year, last_year)
    return [futures._business_days_before(futures._month_start(y, m), 2)
            for y in range(first_year, last_year + 1) for m in (3, 6, 9, 12)]


def build(asset, today: date, session, bars_dir: str, dry_run: bool,
          cache: "str | None") -> int:
    ticker, template = asset.ticker, asset.session_template
    own = bars.load(bars.store_path(bars_dir, asset.file_stem))
    if own.empty:
        print(f"{ticker}: no stored bars to splice under")
        return 1
    # The first session with a stored bar: MarketWatch's bars outside it (the
    # gilt's from 01:00 London) are kept, and the session gate drops them.
    seam_day = next(d for d in (sessions.daily_session_of(int(h), template)
                                for h in sorted(own["hour_utc"])) if d is not None)
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
    below = record[record["hour_utc"] < min(seam, int(own["hour_utc"].min()))].copy()
    below["volume"] = 0.0
    below, strays = reset_stray_closes(below)
    print(f"   {strays} stray closes set to the next open")
    first = pd.Timestamp(int(below["hour_utc"].min()), unit="s").date()
    steps = yield_steps(ticker, below, daily_yields(ticker, session))
    below, nights, lines = switches(ticker, template, below, first, seam_day, steps)
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
    parser.add_argument("--this-month", action="store_true",
                        help="only fetch the month not yet ended into --cache")
    args = parser.parse_args(argv)
    today = datetime.now(timezone.utc).date()
    if args.this_month:
        session = requests.Session()
        for ticker in args.tickers:
            print(ticker, len(this_month(CFD[ticker], today, session, args.cache)), flush=True)
        return 0
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
