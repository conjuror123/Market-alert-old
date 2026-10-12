"""The measurement behind the dashboard: what the detector sends, measured the same way
every time the code changes.

    PYTHONPATH=. python -m tools.measure OUT.json [--bars-dir DIR] [--verified CSV]
                                                  [--asof YYYY-MM-DD]

Everything is computed by the bot's own code, cold, from the bar store: the metrics by
jump.pipeline into a temporary directory, the readings and their 24-hour events by
jump.jumps.run, a push by routing.PUSH_TIERS. Nothing is written to the store, the
record or the metrics the bot keeps.

TWO READINGS OF EVERY COUNT. "As the bot scores it": with the sources' record
(data/jump/verified.csv) applied, as the live run does - a move voted not real is left
out, a first hour voted overnight has its night moved into the gap. "The detector alone":
the same with no record. Votes exist only where voters reached (each source serves its own
stretch of history), so the archive's years differ in how many of their moves were ever
voted; `votes_by_year` says which.

FIXED WINDOWS. The last complete month ends the year measured, so two runs in the same
month measure the same hours and differ only by the code: the year to the 1st of this
month (UTC) and the year before it. An event belongs to the window its first reading was
found in (`event_start`). The archive is counted by calendar year up to the same end.

SELF-CHECKS. The counts are cross-added - blocks to the basket, instruments to their
block, words to the total, years to the archive - and every instrument must have scored.
A check that fails makes the command fail, so no wrong page is published.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import tempfile
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from jump import jumps, routing
from jump.basket import load_basket
from tools.stage_report import BIGGEST_SHARE

log = logging.getLogger("tools.measure")

READINGS = ("bot", "detector")
DAY = 86400


def windows(asof: date) -> "list[dict]":
    """The year to the 1st of `asof`'s month (UTC), and the year before it."""
    end = pd.Timestamp(asof.year, asof.month, 1, tz="UTC")
    out = []
    for back in (1, 2):
        start, stop = end - pd.DateOffset(years=back), end - pd.DateOffset(years=back - 1)
        out.append({"name": f"year to {stop.date()}", "start": int(start.timestamp()),
                    "end": int(stop.timestamp()),
                    "weeks": (stop - start).total_seconds() / (7 * DAY)})
    return out


def event_table(readings: pd.DataFrame) -> pd.DataFrame:
    """One row per 24-hour event (jumps.events): its biggest reading, worded by it,
    pushed or a row in the weekly note."""
    if readings.empty:
        return pd.DataFrame(columns=["ticker", "block", "event_start", "hour_utc", "word",
                                     "push", "reading", "z", "r"])
    events = jumps.events(readings)
    events = events.assign(push=events["word"].isin(routing.PUSH_TIERS).to_numpy(dtype=bool),
                           event_start=events["event_start"].astype("int64"))
    return events[["ticker", "block", "event_start", "hour_utc", "word", "push", "reading",
                   "z", "r"]].reset_index(drop=True)


def volume(events: pd.DataFrame, window: dict) -> dict:
    """Pushes and note rows in one window: counts, a week, the busiest week, by word."""
    inside = events[(events["event_start"] >= window["start"])
                    & (events["event_start"] < window["end"])]
    pushes, rows = int(inside["push"].sum()), int((~inside["push"]).sum())
    weeks = (pd.to_datetime(inside.loc[inside["push"], "event_start"], unit="s")
             .dt.to_period("W-FRI").value_counts())
    busiest = {"pushes": int(weeks.max()), "week_to": str(weeks.idxmax().end_time.date())} \
        if len(weeks) else {"pushes": 0, "week_to": None}
    return {"pushes": pushes, "rows": rows,
            "pushes_a_week": round(pushes / window["weeks"], 2),
            "rows_a_week": round(rows / window["weeks"], 2),
            "busiest_week": busiest,
            "by_word": {w: int((inside["word"] == w).sum()) for w in jumps.WORDS}}


def split(events: pd.DataFrame, window: dict, key: str) -> "dict[str, dict]":
    """Pushes and rows in one window, by `key` (block or ticker)."""
    inside = events[(events["event_start"] >= window["start"])
                    & (events["event_start"] < window["end"])]
    out = {}
    for name, rows in inside.groupby(key):
        out[str(name)] = {"pushes": int(rows["push"].sum()), "rows": int((~rows["push"]).sum())}
    return out


def coverage(basket, metrics_dir: str) -> "list[dict]":
    """Each instrument's scored history: where it comes from, first and last hour, hours."""
    out = []
    for asset in basket.instruments:
        path = os.path.join(metrics_dir, f"{asset.file_stem}.parquet")
        if not os.path.exists(path):
            out.append({"ticker": asset.ticker, "label": asset.label, "block": asset.block,
                        "display": asset.display, "provider": asset.fetched_from,
                        "first": None, "last": None, "hours": 0})
            continue
        hours = pd.read_parquet(path, columns=["hour_utc"])["hour_utc"].astype("int64")
        out.append({"ticker": asset.ticker, "label": asset.label, "block": asset.block,
                    "display": asset.display, "provider": asset.fetched_from,
                    "first": int(hours.min()), "last": int(hours.max()), "hours": int(len(hours))})
    return out


