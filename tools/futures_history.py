"""Stage 2's futures: each series' history below the contract it holds now.

    PYTHONPATH=. python -m tools.futures_history TICKER [TICKER ...] [--dry-run]

ABOVE THE SEAM, THE STORE'S OWN. The seam is the session this series rolled into
the contract it holds now (jump.futures.front_contract); from there on the store
is that contract's own bars from Yahoo - what the hourly fetch keeps.

BELOW IT (the user's, 2026-10-12: Dukascopy where it reaches further, else
Yahoo's two years), by series (HISTORY):

- "cfd": Dukascopy's CFD (price_monitor.dukascopy.CFDS: Brent from 2011, the
  30-year bond and soybeans from 2018, platinum from 2021-11), one contract at a
  time; its stray closes reset (futures.reset_stray_closes) and its volume - a tick
  count - scaled month by month to the contract's median, so the thin-bar rule
  reads both alike. Its switches, at a session's start, are looked for among the nights
  in the weeks before each roll, as the softs' were (futures.locate_switches) -
  soybeans' in the last weeks of the months it switches in (CFD_SWITCHES),
  Brent's around each expiry and confirmed against Yahoo's daily series (CONFIRM).
- "continuous": Yahoo's continuous series, back 730 days, its flips and sparse
  months dropped (futures.clean_continuous) - the 2- and 10-year notes, whose
  series switched in 2026 on this one's roll day, inside an hour (the 10-year
  -26 bp at 07:00 UTC 2026-08-27, against hours of 3-5 bp): looked for within a
  business day of each roll. Its corn and sugar print the other month for hours
  around a switch (corn -7.4% and back on 2026-06-25), and a wide window found
  no clear switch in most of the 10-year's and wheat's: dropped half of each.
- "own": the contract held now, back to the first month it traded at least
  OWN_SHARE of its volume as front - corn, wheat and sugar, whose contracts held
  now Yahoo still serves from 2024 and 2025 (Dec corn: 10 contracts an hour in
  2024-Q4, 584 in 2026-Q1, 4,219 as front): one contract, no switch, from about
  2026-01, past the detector's half-year window.

An archive is spliced only if, over the hours both hold since the seam, it passes
the gates every splice passes (jump.backfill.verify_alignment). A switch on a
session's first bar is a roll night, written to data/jump/rolls.csv; one inside a
session drops that bar.

Rewrites the named stores whole, and their rows of rolls.csv. Run once per series,
from the repository root; the bars are committed as any fetch's are. The hourly
fetch keeps the contract held from then on.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from jump import bars, futures, sessions
from jump.backfill import verify_alignment
from jump.basket import load_basket
from price_monitor import dukascopy, yahoo
from price_monitor.models import ExchangeError

HISTORY = {"BZ=F": "cfd", "ZB=F": "cfd", "ZS=F": "cfd", "PL=F": "cfd",
           "ZT=F": "continuous", "ZN=F": "continuous",
           "ZC=F": "own", "ZW=F": "own", "SB=F": "own"}
STAGE_2 = tuple(HISTORY)
# The contract held now, from the first month whose median hourly volume is this
# share of its median as front.
OWN_SHARE = 0.05
# The splice's check: the archive against the contract held now over these last days.
ALIGN_DAYS = 30
CFD_MIN_HOURS = 60
# Where a CFD's first months are not the market: the bond's 2018-Q1 holds 22
# hourly moves past 2% (-19.6% and back on 02-27; a zero on 03-13) against 0-3 a
# quarter after, and its 2018-Q3/Q4 no bars.
CFD_FROM = {"ZB=F": date(2019, 1, 1)}
# A CFD that does not switch near this series' rolls, looked for in the last
# CFD_BEFORE business days of the months it switches in, and CFD_AFTER after:
# soybeans' moves to each of the seven listed months 5 business days before the
# month ends (on its last business day to 2019-07) - against Yahoo's daily series,
# 26 departures of 60-790 bp - while this series rolls mid-month, before November,
# January, March, May and July only.
CFD_SWITCHES = {"ZS=F": "ZGJMNQV"}
CFD_BEFORE, CFD_AFTER = 12, 2
# Brent's CFD moves on ICE's last trading day or the session after - the business
# day before the 15th day before the delivery month to the February 2016
# contract, the last business day two months before it from March 2016 - and
# Brent rolls every month, so a wide window holds the month's news too: the 18
# business days before each roll took 2020-03-09's -24% and 2019-09-16's Abqaiq
# for switches and dropped 3,037 days. Looked for from BRENT_BEFORE business days
# before to BRENT_AFTER after, and confirmed (CONFIRM).
BRENT_BEFORE, BRENT_AFTER = 2, 3
# A switch moves the CFD and not Yahoo's daily series; the market moves both. A
# night is taken for the switch only if the CFD's gap to Yahoo's daily close, at
# the hour the settlement falls in, moves that session the same way by at least
# CONFIRM_SHARE of the night and CONFIRM_BP (Brent's typical day: 20 bp): of the
# 84 nights that stood out, 44 - 2023-04-03's OPEC+ cut, 580 bp, moved the gap 21.
CONFIRM = {"BZ=F": ("America/New_York", 14)}
CONFIRM_SHARE, CONFIRM_BP = 0.5, 80
# Dukascopy's archive answers 503 for minutes at a time: a month it gives up on is
# asked again after MONTH_PAUSE seconds, MONTH_TRIES times; each month fetched is
# kept in --cache, so a run that stops is resumed rather than repeated.
MONTH_TRIES, MONTH_PAUSE = 6, 120
DAY = 86400


def _frame(candles) -> pd.DataFrame:
    return bars.to_hourly(bars.candles_to_frame(candles))


def _cfd_month(symbol: str, start: date, session, cache: "str | None", today: date
               ) -> pd.DataFrame:
    stop = date(start.year + start.month // 12, start.month % 12 + 1, 1)
    path = os.path.join(cache, f"{symbol}-{start:%Y-%m}-ticks.parquet") if cache else None
    if path and os.path.exists(path):
        return pd.read_parquet(path)
    for attempt in range(MONTH_TRIES):
        try:
            frame = _frame(dukascopy.fetch_history(symbol, start, min(stop, today + timedelta(days=1)),
                                                   session, tick_volume=True))
            break
        except ExchangeError as exc:
            if attempt == MONTH_TRIES - 1:
                raise
            print(f"   {exc}; again in {MONTH_PAUSE} s", flush=True)
            time.sleep(MONTH_PAUSE)
    if path and stop <= today:                   # a whole month, which no longer changes
        os.makedirs(cache, exist_ok=True)
        frame.to_parquet(path, index=False)
    return frame


def archive(ticker: str, today: date, session, cache: "str | None" = None
            ) -> "tuple[pd.DataFrame, str]":
    """The archive's continuous record to today, and which archive it is."""
    symbol = dukascopy.CFDS.get(ticker)
    if symbol:
        month = CFD_FROM.get(ticker) or date(*dukascopy.first_month(symbol), 1)
        parts = []
        while month <= today:
            parts.append(_cfd_month(symbol, month, session, cache, today))
            month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
        frame = pd.concat([p for p in parts if not p.empty], ignore_index=True)
        source = "dukascopy"
    else:
        frame = _frame(yahoo.fetch_full_history(ticker, "1h", days=729, session=session))
        source = "yahoo"
    # A price is positive: the bond's CFD printed a zero (2018-03-13).
    prices = frame[["open", "high", "low", "close"]]
    return frame[(prices > 0).all(axis=1)].reset_index(drop=True), source


