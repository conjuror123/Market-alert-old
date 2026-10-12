"""Futures read as continuous series: when their contract rolls, and which bars
are too thin to be prices.

THE ROLL. Yahoo's continuous series (KC=F, CC=F, ...) is the front contract
until its last trading day and the next one from the session after - measured
on the contracts still listed (2026): coffee moved to December on 2026-09-21,
cocoa on 09-16, cattle to October on 09-01, cotton to October on 07-10, each
the session after that contract's last trading day by the exchange's rule. The
price jumps there by the spread between two contracts, which is not the
market, and it falls in that night's gap, so that gap is left unscored
(jump.returns.overnight_gaps). The rule counts weekdays back from the end of
the month and does not know exchange holidays, which can move the last trading
day one session earlier - so the two sessions from the computed one on are
both left out: one night in fifty or so, five times a year.

THE LIVE BARS are not that series but one contract at a time (front_contract),
rolled on this series' own calendar (SPECS, roll_back) - before first notice,
when the traders move. Its rolls, Yahoo's in the history and a history source's
(ROLLS_PATH) are all left unscored the same way (roll_sessions).

Aluminium (ALI=F) is not here: Yahoo's series follows a monthly contract it
does not roll by any rule the listed contracts show, and the monthly spread is
a few tenths of a percent - below a night's own spread.

THIN BARS. A bar with no or almost no volume is a quote, not a trade: on these
series about one hour in ten has zero volume, and of the moves past six
standard deviations, a third sat on volume under 5% of the series' usual
(coffee's ±12% at 04:00 on 2026-03-30, 04-01 and 04-02, on 15, 34 and 76
contracts, each undone the next hour). jump.quality marks such bars invalid,
which makes them holes, skipped rather than scored.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

MONTH_CODES = "FGHJKMNQUVXZ"

# Per series:
#   listed    the delivery months, and Yahoo's continuous series rolls through
#             all of them on each one's last trading day;
#   ltd_back  that last trading day, as business days before the delivery
#             month's last business day (0 is the last business day itself);
#   held      the months this series holds - the liquid ones (cotton's October
#             trades two to four hours a day in its last weeks, December
#             seventeen);
#   roll_back the business days before the delivery month's first business day
#             on which this series moves to the next held month - five before
#             first notice, when the two contracts trade side by side and
#             Yahoo's series flips between them. None: at the last trading day.
#             Cattle has no first notice but its traders leave the same way:
#             December's volume passed October's on 2026-09-11..16 (October
#             3,097 contracts on 10-07 against December's 18,822), and held to
#             its last day the series sat on a contract hardly trading
#             (October 2025 moved +2.2% on 213 contracts, every other flat).
#   suffix    Yahoo's exchange suffix for a single contract.
# A contract whose last trading day falls before its delivery month counts it
# from an earlier month's end (ltd_months: Brent the second month before, sugar
# the month before), and rolls on business days before it (roll_ltd, in place of
# roll_back). The grains' last trading day is the business day before the 15th of
# the delivery month (ltd_day, in place of ltd_back).
#
# Stage 2's (2026-10-12): each held month and roll set where the volume moves -
# Yahoo's own series came onto the contract held now on the same day: Brent and
# platinum 09-28 (Brent's November last traded 09-30), the Treasuries 08-27,
# wheat 08-12, sugar 09-09 (October last traded 09-30). Yahoo's corn and soybeans
# went from July straight to December and November at July's last trading day,
# past September (and August); held here the same way, rolled before July's
# first notice as wheat is before September's.
SPECS: "dict[str, dict]" = {
    "KC=F": dict(listed="HKNUZ", ltd_back=8, held="HKNUZ", roll_back=12, suffix="NYB"),
    "CC=F": dict(listed="HKNUZ", ltd_back=11, held="HKNUZ", roll_back=15, suffix="NYB"),
    "CT=F": dict(listed="HKNVZ", ltd_back=16, held="HKNZ", roll_back=10, suffix="NYB"),
    "LE=F": dict(listed="GJMQVZ", ltd_back=0, held="GJMQVZ", roll_back=12, suffix="CME"),
    "BZ=F": dict(listed=MONTH_CODES, ltd_months=2, ltd_back=0, held=MONTH_CODES, roll_ltd=3,
                 suffix="NYM"),
    "ZT=F": dict(listed="HMUZ", ltd_back=0, held="HMUZ", roll_back=3, suffix="CBT"),
    "ZN=F": dict(listed="HMUZ", ltd_back=7, held="HMUZ", roll_back=3, suffix="CBT"),
    "ZB=F": dict(listed="HMUZ", ltd_back=7, held="HMUZ", roll_back=3, suffix="CBT"),
    "ZC=F": dict(listed="HKNUZ", ltd_day=15, held="HKNZ", roll_back=14, suffix="CBT"),
    "ZW=F": dict(listed="HKNUZ", ltd_day=15, held="HKNUZ", roll_back=14, suffix="CBT"),
    "ZS=F": dict(listed="FHKNQUX", ltd_day=15, held="FHKNX", roll_back=14, suffix="CBT"),
    "SB=F": dict(listed="HKNV", ltd_months=1, ltd_back=0, held="HKNV", roll_ltd=16, suffix="NYB"),
    "PL=F": dict(listed="FJNV", ltd_back=2, held="FJNV", roll_back=3, suffix="NYM"),
}

# Volume under this share of the series' trailing median is a quote, not a
# trade. The median is of the nonzero volumes among the THIN_WINDOW bars before
# this one - about two months of a ten-hour session.
THIN_SHARE = 0.05
THIN_WINDOW = 500
THIN_MIN_BARS = 50


def is_continuous(ticker: str) -> bool:
    """A continuous futures series, as Yahoo names them."""
    return ticker.endswith("=F")


def _business_days_before(day: date, n: int) -> date:
    while n:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def _month_end(year: int, month: int) -> date:
    end = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    while end.weekday() >= 5:
        end -= timedelta(days=1)
    return end


def _month_start(year: int, month: int) -> date:
    start = date(year, month, 1)
    while start.weekday() >= 5:
        start += timedelta(days=1)
    return start


def _contracts(months: str, first_year: int, last_year: int) -> "list[tuple[int, int, str]]":
    return [(y, MONTH_CODES.index(c) + 1, c) for y in range(first_year, last_year + 1)
            for c in months]


def _last_trading_day(spec: dict, year: int, month: int) -> date:
    """The contract of this delivery month's last trading day, on weekdays."""
    if "ltd_day" in spec:
        return _business_days_before(date(year, month, spec["ltd_day"]), 1)
    back = month - 1 - spec.get("ltd_months", 0)
    return _business_days_before(_month_end(year + back // 12, back % 12 + 1), spec["ltd_back"])


def last_trading_days(ticker: str, first_year: int, last_year: int) -> "list[date]":
    """Each listed contract's last trading day, by the exchange's rule on weekdays."""
    if ticker not in SPECS:
        return []
    spec = SPECS[ticker]
    return [_last_trading_day(spec, y, m)
            for y, m, _ in _contracts(spec["listed"], first_year, last_year)]


def roll_days(ticker: str, first_year: int, last_year: int) -> "list[tuple[str, date]]":
    """(contract symbol, the first day it is front) for each held contract, in
    order: this series' own rolls."""
    spec = SPECS[ticker]
    out = []
    for y, m, code in _contracts(spec["held"], first_year, last_year + 1):
        if "roll_ltd" in spec:
            last = _business_days_before(_last_trading_day(spec, y, m), spec["roll_ltd"])
        elif spec["roll_back"] is None:
            last = _last_trading_day(spec, y, m)
        else:
            last = _business_days_before(_month_start(y, m), spec["roll_back"] + 1)
        out.append((f"{ticker[:-2]}{code}{y % 100:02d}.{spec['suffix']}", last))
    # A contract is front from the day after the previous one's last held day.
    fronts = []
    for k in range(1, len(out)):
        start = out[k - 1][1] + timedelta(days=1)
        while start.weekday() >= 5:
            start += timedelta(days=1)
        fronts.append((out[k][0], start))
    return fronts


# Contract switches of a history source whose roll does not follow this
# series' calendar - Dukascopy's CFDs, located once in their own data when the
# softs' history was built (docs/decisions.md). Their nights are left unscored
# like any roll's.
ROLLS_PATH = os.path.join("data", "jump", "rolls.csv")


def history_rolls(ticker: str, path: "str | None" = None) -> "list[date]":
    path = path or ROLLS_PATH
    if not os.path.exists(path):
        return []
    table = pd.read_csv(path, dtype=str)
    return [date.fromisoformat(d) for d in table.loc[table["ticker"] == ticker, "date"]]


def roll_sessions(ticker: str, session_days) -> "set[str]":
    """The session dates ("YYYY-MM-DD") whose opening gap may hold a roll -
    Yahoo's (its history), this series' own (its live bars) or a history
    source's (ROLLS_PATH): the first two sessions on or after each such day.
    Exchange holidays can move a last trading day one session earlier than the
    weekday count makes it."""
    import bisect

    days = sorted({str(d) for d in session_days})
    if ticker not in SPECS or not days:
        return set()
    first, last = int(days[0][:4]), int(days[-1][:4])
    edges = [ltd + timedelta(days=1)
             for ltd in last_trading_days(ticker, first - 1, last)]
    edges += [start for _, start in roll_days(ticker, first - 1, last)]
    edges += history_rolls(ticker)
    out: "set[str]" = set()
    for edge in edges:
        at = bisect.bisect_left(days, (edge - timedelta(days=1)).isoformat())
        # Only sessions just after the roll: a roll before the stored history
        # began, or across a gap in it, marks nothing.
        out.update(d for d in days[at:at + 2]
                   if date.fromisoformat(d) <= edge + timedelta(days=7))
    return out


def front_contract(ticker: str, today: date) -> "tuple[str, date] | None":
    """The contract this series is on for trading day `today`, and the first
    day it was front. LIVE BARS COME FROM THIS CONTRACT, not from Yahoo's
    continuous series, which mixes in bars of other contracts - 64 hours on
    coffee's since 2024-05 jump past 3% and straight back, against 2 on a single
    contract over the same months. None for a series not rolled here."""
    if ticker not in SPECS:
        return None
    current = None
    for symbol, start in roll_days(ticker, today.year - 2, today.year + 1):
        if start > today:
            break
        current = (symbol, start)
    return current


def thin(volume: pd.Series) -> pd.Series:
    """Per bar, in time order: is its volume under THIN_SHARE of the median of
    the nonzero volumes among the THIN_WINDOW bars before it? A zero is always
    thin. The window ends before the bar, like every window here."""
    v = volume.astype("float64")
    median = (v.where(v > 0).rolling(THIN_WINDOW, min_periods=THIN_MIN_BARS)
              .median().shift(1).ffill())
    return (v <= 0) | (v < THIN_SHARE * median).fillna(False).to_numpy(dtype=bool)


# --- the history import (tools/futures_history.py) -----------------------------
#
# Below the contract held now, a series' history is an archive's continuous
# record: Dukascopy's CFD where it carries the future (one contract at a time,
# each switch once), else Yahoo's continuous series (back 730 days, switching on
# its own days and printing other months around them). Run once per series, on
# import; never in the hourly pass, which would need the bar after the one it
# judges.

# A stray print, judged against the series' own hourly moves: past STRAY_MULT
# times its median absolute hourly move (at least STRAY_FLOOR) and taken back by
# the next bar. Coffee's CFD closed 2018-05-21 at 111.80 from an open of 120.13
# and opened the next session at 119.69 - a -7.2% hour, 20 sigma, that never
# traded; a real last-hour move is followed by a gap that does not undo it
# (cocoa 2024-04-29: +2.8%, then -5.4%).
STRAY_MULT = 8.0
STRAY_FLOOR = 0.002
# An hour past FLIP that the next hour undoes by more than half is another
# contract's print in a continuous series (64 of coffee's hours since 2024-05).
FLIP = 0.03
# A month with under this share of a normal month's bars (the 75th percentile)
# is dropped: Yahoo's cotton held 26-84 bars a month in early 2026 against ~370.
SPARSE_MONTH = 0.5


def _stray_line(frame: pd.DataFrame) -> float:
    return max(STRAY_FLOOR, STRAY_MULT * float(np.log(frame["close"]).diff().abs().median()))


def reset_stray_closes(frame: pd.DataFrame) -> "tuple[pd.DataFrame, int]":
    """Closes past the stray line from their own bar's open, which the next
    bar's open takes back to within a third of the move, set to that next open.
    Returns the frame and the count."""
    out = frame.sort_values("hour_utc").reset_index(drop=True)
    nxt = out["open"].shift(-1)
    move = np.log(out["close"] / out["open"])
    back = np.log(nxt / out["close"])
    stray = (move.abs() > _stray_line(out)) & ((move + back).abs() < move.abs() / 3)
    out.loc[stray, "close"] = nxt[stray]
    out.loc[stray, "low"] = out.loc[stray, ["low", "open", "close"]].min(axis=1)
    out.loc[stray, "high"] = out.loc[stray, ["high", "open", "close"]].max(axis=1)
    return out, int(stray.sum())


def clean_continuous(frame: pd.DataFrame) -> "tuple[pd.DataFrame, int, list]":
    """Yahoo's continuous series with its flipped bars (another month's print,
    FLIP and back) and its sparse months dropped. Returns the frame, the
    flips dropped and the months dropped."""
    out = frame.sort_values("hour_utc").reset_index(drop=True)
    dropped = 0
    while True:
        r = np.log(out["close"]).diff()
        nxt = r.shift(-1)
        flip = (r.abs() > FLIP) & (nxt.abs() > FLIP) & (r * nxt < 0) & \
            ((r + nxt).abs() < r.abs() / 2)
        if not flip.any():
            break
        dropped += int(flip.sum())
        out = out[~flip].reset_index(drop=True)
    month = pd.to_datetime(out["hour_utc"], unit="s", utc=True).dt.strftime("%Y-%m")
    counts = month.value_counts().sort_index()
    full = counts.iloc[1:-1] if len(counts) > 2 else counts          # not the two ends
    sparse = sorted(m for m, n in counts.items()
                    if n < SPARSE_MONTH * full.quantile(0.75) and m in full.index)
    return out[~month.isin(sparse)].reset_index(drop=True), dropped, sparse


# THE ARCHIVE'S OWN SWITCHES. Each is looked for in the business days around
# this series' rolls and each listed contract's last trading day ([day -
# SWITCH_BEFORE, day + SWITCH_AFTER]) - Dukascopy's CFDs switch 2 to 12 business
# days before this series, Yahoo's on its own days, mostly this series' (stage
# 2's, 2026) and a contract's last trading day (corn's and soybeans' July). It
# is the move in the window - an hour's close against the bar before it, a
# night's included - that stands out: SWITCH_CLEAR times the next largest and
# SWITCH_TYPICAL times the series' median. Yahoo switches inside an hour (the
# 10-year 2026-08-27 07:00 UTC opened on September's price and closed on
# December's: -26 bp against the contract's -3); a CFD at a session's start.
# A switch on a session's first bar is a roll night (ROLLS_PATH); one inside a
# session drops that bar, so the next is measured from its own open. Where none
# stands out the whole window is dropped: whichever hour the switch fell on is
# then inside a hole - but for the window of the seam, this series' own roll
# into the contract the store holds above it: that roll's night is already left
# unscored (roll_sessions), and an archive still on the old month up to it
# makes no other step.
SWITCH_BEFORE, SWITCH_AFTER = 15, 3
SWITCH_CLEAR, SWITCH_TYPICAL = 1.8, 5.0


def _business_days_from(day: date, n: int) -> date:
    step = 1 if n >= 0 else -1
    while n:
        day += timedelta(days=step)
        if day.weekday() < 5:
            n -= step
    return day


def switch_windows(ticker: str, first: date, last: date, before: int = SWITCH_BEFORE,
                   after: int = SWITCH_AFTER, rolls_only: bool = False
                   ) -> "list[tuple[date, date]]":
    """[from, to] around each roll of this series and each listed contract's
    last trading day (or its rolls only) between `first` and `last`, merged
    where they overlap."""
    days = [d for _, d in roll_days(ticker, first.year - 1, last.year)]
    if not rolls_only:
        days += last_trading_days(ticker, first.year - 1, last.year + 1)
    spans = sorted((_business_days_from(d, -before), _business_days_from(d, after))
                   for d in set(days) if first <= d <= last)
    out: "list[list[date]]" = []
    for lo, hi in spans:
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(lo, hi) for lo, hi in out]


def locate_switches(frame: pd.DataFrame, ticker: str, template: str, seam: date,
                    before: int = SWITCH_BEFORE, after: int = SWITCH_AFTER,
                    rolls_only: bool = False, nights_only: bool = False,
                    windows: "list[tuple[date, date]] | None" = None
                    ) -> "tuple[pd.DataFrame, list[str], list[tuple[date, date]], list[str]]":
    """The archive's history below the seam with its switches handled: the frame
    without the bars of a switch inside a session and without the windows where
    none stands out; the session dates of switches on a session's first bar
    (roll nights); the windows dropped; a line per window found. `nights_only`:
    a CFD's switch, at a session's start - only the nights are compared, with a
    typical night's move. `windows`: where to look, when the archive does not
    switch near this series' rolls (switch_windows otherwise)."""
    from jump import sessions

    out = frame.sort_values("hour_utc").reset_index(drop=True)
    if out.empty:
        return out, [], [], []
    key = out["hour_utc"].map(lambda h: sessions.session_key(int(h), template))
    first_bar = key.ne(key.shift(1)).to_numpy()
    move = np.log(out["close"] / out["close"].shift(1)).abs()
    if nights_only:
        move = move.where(first_bar)
    typical = float(move.median())
    day = pd.to_datetime(out["hour_utc"], unit="s", utc=True).dt.date
    start, stop = day.iloc[0], day.iloc[-1]
    keep = np.ones(len(out), dtype=bool)
    nights, dropped, found = [], [], []
    if windows is None:
        windows = switch_windows(ticker, start, max(stop, seam), before, after, rolls_only)
    for lo, hi in windows:
        inside = ((day >= lo) & (day <= hi)).to_numpy()
        if not inside.any():
            continue                    # past the archive's end
        w = move[inside].dropna().sort_values(ascending=False)
        if len(w) >= 2 and w.iloc[0] >= SWITCH_CLEAR * w.iloc[1] and \
                w.iloc[0] >= SWITCH_TYPICAL * typical:
            at = int(w.index[0])
            when = pd.Timestamp(int(out.loc[at, "hour_utc"]), unit="s", tz="UTC")
            if first_bar[at] and key.iloc[at] is not None:
                nights.append(key.iloc[at])
                found.append(f"{lo}..{hi}: a night, {key.iloc[at]} ({1e4 * w.iloc[0]:.0f} bp)")
            else:
                keep[at] = False
                found.append(f"{lo}..{hi}: an hour, {when:%Y-%m-%d %H:%M} ({1e4 * w.iloc[0]:.0f} bp)")
        elif not lo <= seam <= hi:
            keep &= ~inside
            dropped.append((lo, hi))
    return out[keep].reset_index(drop=True), nights, dropped, found
