"""tools/metals_probe.py: gold and silver by the hour, asked from a runner."""
from datetime import datetime, timezone

from price_monitor.models import Candle
from tools import metals_probe

ASKED = datetime(2026, 10, 12, 9, 2, 30, tzinfo=timezone.utc)      # a Monday
HOUR = 3600


def _bars(start, count, price=4000.0, step=1.0):
    return [Candle(open_time=start + i * HOUR, open=price + i * step,
                   high=price + i * step + 1, low=price + i * step - 1,
                   close=price + i * step + (i % 3) * 0.5, volume=0.0,
                   close_time=start + (i + 1) * HOUR) for i in range(count)]


def test_the_wait_ends_at_minute_two_of_the_next_hour_that_reaches_it():
    slept = []
    woke = metals_probe.wait_for_minute(
        2, datetime(2026, 10, 12, 9, 40, tzinfo=timezone.utc), slept.append)
    assert woke == datetime(2026, 10, 12, 10, 2, tzinfo=timezone.utc) and slept == [1320.0]
    woke = metals_probe.wait_for_minute(
        2, datetime(2026, 10, 12, 9, 1, tzinfo=timezone.utc), slept.append)
    assert woke == datetime(2026, 10, 12, 9, 2, tzinfo=timezone.utc) and slept[-1] == 60.0


def test_freshness_names_the_bar_that_ended_on_the_hour_and_the_forming_one():
    hour = int(ASKED.timestamp()) // HOUR * HOUR
    assert metals_probe.freshness(_bars(hour - 5 * HOUR, 6), ASKED).startswith(
        "the bar that ended at 09:00 is there, and the forming one")
    assert metals_probe.freshness(_bars(hour - 5 * HOUR, 5), ASKED).startswith(
        "the bar that ended at 09:00 is there (")
    assert metals_probe.freshness(_bars(hour - 5 * HOUR, 4), ASKED).startswith(
        "the bar that ended at 09:00 is MISSING")


def test_the_metals_week_leaves_out_the_weekend():
    assert metals_probe.in_metals_week(ASKED)
    assert not metals_probe.in_metals_week(datetime(2026, 10, 11, 7, 10, tzinfo=timezone.utc))
    assert not metals_probe.in_metals_week(datetime(2026, 10, 16, 20, 2, tzinfo=timezone.utc))


class _Answer:
    def __init__(self, status, body, headers=None):
        self.status_code, self.body, self.headers = status, body, headers or {}
        self.text = str(body)

    def json(self):
        return self.body


class _Session:
    """SiftingIO's commodities endpoint refuses gold and serves silver; its forex
    endpoint serves gold. Every other source is stubbed out by the test."""

    def __init__(self):
        self.asked = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.asked.append(url)
        start = int(ASKED.timestamp()) // HOUR * HOUR - 199 * HOUR
        rows = [{"t": c.open_time * 1000, "o": c.open, "h": c.high, "l": c.low, "c": c.close}
                for c in _bars(start, 200)]
        if url.endswith("/hist/commodities/XAUUSD/bars"):
            return _Answer(404, {"error": "unknown symbol, key sk-secret"})
        return _Answer(200, {"data": rows, "meta": {}})


def test_a_refused_endpoint_falls_back_and_every_line_is_scrubbed(tmp_path, monkeypatch):
    from price_monitor import twelvedata, wallstreetcn

    monkeypatch.setattr(metals_probe, "dukascopy_bars", lambda *a: [])
    monkeypatch.setattr(wallstreetcn, "fetch_hourly", lambda code, *a: _bars(
        int(ASKED.timestamp()) // HOUR * HOUR - 199 * HOUR, 199))
    monkeypatch.setattr(twelvedata, "fetch_batch", lambda *a, **k: {
        "XAU/USD": ValueError("not in the plan, apikey sk-secret"), "XAG/USD": []})
    session = _Session()
    summary = metals_probe.probe(str(tmp_path), session,
                                 {"sifting": "sk-secret", "twelvedata": "td-secret"}, ASKED)
    text = "\n".join(summary)
    assert "sk-secret" not in text and "***" in text
    assert session.asked == [
        "https://api.sifting.io/v1/hist/commodities/XAUUSD/bars",
        "https://api.sifting.io/v1/hist/forex/XAUUSD/bars",
        "https://api.sifting.io/v1/hist/commodities/XAGUSD/bars"]
    gold = next(line for line in summary if line.startswith("sifting_XAUUSD: 2026"))
    assert "the bar that ended at 09:00 is there, and the forming one" in gold
    assert "against wallstreetcn: 199 hours, correlation 1.0000, median 0.00 bp" in gold
    assert "against dukascopy: no overlap" in gold
    assert "twelvedata_XAUUSD: refused - not in the plan" in text
    assert (tmp_path / "sifting_XAGUSD.json").exists()
    assert (tmp_path / "summary.txt").read_text().count("\n") == len(summary)


def test_no_key_asks_nothing(tmp_path, monkeypatch):
    from price_monitor import wallstreetcn

    monkeypatch.setattr(metals_probe, "dukascopy_bars", lambda *a: [])
    monkeypatch.setattr(wallstreetcn, "fetch_hourly", lambda *a: [])
    session = _Session()
    summary = metals_probe.probe(str(tmp_path), session, {}, ASKED)
    assert session.asked == []
    assert "sifting_XAUUSD: not asked, no key" in summary
    assert "twelvedata: failed - not asked, no key" in summary