def cfd_windows(months: str, first: date, last: date) -> "list[tuple[date, date]]":
    """The last CFD_BEFORE business days of each month in `months` (month codes)
    and CFD_AFTER after, between `first` and `last`."""
    out = []
    for year in range(first.year, last.year + 1):
        for code in months:
            month = futures.MONTH_CODES.index(code) + 1
            end = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
            while end.weekday() >= 5:
                end -= timedelta(days=1)
            lo = futures._business_days_from(end, -CFD_BEFORE)
            hi = futures._business_days_from(end, CFD_AFTER)
            if hi >= first and lo <= last:
                out.append((lo, hi))
    return sorted(out)


def brent_last_trading_day(year: int, month: int) -> date:
    """ICE Brent's last trading day for the contract delivering in (year, month)."""
    if (year, month) < (2016, 3):
        day = date(year, month, 1) - timedelta(days=15)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        return futures._business_days_from(day, -1)
    year, month = (year, month - 2) if month > 2 else (year - 1, month + 10)
    day = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def brent_windows(first: date, last: date) -> "list[tuple[date, date]]":
    out = []
    for year in range(first.year, last.year + 2):
        for month in range(1, 13):
            ltd = brent_last_trading_day(year, month)
            lo = futures._business_days_from(ltd, -BRENT_BEFORE)
            hi = futures._business_days_from(ltd, BRENT_AFTER)
            if hi >= first and lo <= last:
                out.append((lo, hi))
    return sorted(out)