def instrument_years(cover: "list[dict]", year: int, end: int) -> float:
    """Years of history the basket's instruments had in a calendar year, up to `end`."""
    start = int(pd.Timestamp(year, 1, 1, tz="UTC").timestamp())
    stop = min(int(pd.Timestamp(year + 1, 1, 1, tz="UTC").timestamp()), end)
    total = 0.0
    for c in cover:
        if c["first"] is None:
            continue
        overlap = min(stop, c["last"] + 3600) - max(start, c["first"])
        total += max(overlap, 0) / (365.25 * DAY)
    return round(total, 2)


def archive(events: "dict[str, pd.DataFrame]", cover: "list[dict]", end: int) -> "list[dict]":
    """Events and pushes by calendar year since the first bar, both readings, and the
    instrument-years they came from."""
    first = min(c["first"] for c in cover if c["first"] is not None)
    out = []
    for year in range(datetime.fromtimestamp(first, timezone.utc).year,
                      datetime.fromtimestamp(end - 1, timezone.utc).year + 1):
        start = int(pd.Timestamp(year, 1, 1, tz="UTC").timestamp())
        stop = min(int(pd.Timestamp(year + 1, 1, 1, tz="UTC").timestamp()), end)
        row = {"year": year, "partial": stop < int(pd.Timestamp(year + 1, 1, 1,
                                                                tz="UTC").timestamp()),
               "instrument_years": instrument_years(cover, year, end)}
        for reading, ev in events.items():
            mine = ev[(ev["event_start"] >= start) & (ev["event_start"] < stop)]
            row[reading] = {"events": int(len(mine)), "pushes": int(mine["push"].sum())}
        out.append(row)
    return out


def biggest_hours(basket, metrics_dir: str, end: int) -> dict:
    """Each instrument's top 0.01% of settled hours by size of move (tools/stage_report's
    measure), and the word the detector alone gave each - the hours nobody would want
    missed."""
    window, ladder = jumps.settings()
    counts = {w: 0 for w in jumps.WORDS} | {"not flagged": 0}
    per = []
    for asset in basket.instruments:
        path = os.path.join(metrics_dir, f"{asset.file_stem}.parquet")
        if not os.path.exists(path):
            continue
        m = pd.read_parquet(path, columns=["hour_utc", "r", "gap"])
        s = jumps.score(m, asset.session_template, window, ladder)
        s = s[~s["young"].astype(bool) & np.isfinite(s["r"]) & (s["hour_utc"] < end)]
        if s.empty:
            continue
        size = s["r"].abs()
        big = s[size >= size.quantile(1 - BIGGEST_SHARE)]
        words = big["word"].fillna("not flagged").astype(str)
        for w, n in words.value_counts().items():
            counts[w] += int(n)
        per.append({"ticker": asset.ticker, "hours": int(len(big)),
                    "not_flagged": int((words == "not flagged").sum())})
    return {"by_word": counts, "total": int(sum(counts.values())), "by_instrument": per}


def votes_by_year(record: dict, events: pd.DataFrame, basket, end: int) -> "list[dict]":
    """The record's verdicts by year of the move, for the basket's instruments, and how
    many of the bot's events had one."""
    ids = {a.asset_id: a.ticker for a in basket.instruments}
    rows = [{"year": datetime.fromtimestamp(k[1], timezone.utc).year, "verdict": r["verdict"]}
            for k, r in record.items() if k[0] in ids and k[1] < end]
    verdicts = pd.DataFrame(rows, columns=["year", "verdict"])
    voted_keys = {(ids[k[0]], k[1]) for k in record if k[0] in ids}
    ev = events[events["event_start"] < end].assign(
        year=lambda f: pd.to_datetime(f["event_start"], unit="s").dt.year,
        voted=lambda f: [(t, int(h)) in voted_keys for t, h in zip(f["ticker"], f["hour_utc"])])
    out = []
    for year in sorted(set(verdicts["year"]) | set(ev["year"])):
        v = verdicts[verdicts["year"] == year]["verdict"].value_counts()
        e = ev[ev["year"] == year]
        out.append({"year": int(year),
                    **{name: int(v.get(name, 0)) for name in
                       ("real", "uncertain", "not_real", "overnight")},
                    "events": int(len(e)), "events_voted": int(e["voted"].sum())})
    return out


