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