def settle_confirm(ticker: str, template: str, record: pd.DataFrame, session):
    """CONFIRM's test: the session's step in the record's gap to Yahoo's daily close."""
    tz, hour = CONFIRM[ticker]
    local = pd.to_datetime(record["hour_utc"], unit="s", utc=True).dt.tz_convert(tz)
    at = record[local.dt.hour == hour]
    keys = at["hour_utc"].map(lambda h: sessions.session_key(int(h), template))
    mine = at.assign(key=keys).dropna(subset=["key"]).groupby("key")["close"].last()
    daily = yahoo.fetch_full_history(ticker, "1d", days=6000, session=session)
    theirs = pd.Series({datetime.fromtimestamp(c.open_time, timezone.utc).date().isoformat(): c.close
                        for c in daily})
    both = pd.concat([mine.rename("mine"), theirs.rename("theirs")], axis=1, join="inner").dropna()
    step = np.log(both["mine"] / both["theirs"]).diff()

    def confirm(key, move: float) -> bool:
        if key is None or key not in step.index or not np.isfinite(step[key]):
            return False
        return bool(np.sign(step[key]) == np.sign(move) and
                    abs(step[key]) >= max(CONFIRM_SHARE * abs(move), CONFIRM_BP / 1e4))
    return confirm


def own_history(contract: pd.DataFrame, seam: int) -> pd.DataFrame:
    """The contract held now, from the first month it traded at least OWN_SHARE
    of its median hourly volume as front."""
    month = pd.to_datetime(contract["hour_utc"], unit="s", utc=True).dt.strftime("%Y-%m")
    front = float(contract.loc[contract["hour_utc"] >= seam, "volume"].median())
    by = contract.assign(month=month).groupby("month")["volume"].median()
    traded = by[by >= OWN_SHARE * front]
    first = traded.index.min() if len(traded) else month.iloc[-1]
    return contract[month >= first].reset_index(drop=True)


