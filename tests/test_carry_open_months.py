"""tools/carry_open_months.py (one-off): carried hours fill the store, never replace."""
import pandas as pd

from jump import bars
from tools import carry_open_months

HOUR = 3600
OCT_1 = 1790834400                                     # 2026-10-01 06:00 UTC


def _rows(hours, price):
    return pd.DataFrame({"hour_utc": hours, "open": price, "high": price, "low": price,
                         "close": price, "volume": 0.0, "n_src": 1})


def test_carried_hours_fill_the_store_and_leave_its_own_bars(tmp_path):
    # The live store has fetched 10-05 on; the carry holds 10-01 on, at other
    # prices. The hours the store lacks come in; its own bars stand.
    stem = "marketwatch_RLI_F"
    store = bars.store_path(str(tmp_path / "bars"), stem)
    live = [OCT_1 + 4 * 86400 + k * HOUR for k in range(5)]
    bars.merge(store, _rows(live, 84.0))
    carry = tmp_path / "carry"
    carry.mkdir()
    old = [OCT_1 + k * HOUR for k in range(3)]
    _rows(old + live, 83.0).to_csv(carry / f"{stem}.csv", index=False)
    added = carry_open_months.carry(str(carry), str(tmp_path / "bars"))
    assert added == {stem: 3}
    got = bars.load(store).set_index("hour_utc")["close"]
    assert got.loc[old].tolist() == [83.0] * 3 and got.loc[live].tolist() == [84.0] * 5
    assert carry_open_months.carry(str(carry), str(tmp_path / "bars")) == {stem: 0}