def checks(result: dict) -> "list[dict]":
    """Cross-additions of the result: each a name, whether it held, and what it compared."""
    out = []

    def check(name, ok, detail):
        out.append({"name": name, "ok": bool(ok), "detail": detail})

    missing = [c["ticker"] for c in result["coverage"] if c["first"] is None]
    check("every instrument scored", not missing and not result["meta"]["failures"],
          f"no metrics: {missing}; failures: {result['meta']['failures']}")
    for reading in READINGS:
        for w in result["windows"]:
            total = result["volume"][reading][w["name"]]
            blocks = result["by_block"][reading][w["name"]]
            tickers = result["by_instrument"][reading][w["name"]]
            for kind in ("pushes", "rows"):
                b = sum(x[kind] for x in blocks.values())
                t = sum(x[kind] for x in tickers.values())
                check(f"{reading}, {w['name']}: {kind} of the blocks and instruments add up",
                      b == total[kind] == t, f"total {total[kind]}, blocks {b}, instruments {t}")
            words = sum(total["by_word"].values())
            check(f"{reading}, {w['name']}: the words add up",
                  words == total["pushes"] + total["rows"],
                  f"words {words}, events {total['pushes'] + total['rows']}")
        years = sum(y[reading]["events"] for y in result["archive"])
        check(f"{reading}: the archive's years add up", years == result["events"][reading],
              f"years {years}, events {result['events'][reading]}")
    return out


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def measure(bars_dir: str, verified: str, asof: date, metrics_dir: str) -> dict:
    from jump import pipeline

    basket = load_basket()
    window_days, levels = jumps.settings()
    failures: "list[tuple[str, str]]" = []
    pipeline.write_all(basket, bars_dir, metrics_dir, full=True, failures=failures)
    wins = windows(asof)
    end = wins[0]["end"]
    empty = os.path.join(metrics_dir, "no-record.csv")      # never written: no votes
    readings = {"bot": jumps.run(metrics_dir, now=end, verified_path=verified,
                                 failures=failures),
                "detector": jumps.run(metrics_dir, now=end, verified_path=empty)}
    events = {k: event_table(v) for k, v in readings.items()}
    cover = coverage(basket, metrics_dir)
    from jump import verify
    record = verify.load(verified)
    last = max((c["last"] for c in cover if c["last"] is not None), default=None)
    result = {
        "meta": {"commit": os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD"),
                 "subject": _git("log", "-1", "--format=%s"),
                 "branch": os.environ.get("GITHUB_REF_NAME") or _git("branch", "--show-current"),
                 "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                 "end": end, "instruments": len(basket.instruments),
                 "levels": list(levels), "window_days": window_days,
                 "push_words": list(routing.PUSH_TIERS), "last_bar": last,
                 "record_rows": len(record),
                 "record_newest_check": max((int(r.get("checked_utc") or 0)
                                             for r in record.values()), default=None),
                 "failures": [f"{a}: {e}" for a, e in failures]},
        "windows": wins,
        "events": {k: int(len(v[v["event_start"] < end])) for k, v in events.items()},
        "volume": {k: {w["name"]: volume(v, w) for w in wins} for k, v in events.items()},
        "by_block": {k: {w["name"]: split(v, w, "block") for w in wins}
                     for k, v in events.items()},
        "by_instrument": {k: {w["name"]: split(v, w, "ticker") for w in wins}
                          for k, v in events.items()},
        "coverage": cover,
        "archive": archive({k: v[v["event_start"] < end] for k, v in events.items()},
                           cover, end),
        "biggest_hours": biggest_hours(basket, metrics_dir, end),
        "votes_by_year": votes_by_year(record, events["bot"], basket, end),
    }
    result["checks"] = checks(result)
    return result


def headline(result: dict) -> dict:
    """The row a run adds to the dashboard's history across changes."""
    meta, first = result["meta"], result["windows"][0]["name"]
    v = result["volume"]["bot"][first]
    return {"commit": meta["commit"], "subject": meta["subject"],
            "measured_at": meta["measured_at"], "window": first,
            "pushes_a_week": v["pushes_a_week"], "rows_a_week": v["rows_a_week"],
            "busiest_week": v["busiest_week"]["pushes"],
            "instruments": meta["instruments"], "levels": meta["levels"]}


def main(argv: "list[str] | None" = None) -> int:
    from jump import bars, verify

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--bars-dir", default=bars.DEFAULT_BARS_DIR)
    parser.add_argument("--verified", default=verify.VERIFIED_PATH)
    parser.add_argument("--asof", default=None, help="YYYY-MM-DD; today by default")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    asof = date.fromisoformat(args.asof) if args.asof else datetime.now(timezone.utc).date()
    with tempfile.TemporaryDirectory() as tmp:
        result = measure(args.bars_dir, args.verified, asof, tmp)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, default=int)
    failed = [c for c in result["checks"] if not c["ok"]]
    for c in failed:
        print(f"CHECK FAILED: {c['name']} ({c['detail']})")
    print(f"{len(result['checks']) - len(failed)} of {len(result['checks'])} checks held; "
          f"wrote {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
