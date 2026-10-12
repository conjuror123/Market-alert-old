"""tools/measure.py: the dashboard's numbers - windows, counts, the cross-checks."""
from datetime import date

import pandas as pd

from tools import measure

DAY = 86400


def ts(text):
    return int(pd.Timestamp(text, tz="UTC").timestamp())


def _events(rows):
    """(ticker, block, event start, word) -> the event table's columns."""
    return pd.DataFrame([{"ticker": t, "block": b, "event_start": ts(when),
                          "hour_utc": ts(when) - 3600, "word": w,
                          "push": w in ("high", "major", "extreme"), "reading": "hour",
                          "z": 5.0, "r": 0.01} for t, b, when, w in rows])


def test_the_windows_end_on_the_first_of_the_month_and_run_a_year_each():
    first, second = measure.windows(date(2026, 10, 12))
    assert (first["start"], first["end"]) == (ts("2025-10-01"), ts("2026-10-01"))
    assert (second["start"], second["end"]) == (ts("2024-10-01"), ts("2025-10-01"))
    assert first["name"] == "year to 2026-10-01"
    assert round(first["weeks"], 2) == 52.14 and round(second["weeks"], 2) == 52.14


def test_volume_counts_events_by_when_they_started_a_week_and_the_busiest_week():
    win = measure.windows(date(2026, 10, 12))[0]
    ev = _events([("SPY", "equity", "2026-03-02 15:00", "high"),
                  ("SPY", "equity", "2026-03-03 15:00", "noticeable"),
                  ("BTC", "crypto", "2026-03-04 01:00", "extreme"),
                  ("BTC", "crypto", "2026-04-15 01:00", "major"),
                  ("BTC", "crypto", "2025-09-30 23:00", "extreme"),    # the window before
                  ("BTC", "crypto", "2026-10-01 00:00", "extreme")])   # after the window
    v = measure.volume(ev, win)
    assert (v["pushes"], v["rows"]) == (3, 1)
    assert v["pushes_a_week"] == round(3 / win["weeks"], 2)
    assert v["busiest_week"] == {"pushes": 2, "week_to": "2026-03-06"}
    assert v["by_word"] == {"noticeable": 1, "high": 1, "major": 1, "extreme": 1}
    assert measure.split(ev, win, "block") == {"crypto": {"pushes": 2, "rows": 0},
                                               "equity": {"pushes": 1, "rows": 1}}


def test_instrument_years_count_only_the_history_each_instrument_had():
    cover = [{"first": ts("2026-01-01"), "last": ts("2026-12-31 23:00")},
             {"first": ts("2026-07-02"), "last": ts("2026-12-31 23:00")},
             {"first": None, "last": None}]
    assert measure.instrument_years(cover, 2026, ts("2027-01-01")) == round(
        (365 + 183) / 365.25, 2)
    # Cut at the measurement's end.
    assert measure.instrument_years(cover, 2026, ts("2026-07-02")) == round(182 / 365.25, 2)


def test_the_archive_counts_each_year_in_both_readings():
    ev = _events([("SPY", "equity", "2025-03-02 15:00", "high"),
                  ("SPY", "equity", "2026-03-03 15:00", "noticeable")])
    cover = [{"first": ts("2025-01-01"), "last": ts("2026-06-30 23:00")}]
    years = measure.archive({"bot": ev, "detector": ev.iloc[:1]}, cover, ts("2026-07-01"))
    assert [y["year"] for y in years] == [2025, 2026]
    assert years[0]["bot"] == {"events": 1, "pushes": 1}
    assert years[1]["bot"] == {"events": 1, "pushes": 0} and years[1]["partial"]
    assert years[1]["detector"] == {"events": 0, "pushes": 0}


def _result(ev):
    wins = measure.windows(date(2026, 10, 12))
    out = {"meta": {"failures": []}, "windows": wins,
           "coverage": [{"ticker": "SPY", "first": 1, "last": 2}],
           "events": {r: len(ev) for r in measure.READINGS},
           "volume": {r: {w["name"]: measure.volume(ev, w) for w in wins}
                      for r in measure.READINGS},
           "by_block": {r: {w["name"]: measure.split(ev, w, "block") for w in wins}
                        for r in measure.READINGS},
           "by_instrument": {r: {w["name"]: measure.split(ev, w, "ticker") for w in wins}
                             for r in measure.READINGS},
           "archive": measure.archive({r: ev for r in measure.READINGS},
                                      [{"first": ts("2025-01-01"), "last": ts("2026-09-30")}],
                                      ts("2026-10-01"))}
    return out


def test_the_checks_hold_on_consistent_counts_and_fail_on_a_broken_total():
    ev = _events([("SPY", "equity", "2026-03-02 15:00", "high"),
                  ("BTC", "crypto", "2025-03-04 01:00", "noticeable")])
    result = _result(ev)
    assert all(c["ok"] for c in measure.checks(result))
    result["by_block"]["bot"]["year to 2026-10-01"]["equity"]["pushes"] += 1
    failed = [c["name"] for c in measure.checks(result) if not c["ok"]]
    assert failed == ["bot, year to 2026-10-01: pushes of the blocks and instruments add up"]
    result = _result(ev)
    result["coverage"].append({"ticker": "GLD", "first": None, "last": None})
    assert not measure.checks(result)[0]["ok"]


def test_votes_by_year_name_the_verdicts_and_the_events_that_had_one():
    from jump.basket import load_basket
    basket = load_basket()
    spy = next(a for a in basket.instruments if a.ticker == "SPY")
    hour = ts("2026-03-02 14:00")
    record = {(spy.asset_id, hour, "close"): {"verdict": "not_real"},
              (spy.asset_id, ts("2024-01-02 15:00"), "close"): {"verdict": "real"},
              ("twelvedata:GONE", hour, "close"): {"verdict": "real"}}     # not in the basket
    ev = _events([("SPY", "equity", "2026-03-02 15:00", "high")])
    rows = measure.votes_by_year(record, ev, basket, ts("2026-10-01"))
    assert rows == [{"year": 2024, "real": 1, "uncertain": 0, "not_real": 0, "overnight": 0,
                     "events": 0, "events_voted": 0},
                    {"year": 2026, "real": 0, "uncertain": 0, "not_real": 1, "overnight": 0,
                     "events": 1, "events_voted": 1}]
