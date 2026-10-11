"""One-off: which source gives gold and silver round the clock by the hour? SiftingIO's
and Twelve Data's hourly bars of XAU/USD and XAG/USD, asked from a runner two minutes
past the hour, and their agreement with Dukascopy's and Wallstreetcn's.

    python -m tools.metals_probe OUT [--now]

For the basket's stage 1 (docs/basket-proposal.md, task 6), the four questions of
docs/decisions.md ("A candidate source answers four questions"): is the bar that
ended at :00 there by :05; which hours it holds; whether it agrees with two
others; what it costs. The run waits for minute 2 of the next hour (--now asks at
once), before the hourly run's minutes on Twelve Data (price_monitor/twelvedata.py,
LIVE_SLOT_MINUTES), and asks each keyed source for 60 days of each metal, one page
each: SiftingIO's commodities endpoint, its forex endpoint only where that refuses,
and Twelve Data's two in one batch - six requests at most, SiftingIO's month being
near its limit. Dukascopy's last two whole months (a month's file is there once
the month has ended) and Wallstreetcn's bars need no key.

Each series is written to OUT/<source>_<metal>.json as [start, open, high, low,
close] rows, and OUT/summary.txt says what came back; each line is printed as a
notice too, so the run's annotations carry it. The keys are read from the
environment and scrubbed from every line. The bot never runs this: it writes
nothing to the store.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger(__name__)

# Ours -> SiftingIO's and Dukascopy's symbol, Wallstreetcn's code.
METALS = {"XAU/USD": ("XAUUSD", "XAUUSD.OTC"), "XAG/USD": ("XAGUSD", "XAGUSD.OTC")}
DAYS = 60
ASK_AT_MINUTE = 2
COMMODITIES_ENDPOINT = "/hist/commodities/{symbol}/bars"
# Dukascopy's integers for the metals are in thousandths: read so, gold is 4,040-4,450
# and silver 57-66 dollars in August 2026.
DUKASCOPY_POINT = 1e-3
HOUR = 3600


def in_metals_week(moment: datetime) -> bool:
    """Spot gold and silver trade from Sunday evening to Friday evening (UTC);
    the hours this asks about are Monday 00:00 to Friday 20:00."""
    return moment.weekday() < 4 or (moment.weekday() == 4 and moment.hour < 20)


def wait_for_minute(minute: int, now: datetime, sleep=time.sleep) -> datetime:
    """Sleeps until `minute` past the next hour that reaches it; the moment woken."""
    target = now.replace(minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(hours=1)
    sleep((target - now).total_seconds())
    return target


def freshness(candles: list, asked: datetime) -> str:
    """Whether the bar that ended on the hour before `asked` is there, and the
    forming one after it."""
    hour = int(asked.timestamp()) // HOUR * HOUR
    starts = {c.open_time for c in candles}
    if not starts:
        return "no bars"
    ended = datetime.fromtimestamp(hour, tz=timezone.utc).strftime("%H:%M")
    said = (f"the bar that ended at {ended} is there" if hour - HOUR in starts
            else f"the bar that ended at {ended} is MISSING")
    if hour in starts:
        said += ", and the forming one"
    newest = datetime.fromtimestamp(max(starts), tz=timezone.utc)
    return f"{said} (asked at {asked:%H:%M:%S}, newest opens {newest:%Y-%m-%d %H:%M})"


def hours_held(candles: list) -> str:
    """Hours a week over the bars' own span, and the weekday hours (UTC) held on
    fewer than half the days."""
    if not candles:
        return "no hours"
    days = (candles[-1].open_time - candles[0].open_time + HOUR) / 86400
    weekdays = [datetime.fromtimestamp(c.open_time, tz=timezone.utc) for c in candles]
    weekdays = [m for m in weekdays if m.weekday() < 4]
    days_seen = len({m.date() for m in weekdays}) or 1
    count = {h: 0 for h in range(24)}
    for m in weekdays:
        count[m.hour] += 1
    thin = [h for h, n in count.items() if n < days_seen / 2]
    weekend = sum(datetime.fromtimestamp(c.open_time, tz=timezone.utc).weekday() == 5
                  for c in candles)
    return (f"{len(candles) / (days / 7):.0f} hours a week; Mon-Thu hours held on under "
            f"half of {days_seen} days: {thin or 'none'}; Saturday bars {weekend}")


def agreement(candidate: list, reference: list) -> str:
    """The import gate's measures (jump.backfill.verify_alignment) over the hours
    both hold."""
    from jump import backfill, bars

    if not candidate or not reference:
        return "no overlap"
    stored = bars.to_hourly(bars.candles_to_frame(reference))
    got = backfill.verify_alignment(bars.candles_to_frame(candidate), stored, min_hours=1)
    return (f"{got['hours']} hours, correlation {got['correlation']:.4f}, "
            f"median {got['median_bp']:.2f} bp")


def sifting_bars(symbol: str, api_key: str, session, now: datetime) -> "tuple[str, list]":
    """60 days of hourly bars from the commodities endpoint, or the forex one
    where that refuses; the endpoint that answered, and the bars."""
    from price_monitor import sifting
    from price_monitor.models import ExchangeError

    params = {"start": sifting._stamp(now - timedelta(days=DAYS)),
              "end": sifting._stamp(now), "interval": "1h", "limit": sifting.PAGE_LIMIT}
    refused = []
    for endpoint in (COMMODITIES_ENDPOINT, sifting.FX_ENDPOINT):
        path = endpoint.format(symbol=symbol, pair=symbol)
        try:
            payload = sifting._get(session, f"{sifting.BASE_URL}{path}", params, api_key,
                                   symbol)
        except sifting.RateLimited:
            raise
        except ExchangeError as exc:              # a refusal, the key's included
            refused.append(f"{path} refused - {str(exc)[:160]}")
            continue
        more = " (more pages)" if (payload.get("meta") or {}).get("next_cursor") else ""
        bars = sifting._parse(payload.get("data"), HOUR, symbol)
        return "; ".join(refused + [f"{path}{more}"]), bars
    raise ExchangeError("; ".join(refused))


def dukascopy_bars(symbol: str, today: date, session) -> list:
    """The last two whole months, bid and ask folded to the mid, in dollars."""
    from price_monitor import dukascopy
    from price_monitor.models import Candle

    end = today.replace(day=1)
    start = (end - timedelta(days=32)).replace(day=1)
    scale = DUKASCOPY_POINT / dukascopy.point_for(symbol)
    return [Candle(open_time=c.open_time, open=c.open * scale, high=c.high * scale,
                   low=c.low * scale, close=c.close * scale, volume=0.0,
                   close_time=c.close_time)
            for c in dukascopy.fetch_history(symbol, start, end, session)]


def _save(out_dir: str, name: str, candles: list) -> None:
    with open(os.path.join(out_dir, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump([[c.open_time, c.open, c.high, c.low, c.close] for c in candles], f)


def probe(out_dir: str, session, keys: dict, asked: datetime) -> "list[str]":
    from jump.backfill import TWELVEDATA_BASE_URL
    from price_monitor import sifting, twelvedata, wallstreetcn

    os.makedirs(out_dir, exist_ok=True)
    summary = [] if in_metals_week(asked) else [
        f"asked at {asked:%a %H:%M} UTC, outside the metals' week: freshness not measured"]
    series: dict = {}

    sifting_spent = False
    for symbol, _ in METALS.values():
        name = f"sifting_{symbol}"
        if sifting_spent or not keys.get("sifting"):
            summary.append(f"{name}: not asked, "
                           + ("SiftingIO's budget spent" if sifting_spent else "no key"))
            continue
        try:
            endpoint, series[name] = sifting_bars(symbol, keys.get("sifting", ""), session,
                                                  asked)
            summary.append(f"{name}: {endpoint}; {len(series[name])} bars")
        except sifting.RateLimited as exc:
            sifting_spent = True
            summary.append(f"{name}: rate limited - {exc} (remaining {exc.remaining})")
        except Exception as exc:
            summary.append(f"{name}: failed - {str(exc)[:300]}")

    try:
        if not keys.get("twelvedata"):
            raise ValueError("not asked, no key")
        answer = twelvedata.fetch_batch(list(METALS), "1h", asked - timedelta(days=DAYS),
                                        asked, TWELVEDATA_BASE_URL,
                                        keys.get("twelvedata", ""), session, retries=0)
        for ours, (symbol, _) in METALS.items():
            got = answer.get(ours)
            if isinstance(got, Exception) or got is None:
                summary.append(f"twelvedata_{symbol}: refused - {str(got)[:300]}")
            else:
                series[f"twelvedata_{symbol}"] = got
                summary.append(f"twelvedata_{symbol}: {len(got)} bars")
    except Exception as exc:
        summary.append(f"twelvedata: failed - {str(exc)[:300]}")

    for symbol, code in METALS.values():
        try:
            series[f"dukascopy_{symbol}"] = dukascopy_bars(symbol, asked.date(), session)
        except Exception as exc:
            summary.append(f"dukascopy_{symbol}: failed - {str(exc)[:300]}")
        try:
            series[f"wallstreetcn_{symbol}"] = wallstreetcn.fetch_hourly(code, session,
                                                                         asked, DAYS)
        except Exception as exc:
            summary.append(f"wallstreetcn_{symbol}: failed - {str(exc)[:300]}")

    for name, candles in series.items():
        _save(out_dir, name, candles)
        span = (f"{datetime.fromtimestamp(candles[0].open_time, tz=timezone.utc):%Y-%m-%d %H:%M}"
                f" .. {datetime.fromtimestamp(candles[-1].open_time, tz=timezone.utc):%Y-%m-%d %H:%M}"
                if candles else "")
        line = f"{name}: {span}; {hours_held(candles)}"
        if name.startswith(("sifting", "twelvedata")):
            symbol = name.split("_", 1)[1]
            line += "; " + freshness(candles, asked)
            for ref in ("dukascopy", "wallstreetcn"):
                line += f"; against {ref}: {agreement(candles, series.get(f'{ref}_{symbol}', []))}"
        summary.append(line)
    for symbol, _ in METALS.values():
        summary.append(f"dukascopy_{symbol} against wallstreetcn: " + agreement(
            series.get(f"dukascopy_{symbol}", []), series.get(f"wallstreetcn_{symbol}", [])))

    summary = [scrub(line, keys) for line in summary]
    with open(os.path.join(out_dir, "summary.txt"), "w", encoding="utf-8") as f:
        f.writelines(f"{line}\n" for line in summary)
    return summary


def scrub(line: str, keys: dict) -> str:
    """A line with no key in it, whatever an error message quoted."""
    for key in keys.values():
        if key:
            line = line.replace(key, "***")
    return line


def main(argv: "list[str] | None" = None) -> int:
    import requests

    parser = argparse.ArgumentParser(description="Gold and silver by the hour, asked from a runner")
    parser.add_argument("out_dir")
    parser.add_argument("--now", action="store_true", help="ask at once, not at minute 2")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    keys = {"sifting": os.environ.get("SIFTING_API_KEY", ""),
            "twelvedata": os.environ.get("TWELVEDATA_API_KEY", "")}
    if not args.now:
        wait_for_minute(ASK_AT_MINUTE, datetime.now(timezone.utc))
    for line in probe(args.out_dir, requests.Session(), keys, datetime.now(timezone.utc)):
        print(line)
        print(f"::notice title=metals-probe::{line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
