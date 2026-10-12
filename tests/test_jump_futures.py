from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from jump import bars, futures, returns, sessions
from jump.basket import Asset

NY = ZoneInfo("America/New_York")
HOUR = 3600


def ny(*a):
    return int(datetime(*a, tzinfo=NY).timestamp())


# --- the roll calendar ---------------------------------------------------------

def test_last_trading_days_match_the_rolls_yahoo_made_in_2026():
    # The session after each is when Yahoo's series was seen on the next contract.
    assert date(2026, 9, 18) in futures.last_trading_days("KC=F", 2026, 2026)
    assert date(2026, 9, 15) in futures.last_trading_days("CC=F", 2026, 2026)
    assert date(2026, 7, 9) in futures.last_trading_days("CT=F", 2026, 2026)
    assert date(2026, 8, 31) in futures.last_trading_days("LE=F", 2026, 2026)


def test_the_live_contract_rolls_before_first_notice_and_skips_october_cotton():
    assert futures.front_contract("KC=F", date(2026, 10, 2)) == ("KCZ26.NYB", date(2026, 8, 14))
    assert futures.front_contract("CT=F", date(2026, 10, 2))[0] == "CTZ26.NYB"
    # Cattle rolls when its volume does: December passed October 2026-09-11..16.
    assert futures.front_contract("LE=F", date(2026, 10, 2)) == ("LEZ26.CME", date(2026, 9, 15))
    assert futures.front_contract("ALI=F", date(2026, 10, 2)) is None


def test_stage_twos_last_trading_days_follow_each_exchanges_rule():
    # Brent two months before delivery, sugar the month before, the 10-year seven
    # business days before its month's last, the grains the business day before
    # the 15th (soybeans' November 2026: the 15th a Sunday, so Friday the 13th).
    assert date(2026, 9, 30) in futures.last_trading_days("BZ=F", 2026, 2026)      # BZX26
    assert date(2026, 10, 30) in futures.last_trading_days("BZ=F", 2026, 2026)     # BZZ26
    assert date(2026, 9, 30) in futures.last_trading_days("SB=F", 2026, 2026)      # SBV26
    assert date(2026, 9, 21) in futures.last_trading_days("ZN=F", 2026, 2026)
    assert date(2026, 9, 30) in futures.last_trading_days("ZT=F", 2026, 2026)
    assert date(2026, 11, 13) in futures.last_trading_days("ZS=F", 2026, 2026)
    assert date(2026, 10, 28) in futures.last_trading_days("PL=F", 2026, 2026)


def test_stage_twos_contracts_roll_when_yahoos_series_did_in_2026():
    # Each onto the contract held now on the day Yahoo's own series came onto it;
    # corn and soybeans before July's first notice, past September (and August).
    assert futures.front_contract("BZ=F", date(2026, 10, 12)) == ("BZZ26.NYM", date(2026, 9, 28))
    assert futures.front_contract("ZN=F", date(2026, 10, 12)) == ("ZNZ26.CBT", date(2026, 8, 27))
    assert futures.front_contract("ZW=F", date(2026, 10, 12)) == ("ZWZ26.CBT", date(2026, 8, 12))
    assert futures.front_contract("SB=F", date(2026, 10, 12)) == ("SBH27.NYB", date(2026, 9, 9))
    assert futures.front_contract("PL=F", date(2026, 10, 12)) == ("PLF27.NYM", date(2026, 9, 28))
    assert futures.front_contract("ZC=F", date(2026, 7, 1))[0] == "ZCZ26.CBT"
    assert futures.front_contract("ZS=F", date(2026, 7, 1))[0] == "ZSX26.CBT"
    # Brent holds every month: November until three business days before 09-30.
    assert futures.front_contract("BZ=F", date(2026, 9, 25))[0] == "BZX26.NYM"


def test_both_roll_calendars_leave_their_nights_unscored():
    days = [str(d.date()) for d in pd.bdate_range("2026-08-01", "2026-10-01")]
    rolled = futures.roll_sessions("KC=F", days)
    assert {"2026-08-13", "2026-08-14"} <= rolled          # this series' own roll
    assert {"2026-09-18", "2026-09-21"} <= rolled          # Yahoo's, in the history
    assert "2026-09-01" not in rolled


# --- thin bars -----------------------------------------------------------------

def test_a_bar_without_trading_is_thin_and_the_window_ends_before_it():
    vol = pd.Series([1000.0] * 60 + [0.0, 20.0, 900.0])
    assert list(futures.thin(vol).iloc[-3:]) == [True, True, False]
    # A single huge bar does not make the next one look thin.
    vol = pd.Series([1000.0] * 60 + [10 ** 9, 1000.0])
    assert not futures.thin(vol).iloc[-1]


