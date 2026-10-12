"""tools/usage_from_logs.py: the usage files' starting point from the runs' logs."""
from tools import usage_from_logs as t


def test_requests_lines_are_read_by_their_own_time():
    text = ("2026-10-12T09:06:01.1234567Z 2026-10-12 09:06:01 INFO requests: tiingo 27 "
            "(left 4973), sifting 17, twelvedata 1 (left 793)\n"
            "2026-10-12T09:06:02.0000000Z something else\n"
            "2026-10-12T10:06:01.0000000Z INFO requests: none\n")
    assert t.parse(text) == [("2026-10-12T09:06:01", "tiingo", 27, "4973"),
                             ("2026-10-12T09:06:01", "sifting", 17, ""),
                             ("2026-10-12T09:06:01", "twelvedata", 1, "793")]


def test_a_day_adds_up_and_twelve_data_is_its_own_count():
    # Two runs: Tiingo's requests add up; Twelve Data's day is 800 less the last
    # credits it said were left, whatever the lines counted as requests.
    seen = [("2026-10-12T09:06:01", "tiingo", 27, "4973"),
            ("2026-10-12T09:06:01", "twelvedata", 1, "793"),
            ("2026-10-12T10:06:01", "tiingo", 27, "4946"),
            ("2026-10-12T10:06:01", "twelvedata", 1, "786"),
            ("2026-10-13T00:06:01", "tiingo", 3, "")]
    rows = t.day_rows(seen, "fetch")
    got = {(r.day, r.provider): (r.calls, r.left, r.left_at) for r in rows.itertuples()}
    assert got == {("2026-10-12", "tiingo"): (54, "4946", "10:06"),
                   ("2026-10-12", "twelvedata"): (14, "786", "10:06"),
                   ("2026-10-13", "tiingo"): (3, "", "")}
    assert set(rows["purpose"]) == {"fetch"}
