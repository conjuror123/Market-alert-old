"""tools/source_audit.py: a source against the store, judged as the vote judges."""
import numpy as np
import pandas as pd

from tools import source_audit as a

HOUR = 3600


def _store(n=1200, seed=1):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.003, n)
    r[rng.choice(n, 40, replace=False)] *= 6                     # big moves, any hour
    start = 1_790_000_000 // HOUR * HOUR
    return pd.DataFrame({"hour_utc": [start + i * HOUR for i in range(n)],
                         "close": 100 * np.exp(np.cumsum(r))})


def _hour(frame):
    return pd.to_datetime(frame["hour_utc"], unit="s", utc=True).dt.hour.to_numpy()


def _judge(src, store):
    row = a.compare(src, store, "UTC")
    row.update(hours=len(src))
    return row, a.verdict(row)


def test_the_same_moves_are_accepted():
    store = _store()
    row, v = _judge(store.copy(), store)
    assert row["corr"] == 1.0 and row["confirmed"] == 1.0 and v == "accepted"


def test_a_close_filed_an_hour_early_is_another_grid():
    # The FT's Top 40: its 14:00 bar carries the store's 15:00 close, so the big
    # moves the store makes at 14:00 the source shows at 13:00.
    store = _store()
    rng = np.random.default_rng(3)
    at14 = _hour(store) == 14
    bump = np.where(at14, rng.choice([-1, 1], len(store)) * 0.02, 0.0)
    store["close"] = store["close"] * np.exp(np.cumsum(bump))
    src = store.copy()
    early = _hour(src) == 13
    src.loc[early, "close"] = np.roll(store["close"].to_numpy(), -1)[early]
    row, v = _judge(src, store)
    assert "14h" in row["bad_hours"] and v != "accepted"


def test_a_quiet_hours_noise_is_not_held_against_a_source():
    # A pair's 21:00 UTC: the source's prints there are noise, but no big move
    # falls in it.
    store = _store()
    src = store.copy()
    quiet = _hour(src) == 21
    src.loc[quiet, "close"] *= np.exp(np.random.default_rng(7).normal(0, 0.0008, quiet.sum()))
    row, v = _judge(src, store)
    assert row["corr"] >= a.ACCEPT and v == "accepted"


def test_no_answer_and_no_bars_are_named():
    assert a.verdict({"error": "403"}) == "no answer"
    assert a.verdict({"hours": 0}) == "no bars"
    assert a.verdict({"hours": 5, "corr": None}) == "too few shared hours"