def _frame(closes, opens=None, start=ny(2026, 3, 2, 9), step=HOUR):
    opens = opens if opens is not None else closes
    return pd.DataFrame({"hour_utc": [start + i * step for i in range(len(closes))],
                         "open": opens, "high": np.maximum(opens, closes),
                         "low": np.minimum(opens, closes), "close": closes,
                         "volume": 100.0, "n_src": 1}).astype(bars.SCHEMA)


# --- daily sessions ---------------------------------------------------------------

def test_an_overnight_session_starts_the_evening_before():
    assert sessions.daily_session_of(ny(2026, 3, 1, 21), "ice_cotton") == date(2026, 3, 2)
    assert sessions.daily_session_of(ny(2026, 3, 2, 14), "ice_cotton") == date(2026, 3, 2)
    assert sessions.daily_session_of(ny(2026, 3, 2, 15), "ice_cotton") is None
    assert sessions.daily_session_of(ny(2026, 3, 6, 21), "ice_cotton") is None   # Friday night


def _future(ticker="KC=F", template="ice_coffee"):
    return Asset(ticker=ticker, source="yahoo", block="agriculture",
                 has_volume=True, tick_size=0.05, session_template=template,
                 fetch_interval="1h", label=ticker, in_basket=True)


def _dividends():
    from jump.corporate_actions import Dividends
    return Dividends(steps={}, splits={}, checked_through={})


def _two_sessions(first_day, second_day, last_hour=12):
    rows = [(ny(*first_day, h), 300, 301, 299, 300, 100.0, 1) for h in range(5, last_hour + 1)]
    # The second session from its first hour: coffee opens 04:15 New York.
    rows += [(ny(*second_day, 4), 309, 310, 308, 309, 100.0, 1),
             (ny(*second_day, 5), 309, 310, 308, 309.5, 100.0, 1)]
    return pd.DataFrame(rows, columns=list(bars.SCHEMA)).astype(bars.SCHEMA)


def test_a_night_ending_within_an_hour_of_the_close_is_scored():
    # Coffee closes 13:30; Yahoo's 13:00 bar is a zero-volume marker.
    out = returns.split_channels(_future(), _two_sessions((2026, 3, 3), (2026, 3, 4)),
                                 dividends=_dividends())
    assert out["gap"].dropna().tolist() == pytest.approx([np.log(309 / 300)])


def test_a_night_that_lost_its_afternoon_is_not():
    out = returns.split_channels(_future(), _two_sessions((2026, 3, 3), (2026, 3, 4), 10),
                                 dividends=_dividends())
    assert out["gap"].isna().all()


def test_a_roll_night_is_not_scored():
    # Coffee's September 2026 contract last traded on the 18th.
    out = returns.split_channels(_future(), _two_sessions((2026, 9, 18), (2026, 9, 21)),
                                 dividends=_dividends())
    assert out["gap"].isna().all()


def test_a_thin_bar_is_invalid_for_a_continuous_future():
    from jump import quality
    frame = _frame([300.0] * 61).assign(volume=[1000.0] * 60 + [0.0])
    reasons = quality.invalid_reasons(_future(), frame)
    assert reasons.iloc[-1] == "volume too thin to be a trade" and (reasons.iloc[:-1] == "").all()


def test_a_history_sources_switch_night_is_a_roll(tmp_path, monkeypatch):
    # Dukascopy's CFD switches contract on days of its own; the list of them
    # leaves those nights unscored like the series' own rolls.
    rolls = tmp_path / "rolls.csv"
    rolls.write_text("ticker,date,source\nKC=F,2021-07-26,dukascopy\n")
    monkeypatch.setattr(futures, "ROLLS_PATH", str(rolls))
    days = ["2021-07-22", "2021-07-23", "2021-07-26", "2021-07-27", "2021-07-28"]
    marked = futures.roll_sessions("KC=F", days)
    monkeypatch.setattr(futures, "ROLLS_PATH", str(tmp_path / "none.csv"))
    without = futures.roll_sessions("KC=F", days)
    assert marked - without == {"2021-07-26", "2021-07-27"}


def test_a_night_ending_on_a_late_first_bar_is_not_scored():
    # F2: with the 04:00 hour missing, the 05:00 bar's open is the night and an
    # hour of trading.
    late = _two_sessions((2026, 3, 3), (2026, 3, 4))
    late = late[late["hour_utc"] != ny(2026, 3, 4, 4)].reset_index(drop=True)
    out = returns.split_channels(_future(), late, dividends=_dividends())
    assert out["gap"].isna().all()


