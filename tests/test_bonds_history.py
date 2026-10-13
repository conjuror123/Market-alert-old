"""tools/bonds_history.py (one-off): the Bund's and gilt's CFD switches."""
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from tools import bonds_history as bh


def _record(days, step_at=None, step=0.0):
    """Hourly CFD bars 07:00-20:00 UTC on these days, quiet, with one hour
    moved by `step` (a log move) from then on."""
    rng = np.random.default_rng(5)
    rows, price = [], 160.0
    for d in days:
        for h in range(7, 21):
            t = int(datetime(d.year, d.month, d.day, h, tzinfo=timezone.utc).timestamp())
            price *= np.exp(rng.normal(0, 0.0004))
            if step_at is not None and t == step_at:
                price *= np.exp(step)
            rows.append((t, price, price, price, price, 1.0))
    return pd.DataFrame(rows, columns=["hour_utc", "open", "high", "low", "close", "volume"])


def test_a_confirmed_switch_drops_its_hour_inside_the_session_or_marks_the_night():
    # The Bund's December 2018 contract last traded on the 6th: its CFD switched
    # on the 5th, a move the yield did not make. At 14:00 UTC (15:00 Frankfurt,
    # in session) the hour goes; at 19:00 UTC (outside 08:00-18:00) the next
    # session's night is a roll.
    days = [date(2018, 12, d) for d in (3, 4, 5, 6, 7)]
    inside = int(datetime(2018, 12, 5, 14, tzinfo=timezone.utc).timestamp())
    rec = _record(days, inside, -0.015)
    out, nights, _ = bh.switches("FGBL=F", "eurex_bund", rec, days[0], days[-1],
                                 pd.Series({inside: -0.015}))
    assert inside not in set(out["hour_utc"]) and len(out) == len(rec) - 1 and nights == []
    late = int(datetime(2018, 12, 5, 19, tzinfo=timezone.utc).timestamp())
    out, nights, _ = bh.switches("FGBL=F", "eurex_bund", _record(days, late, -0.015),
                                 days[0], days[-1], pd.Series({late: -0.015}))
    assert len(out) == len(rec) and nights == ["2018-12-06"]


def test_a_large_move_the_yield_also_made_is_the_market():
    # The same hour, but the yield explains it (no residual): a market move,
    # kept and scored.
    days = [date(2018, 12, d) for d in (3, 4, 5, 6, 7)]
    inside = int(datetime(2018, 12, 5, 14, tzinfo=timezone.utc).timestamp())
    rec = _record(days, inside, -0.015)
    out, nights, lines = bh.switches("FGBL=F", "eurex_bund", rec, days[0], days[-1],
                                     pd.Series({inside: -0.0004}))
    assert len(out) == len(rec) and nights == [] and "none confirmed" in lines[0]


def test_the_residual_is_the_cfds_move_the_yield_does_not_make():
    # The CFD follows the Bund yield fixed at 10:00 Frankfurt (09:00 UTC in
    # winter), and switches by -150 bp at 14:00 UTC on the 5th: that hour's
    # interval, 09:00 the 5th to 09:00 the 6th, holds the switch; the others
    # nothing. MarketWatch's continuous series rolled the same day in 2019-21,
    # which a check against it could not see.
    days = [date(2018, 12, d) for d in range(3, 22) if date(2018, 12, d).weekday() < 5]
    rng = np.random.default_rng(3)
    y = {d.isoformat(): 0.3 + 0.05 * rng.standard_normal() for d in days}
    switch = int(datetime(2018, 12, 5, 14, tzinfo=timezone.utc).timestamp())
    rows = []
    for k, d in enumerate(days):
        for h in range(7, 21):
            t = int(datetime(d.year, d.month, d.day, h, tzinfo=timezone.utc).timestamp())
            fixed = y[(d if h >= 9 or not k else days[k - 1]).isoformat()]
            price = 160.0 * np.exp(-0.08 * fixed - (0.015 if t >= switch else 0.0))
            rows.append((t, price, price, price, price, 0.0))
    rec = pd.DataFrame(rows, columns=["hour_utc", "open", "high", "low", "close", "volume"])
    steps = bh.yield_steps("FGBL=F", rec, pd.Series(y))
    assert steps[switch] == pytest.approx(-0.015, abs=1e-6)
    late = int(datetime(2018, 12, 6, 8, tzinfo=timezone.utc).timestamp())   # before its fixing
    assert steps[late] == pytest.approx(-0.015, abs=1e-6)
    quiet = [int(datetime(2018, 12, d, 14, tzinfo=timezone.utc).timestamp()) for d in (4, 6, 10)]
    assert all(abs(steps[t]) < 1e-6 for t in quiet)


def test_the_gilt_is_looked_for_around_first_notice():
    # December 2025's first notice: two business days before Monday 12-01.
    assert date(2025, 11, 27) in bh.switch_edges("RLI=F", 2025, 2025)
    assert date(2025, 12, 8) in bh.switch_edges("FGBL=F", 2025, 2025)      # last trading day
    # Its CFD switched as late as the delivery month's first business day
    # (2021-12-01 -119 bp at the open): looked for to two business days after.
    assert bh.SWITCH_DAYS["RLI=F"] == (3, 2)
