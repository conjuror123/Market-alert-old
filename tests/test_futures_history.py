"""tools/futures_history.py: where a contract's own history starts."""
import pandas as pd

from tools import futures_history

HOUR = 3600


def test_the_contract_held_now_counts_from_the_first_month_it_traded():
    # Dec corn traded 10 contracts an hour in 2024-Q4 and 4,219 as front: its own
    # history starts at the first month at OWN_SHARE of that, not at its listing.
    def month(text, n, volume):
        start = int(pd.Timestamp(text, tz="UTC").timestamp())
        return [(start + k * HOUR, volume) for k in range(n)]
    rows = month("2026-01-05", 50, 10.0) + month("2026-02-02", 50, 300.0) + \
        month("2026-06-11", 50, 4000.0)
    contract = pd.DataFrame(rows, columns=["hour_utc", "volume"]).assign(
        open=1.0, high=1.0, low=1.0, close=1.0, n_src=1)
    seam = int(pd.Timestamp("2026-06-11", tz="UTC").timestamp())
    own = futures_history.own_history(contract, seam)
    assert pd.to_datetime(own["hour_utc"].min(), unit="s").strftime("%Y-%m") == "2026-02"
    assert len(own) == 100


def test_soybeans_cfd_is_looked_for_where_it_switches():
    # Dukascopy's soybeans moved to August on 2022-07-22, 5 business days before
    # July ended (-790 bp against Yahoo's daily series), while this series rolls
    # mid-month and not before August: its own windows never held that night.
    from datetime import date

    from jump import futures
    switch = date(2022, 7, 22)
    own = futures.switch_windows("ZS=F", date(2022, 1, 1), date(2022, 12, 31), rolls_only=True)
    assert not any(lo <= switch <= hi for lo, hi in own)
    cfd = futures_history.cfd_windows(futures_history.CFD_SWITCHES["ZS=F"],
                                      date(2022, 1, 1), date(2022, 12, 31))
    assert any(lo <= switch <= hi for lo, hi in cfd)
    assert len(cfd) == 7


def test_brents_last_trading_day_follows_ices_rule_of_its_time():
    # To the February 2016 contract: the business day before the 15th day before
    # the delivery month (the 17th of July 2011 a Sunday: the 15th, then the 14th).
    # From March 2016: the last business day two months before it.
    from datetime import date
    assert futures_history.brent_last_trading_day(2011, 7) == date(2011, 6, 15)
    assert futures_history.brent_last_trading_day(2011, 8) == date(2011, 7, 14)
    assert futures_history.brent_last_trading_day(2016, 2) == date(2016, 1, 14)
    assert futures_history.brent_last_trading_day(2016, 3) == date(2016, 1, 29)
    assert futures_history.brent_last_trading_day(2026, 12) == date(2026, 10, 30)