def test_the_ft_names_stage_twos_contracts_as_it_lists_them():
    from price_monitor import ft
    assert ft.futures_symbol("ZCZ26.CBT") == "CZ26"
    assert ft.futures_symbol("ZSX26.CBT") == "SX26"
    assert ft.futures_symbol("PLF27.NYM") == "US@PLF272"
    assert ft.futures_symbol("ZNZ26.CBT") is None and ft.futures_symbol(None) is None


# --- the history import (tools/futures_history.py) --------------------------------

def _hours(closes, start=ny(2026, 3, 2, 9), opens=None):
    opens = opens if opens is not None else closes
    return pd.DataFrame({"hour_utc": [start + i * HOUR for i in range(len(closes))],
                         "open": opens, "high": np.maximum(opens, closes),
                         "low": np.minimum(opens, closes), "close": closes,
                         "volume": 100.0, "n_src": 1}).astype(bars.SCHEMA)


def test_a_stray_close_taken_back_by_the_next_open_is_reset():
    close = list(100.0 + 0.05 * np.sin(np.arange(40)))
    frame = _hours(close)
    frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    frame.loc[20, "close"] = 93.0              # -7%, and the next bar opens back
    frame.loc[30, "close"] = 103.0             # +3%, and the next bar goes on
    frame.loc[31, "open"] = 104.0
    out, n = futures.reset_stray_closes(frame)
    assert n == 1
    assert out.loc[20, "close"] == frame.loc[21, "open"]
    assert out.loc[20, "low"] <= out.loc[20, "close"]
    assert out.loc[30, "close"] == 103.0


def test_another_months_print_is_dropped_from_the_continuous_series():
    out, flips, sparse = futures.clean_continuous(
        _hours([300.0, 301.0, 285.0, 301.5, 302.0, 302.5]))       # 285: there and back
    assert flips == 1 and 285.0 not in list(out["close"]) and sparse == []


def test_a_month_with_under_half_a_normal_months_hours_is_dropped():
    full = [ny(2026, m, d, 9) for m in (1, 2, 3, 4, 5) for d in range(2, 28)]
    sparse = [ny(2026, 6, d, 9) for d in (2, 3)]
    tail = [ny(2026, 7, d, 9) for d in range(2, 28)]
    stamps = full + sparse + tail
    out, _, months = futures.clean_continuous(_hours([300.0] * len(stamps)).assign(hour_utc=stamps))
    assert months == ["2026-06"] and len(out) == len(stamps) - 2


def _rates(steps):
    """The 10-year's hours, 2026-08-03 to 09-11, moving 1 bp an hour back and forth,
    with a step of `size` at each (UTC hour text, size)."""
    hours = [h for h in range(int(pd.Timestamp("2026-08-03", tz="UTC").timestamp()),
                              int(pd.Timestamp("2026-09-11", tz="UTC").timestamp()), HOUR)
             if sessions.session_key(h, "cbot_rates")]
    r = np.where(np.arange(len(hours)) % 2, 1e-4, -1e-4)
    at = {int(pd.Timestamp(t, tz="UTC").timestamp()): size for t, size in steps}
    r = r + np.array([at.get(h, 0.0) for h in hours])
    return _hours(list(108.0 * np.exp(np.cumsum(r)))).assign(hour_utc=hours)


def test_a_switch_inside_an_hour_drops_that_hour_and_an_unclear_window_goes():
    # The 10-year's series switched inside 07:00 UTC 2026-08-27, this series' roll
    # day: looked for within a business day of it, the hour stands out and is
    # dropped, so the next is measured from its own open.
    frame = _rates([("2026-08-27 07:00", -0.0026)])
    out, nights, dropped, found = futures.locate_switches(
        frame, "ZN=F", "cbot_rates", date(2026, 12, 1), before=1, after=1, rolls_only=True)
    switch = int(pd.Timestamp("2026-08-27 07:00", tz="UTC").timestamp())
    assert switch not in set(out["hour_utc"]) and len(out) == len(frame) - 1
    assert nights == [] and dropped == [] and len(found) == 1
    # Two steps alike: neither stands out, and the window's days are dropped.
    frame = _rates([("2026-08-27 07:00", -0.0026), ("2026-08-26 15:00", 0.0025)])
    out, _, dropped, _ = futures.locate_switches(
        frame, "ZN=F", "cbot_rates", date(2026, 12, 1), before=1, after=1, rolls_only=True)
    assert dropped == [(date(2026, 8, 26), date(2026, 8, 28))]
    days = pd.to_datetime(out["hour_utc"], unit="s", utc=True).dt.date
    assert not days.between(date(2026, 8, 26), date(2026, 8, 28)).any()
    # Unless it is the seam's: that roll's night is unscored already.
    out, _, dropped, _ = futures.locate_switches(
        frame, "ZN=F", "cbot_rates", date(2026, 8, 27), before=1, after=1, rolls_only=True)
    assert dropped == [] and len(out) == len(frame)
