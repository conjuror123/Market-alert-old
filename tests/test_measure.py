"""tools/measure.py: the dashboard's numbers - windows, counts, the votes, the checks."""
import pandas as pd
import pytest

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


def test_the_windows_are_the_365_days_to_the_end_and_the_365_before():
    end = ts("2026-10-12 06:00")
    first, second = measure.windows(end)
    assert (first["start"], first["end"]) == (end - 365 * DAY, end)
    assert (second["start"], second["end"]) == (end - 730 * DAY, end - 365 * DAY)
    assert first["name"] == "year to 2026-10-12 06:00" and first["weeks"] == 365 / 7


def test_volume_counts_events_by_when_they_started_a_week_and_the_busiest_week():
    win = measure.windows(ts("2026-10-01"))[0]
    ev = _events([("SPY", "equity", "2026-03-02 15:00", "high"),
                  ("SPY", "equity", "2026-03-03 15:00", "noticeable"),
                  ("BTC", "crypto", "2026-03-04 01:00", "extreme"),
                  ("BTC", "crypto", "2026-04-15 01:00", "major"),
                  ("BTC", "crypto", "2025-09-30 23:00", "extreme"),    # the year before
                  ("BTC", "crypto", "2026-10-01 00:00", "extreme")])   # after the end
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
    assert measure.instrument_years(cover, 2026, ts("2026-07-02")) == round(182 / 365.25, 2)


def test_the_archive_counts_each_year_and_marks_the_last_partial():
    ev = _events([("SPY", "equity", "2025-03-02 15:00", "high"),
                  ("SPY", "equity", "2026-03-03 15:00", "noticeable")])
    cover = [{"first": ts("2025-01-01"), "last": ts("2026-06-30 23:00")}]
    years = measure.archive(ev, cover, ts("2026-07-01"))
    assert [(y["year"], y["events"], y["pushes"], y["partial"]) for y in years] == [
        (2025, 1, 1, False), (2026, 1, 0, True)]


def test_the_fetch_line_gives_when_and_how_far_and_the_failures(tmp_path):
    (tmp_path / "failed.txt").write_text(
        "fetched 2026-10-12 06:07 UTC, 365 days\nSPY yahoo: answered 429\n")
    fetch = measure.read_fetch(str(tmp_path))
    assert fetch == {"at": ts("2026-10-12 06:07"), "days": 365.0,
                     "failed": ["SPY yahoo: answered 429"]}


def test_the_votes_make_a_record_the_detector_reads(tmp_path):
    from jump import verify
    from jump.basket import load_basket

    spy = next(a for a in load_basket().instruments if a.ticker == "SPY")
    gone = {"hour": ts("2026-03-02 14:00"), "check": verify.CLOSE}
    night = {"hour": ts("2026-03-03 14:00"), "check": verify.CLOSE}
    record = {(spy.asset_id, gone["hour"], gone["check"]): verify._row(
                  spy, gone, verify.NOT_REAL, 0.02, ["yahoo", "sina"], [0.0, None], [], 1),
              (spy.asset_id, night["hour"], night["check"]): verify._row(
                  spy, night, verify.OVERNIGHT, 0.03, ["yahoo", "sina"], [0.025, 0.027],
                  ["yahoo", "sina"], 1)}
    path = str(tmp_path / "votes.csv")
    measure.write_record(record, path)
    assert set(verify.not_real(path)) == {(spy.asset_id, gone["hour"], "close")}
    assert verify.overnight(path) == {(spy.asset_id, night["hour"], "close"):
                                      pytest.approx(0.026)}


def _vote(ticker, block, age, verdict, answers, z=5.0):
    return {"ticker": ticker, "block": block, "hour": 0, "check": "close", "z": z,
            "stored": 0.01, "verdict": verdict, "age_days": age,
            "answers": [{"source": s, "move": m, "saw": saw} for s, m, saw in answers]}


def test_the_votes_are_counted_by_verdict_age_source_and_block():
    votes = [_vote("SPY", "equity", 3, "real", [("yahoo", 0.01, True), ("sina", None, False)]),
             _vote("SPY", "equity", 40, "not_real", [("yahoo", 0.0, False), ("sina", 0.0, False)]),
             _vote("BTC", "crypto", 200, "uncertain", [("kraken", None, False)], z=4.2)]
    t = measure.vote_tables(votes, bottom=4.5)
    assert t["votes"] == 3 and t["by_verdict"] == {"real": 1, "uncertain": 1, "not_real": 1,
                                                    "overnight": 0}
    assert t["flagged"] == 2 and t["flagged_by_verdict"]["uncertain"] == 0
    assert [a["votes"] for a in t["by_age"]] == [1, 0, 1, 0, 1]
    assert t["by_age"][0]["answers_a_vote"] == 1 and t["by_age"][0]["sources_answering"] == ["yahoo"]
    assert t["by_source"] == {"yahoo": {"asked": 2, "saw": 1, "did_not": 1, "outage": 0},
                              "sina": {"asked": 2, "saw": 0, "did_not": 1, "outage": 1},
                              "kraken": {"asked": 1, "saw": 0, "did_not": 0, "outage": 1}}
    assert t["by_block"]["equity"] == {"real": 1, "uncertain": 0, "not_real": 1, "overnight": 0}


def _result(ev, votes=None):
    wins = measure.windows(ts("2026-10-01"))
    out = {"meta": {"failures": []}, "windows": wins,
           "coverage": [{"ticker": "SPY", "first": 1, "last": 2}],
           "events": len(ev),
           "volume": {"detector": {w["name"]: measure.volume(ev, w) for w in wins}},
           "by_block": {"detector": {w["name"]: measure.split(ev, w, "block") for w in wins}},
           "by_instrument": {"detector": {w["name"]: measure.split(ev, w, "ticker")
                                          for w in wins}},
           "archive": measure.archive(ev, [{"first": ts("2024-10-01"), "last": ts("2026-09-30")}],
                                      ts("2026-10-01")),
           "votes": None}
    if votes is not None:
        first = wins[0]
        out["volume"]["voted"] = {first["name"]: measure.volume(ev, first)}
        out["by_block"]["voted"] = {first["name"]: measure.split(ev, first, "block")}
        out["by_instrument"]["voted"] = {first["name"]: measure.split(ev, first, "ticker")}
        out["votes"] = {"list": votes, "tables": measure.vote_tables(votes, 4.5)}
    return out


def test_the_checks_hold_on_consistent_counts_and_fail_on_a_broken_one():
    ev = _events([("SPY", "equity", "2026-03-02 15:00", "high"),
                  ("BTC", "crypto", "2025-03-04 01:00", "noticeable")])
    votes = [_vote("SPY", "equity", 3, "real", [("yahoo", 0.01, True)])]
    result = _result(ev, votes)
    assert all(c["ok"] for c in measure.checks(result))
    result["by_block"]["detector"][result["windows"][0]["name"]]["equity"]["pushes"] += 1
    failed = [c["name"] for c in measure.checks(result) if not c["ok"]]
    assert failed == [f"detector, {result['windows'][0]['name']}: pushes of the blocks and "
                      "instruments add up"]
    result = _result(ev, votes)
    result["votes"]["tables"]["by_source"]["yahoo"]["saw"] = 0
    assert [c["name"] for c in measure.checks(result) if not c["ok"]] == [
        "each source's answers add up to its asks"]
    result = _result(ev)
    result["coverage"].append({"ticker": "GLD", "first": None, "last": None})
    assert not measure.checks(result)[0]["ok"]