def build(asset, today: date, session, bars_dir: str, dry_run: bool,
          cache: "str | None" = None) -> int:
    ticker, template = asset.ticker, asset.session_template
    held, front_day = futures.front_contract(ticker, today)
    seam = sessions.daily_session_open(front_day, template)
    now = int(datetime.now(timezone.utc).timestamp())
    plan = HISTORY[ticker]
    reach = 729 if plan == "own" else (now - seam) / DAY + 1
    contract = _frame(yahoo.fetch_full_history(held, "1h", days=reach, session=session))
    own = contract[contract["hour_utc"] >= seam].reset_index(drop=True)
    if plan == "own":
        store = own_history(contract, seam)
        print(f"{ticker}: {held}, front from {front_day}; its own bars from "
              f"{pd.to_datetime(store['hour_utc'].min(), unit='s'):%Y-%m-%d} "
              f"({len(store)} hours, {len(own)} as front)")
        return _write(asset, store, [], plan, bars_dir, dry_run)
    record, source = archive(ticker, today, session, cache)
    print(f"{ticker}: {held} from {front_day} ({len(own)} hours); {source} "
          f"{len(record)} hours from "
          f"{pd.to_datetime(record['hour_utc'].min(), unit='s'):%Y-%m-%d}")
    if source == "yahoo":
        record, flips, sparse = futures.clean_continuous(record)
        print(f"   {flips} flipped hours dropped; sparse months dropped: {' '.join(sparse) or 'none'}")
    # Over the last ALIGN_DAYS: an archive keeps its own months for a while after
    # this series' roll (Dukascopy's soybeans on another month until about 09).
    # Dukascopy publishes a month's hours once it has ended: a seam in its last
    # weeks (Brent's and platinum's, 09-28) leaves a few days to check, so a CFD
    # needs CFD_MIN_HOURS of them.
    since = max(seam, now - ALIGN_DAYS * DAY)
    check = verify_alignment(record[record["hour_utc"] >= since], own[own["hour_utc"] >= since],
                             min_hours=CFD_MIN_HOURS if source == "dukascopy" else 0)
    print(f"   over the last {ALIGN_DAYS} days: {check['hours']} hours shared, correlation "
          f"{check['correlation']:.4f}, median gap {check['median_bp']:.1f} bp")
    if not check["ok"]:
        print(f"   refused: {check['why']}")
        return 1
    below = record[record["hour_utc"] < seam].reset_index(drop=True)
    if source == "dukascopy":
        # A tick count, whose scale changes over the years (Brent's hour a median
        # 22 million in 2012, a few hundred from 2013-03): each month scaled to the
        # contract's median, so the thin-bar rule reads a month against itself
        # (Brent's 2013-Q2 was 56% thin against 2012's counts).
        month = pd.to_datetime(below["hour_utc"], unit="s").dt.strftime("%Y-%m")
        level = below["volume"].where(below["volume"] > 0).groupby(month).transform("median")
        below["volume"] *= float(own.loc[own["volume"] > 0, "volume"].median()) / level
        below["volume"] = below["volume"].fillna(0.0)
        below, strays = futures.reset_stray_closes(below)
        print(f"   {strays} stray closes set to the next open")
    # A CFD switches at a session's start, 2 to 12 business days before this
    # series rolls (the softs'); Yahoo's notes inside an hour, on this series' roll day.
    how = dict(before=1, after=1, rolls_only=True) if plan == "continuous" else \
        dict(rolls_only=True, nights_only=True)
    first = pd.Timestamp(int(record["hour_utc"].min()), unit="s").date()
    if ticker in CFD_SWITCHES:
        how["windows"] = cfd_windows(CFD_SWITCHES[ticker], first, front_day)
    if ticker == "BZ=F":
        how["windows"] = brent_windows(first, front_day)
    if ticker in CONFIRM:
        how["confirm"] = settle_confirm(ticker, template, record, session)
    below, nights, dropped, found = futures.locate_switches(below, ticker, template, front_day,
                                                            **how)
    for line in found:
        print(f"   switch {line}")
    days = sum((hi - lo).days + 1 for lo, hi in dropped)
    print(f"   {len(dropped)} windows with no clear switch dropped ({days} days): "
          f"{', '.join(f'{lo}..{hi}' for lo, hi in dropped) or 'none'}")
    store = pd.concat([below, own], ignore_index=True)
    print(f"   {len(below)} hours below the seam, {len(own)} above; from "
          f"{pd.to_datetime(store['hour_utc'].min(), unit='s'):%Y-%m-%d}")
    return _write(asset, store, nights, source, bars_dir, dry_run)


def _write(asset, store: pd.DataFrame, nights: list, source: str, bars_dir: str,
           dry_run: bool) -> int:
    ticker = asset.ticker
    if dry_run:
        return 0
    path = bars.store_path(bars_dir, asset.file_stem)
    shutil.rmtree(path, ignore_errors=True)
    bars.merge(path, store)
    table = pd.read_csv(futures.ROLLS_PATH, dtype=str) if os.path.exists(futures.ROLLS_PATH) \
        else pd.DataFrame(columns=["ticker", "date", "source"])
    table = table[table["ticker"] != ticker]
    table = pd.concat([table, pd.DataFrame({"ticker": ticker, "date": nights,
                                            "source": source})], ignore_index=True)
    table.sort_values(["ticker", "date"]).to_csv(futures.ROLLS_PATH, index=False,
                                                 lineterminator="\n")
    print(f"   stored {len(bars.load(path))} hours, {len(nights)} roll nights")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 2's futures' history (rewrites their stores)")
    parser.add_argument("tickers", nargs="+", choices=STAGE_2, metavar="TICKER")
    parser.add_argument("--bars-dir", default=bars.DEFAULT_BARS_DIR)
    parser.add_argument("--dry-run", action="store_true", help="report, write nothing")
    parser.add_argument("--cache", default=None,
                        help="a folder for the archive's whole months, kept between runs")
    args = parser.parse_args(argv)
    basket = {a.ticker: a for a in load_basket().instruments}
    today = datetime.now(timezone.utc).date()
    session = requests.Session()
    failed = [t for t in args.tickers
              if build(basket[t], today, session, args.bars_dir, args.dry_run, args.cache)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
