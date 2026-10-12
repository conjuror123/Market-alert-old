"""The measurement behind the dashboard: what the code sends, measured afresh each run.

    PYTHONPATH=. python -m tools.measure OUT.json [--voters DIR] [--bars-dir DIR]

Everything is computed by the bot's own code, cold, from the bar store: the metrics by
jump.pipeline into a temporary directory, the readings and their 24-hour events by
jump.jumps.run, a push by routing.PUSH_TIERS, a vote by jump.verify (candidates,
judge_found, as the live pass votes). Nothing is written to the store, the record or the
metrics the bot keeps, and nothing is kept between runs.

THE VOTES ARE TAKEN AGAIN, by this code, from every voter's bars as tools/voter_bars.py
fetched them (`--voters`): every far move of the last 365 days put to its sources. A
source reaches back only so far (MarketWatch 9 days, the FT 30, Wallstreetcn 170, Alpaca's
tape years), and a source with no bar at a move is an outage, so the older a move, the
fewer its voters: the votes are counted by age, with the sources that reach each age.

TWO READINGS. "The detector alone": every reading, no vote. "With the votes": the votes
taken here applied as the live run applies its record (a move voted not real left out, a
first hour voted overnight moved into its night) - over the voted year only, as no vote
exists before it.

WINDOWS. The year to the measurement (the voters' fetch, or now without them) and the year
before it; the archive by calendar year. An event belongs to the window its first reading
was found in (`event_start`).

SELF-CHECKS. The counts are cross-added - blocks to the basket, instruments to their block,
words to the total, years to the archive, ages and verdicts to the votes, each source's
answers to its asks - and every instrument must have scored. A check that fails makes the
command fail, so no wrong page is published.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from jump import jumps, routing
from jump.basket import load_basket
from tools.stage_report import BIGGEST_SHARE

log = logging.getLogger("tools.measure")

DAY = 86400
VOTE_DAYS = 365
# The ages a vote is counted by, in days: where the sources' reaches end.
AGE_EDGES = (0, 9, 30, 60, 170, 365)


def windows(end: int) -> "list[dict]":
    """The 365 days to `end`, and the 365 before them."""
    out = []
    for back in (1, 2):
        start, stop = end - back * 365 * DAY, end - (back - 1) * 365 * DAY
        out.append({"name": f"year to {datetime.fromtimestamp(stop, timezone.utc):%Y-%m-%d %H:%M}",
                    "start": start, "end": stop, "weeks": 365 / 7})
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


def _inside(events: pd.DataFrame, window: dict) -> pd.DataFrame:
    return events[(events["event_start"] >= window["start"])
                  & (events["event_start"] < window["end"])]


def volume(events: pd.DataFrame, window: dict) -> dict:
    """Pushes and note rows in one window: counts, a week, the busiest week, by word."""
    inside = _inside(events, window)
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
    out = {}
    for name, rows in _inside(events, window).groupby(key):
        out[str(name)] = {"pushes": int(rows["push"].sum()), "rows": int((~rows["push"]).sum())}
    return out


def coverage(basket, metrics_dir: str) -> "list[dict]":
    """Each instrument's scored history: where it comes from, first and last hour, hours."""
    out = []
    for asset in basket.instruments:
        row = {"ticker": asset.ticker, "label": asset.label, "block": asset.block,
               "display": asset.display, "provider": asset.fetched_from,
               "first": None, "last": None, "hours": 0}
        path = os.path.join(metrics_dir, f"{asset.file_stem}.parquet")
        if os.path.exists(path):
            hours = pd.read_parquet(path, columns=["hour_utc"])["hour_utc"].astype("int64")
            row.update(first=int(hours.min()), last=int(hours.max()), hours=int(len(hours)))
        out.append(row)
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


def archive(events: pd.DataFrame, cover: "list[dict]", end: int) -> "list[dict]":
    """Events and pushes by calendar year since the first bar, and the instrument-years
    they came from."""
    first = min(c["first"] for c in cover if c["first"] is not None)
    out = []
    for year in range(datetime.fromtimestamp(first, timezone.utc).year,
                      datetime.fromtimestamp(end - 1, timezone.utc).year + 1):
        start = int(pd.Timestamp(year, 1, 1, tz="UTC").timestamp())
        full = int(pd.Timestamp(year + 1, 1, 1, tz="UTC").timestamp())
        stop = min(full, end)
        mine = events[(events["event_start"] >= start) & (events["event_start"] < stop)]
        out.append({"year": year, "partial": stop < full,
                    "instrument_years": instrument_years(cover, year, end),
                    "events": int(len(mine)), "pushes": int(mine["push"].sum())})
    return out


def biggest_hours(basket, metrics_dir: str, end: int) -> dict:
    """Each instrument's top 0.01% of settled hours by size of move (tools/stage_report's
    measure), and the word the detector gave each - the hours nobody would want missed."""
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


# --- the votes, taken again ---------------------------------------------------------

def read_fetch(voters_dir: str) -> dict:
    """tools/voter_bars.py's first line (when it fetched, how far back) and its failures."""
    with open(os.path.join(voters_dir, "failed.txt"), encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]
    words = lines[0].split()            # fetched YYYY-MM-DD HH:MM UTC, N days
    at = datetime.strptime(f"{words[1]} {words[2]}", "%Y-%m-%d %H:%M").replace(
        tzinfo=timezone.utc)
    return {"at": int(at.timestamp()), "days": float(words[4]),
            "failed": [line for line in lines[1:] if line.strip()]}


def _z_of(asset, metrics_dir: str) -> "dict[tuple[int, str], float]":
    """Each reading's z, as the detector scores it, by (hour, the vote's check)."""
    from jump import verify

    window, ladder = jumps.settings()
    m = pd.read_parquet(os.path.join(metrics_dir, f"{asset.file_stem}.parquet"),
                        columns=["hour_utc", "r", "gap"])
    parts = [jumps.score(m, asset.session_template, window, ladder),
             jumps.score_gaps(m, window, ladder, asset.session_template)]
    s = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    return {(int(h), verify.CLOSE if k == jumps.HOUR else verify.OPEN): float(z)
            for h, k, z in zip(s["hour_utc"], s["reading"], s["z"])}


def take_votes(basket, bars_dir: str, metrics_dir: str, voters_dir: str, now: int,
               days: float = VOTE_DAYS) -> "tuple[list[dict], dict]":
    """Every far move of the last `days` before `now`, voted by this code on the voters'
    saved bars, as the live pass votes (verify.candidates, verify.judge_found). Returns
    one row per vote and the record they make, in the bot's own format."""
    from jump import bars, corporate_actions, sessions, verify

    settings = jumps.settings()
    table = sessions.load_sessions()
    dividends = corporate_actions.load_dividends()
    since = now - int(days * DAY)
    rows, record = [], {}
    for asset in basket.instruments:
        sources = verify.sources_for(asset)
        if not sources:
            continue
        frame = bars.load(bars.store_path(bars_dir, asset.file_stem),
                          since - verify.tail_days(settings[0]) * DAY)
        if frame.empty:
            continue
        found = verify.candidates(asset, frame, table, now, since, basket, dividends,
                                  settings, None)
        if not found:
            continue
        asked = []
        for src in sources:
            path = os.path.join(voters_dir, src.name, f"{asset.file_stem}.parquet")
            asked.append((src.name, verify._priced(pd.read_parquet(path))
                          if os.path.exists(path) else None))
        z = _z_of(asset, metrics_dir)
        for c, (verdict, stored, names, moves, seen) in verify.judge_found(
                asset, frame, found, sources, asked, now):
            record[(asset.asset_id, c["hour"], c["check"])] = verify._row(
                asset, c, verdict, stored, names, moves, seen, now)
            rows.append({"ticker": asset.ticker, "block": asset.block, "hour": int(c["hour"]),
                         "check": c["check"], "z": z.get((int(c["hour"]), c["check"])),
                         "stored": float(stored), "verdict": verdict,
                         "age_days": round((now - int(c["hour"])) / DAY, 2),
                         "answers": [{"source": n, "move": None if m is None else float(m),
                                      "saw": n in seen} for n, m in zip(names, moves)]})
    return rows, record


def write_record(record: dict, path: str) -> None:
    """The votes as a record the detector reads (jump.verify.load)."""
    from jump import verify

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=verify.COLUMNS, lineterminator="\n",
                                extrasaction="ignore")
        writer.writeheader()
        for row in sorted(record.values(), key=lambda r: (r["asset_id"], int(r["hour_utc"]),
                                                          r["check"])):
            writer.writerow(row)


VERDICTS = ("real", "uncertain", "not_real", "overnight")


def vote_tables(votes: "list[dict]", bottom: float) -> dict:
    """The votes counted: by verdict (all, and those far enough to be flagged), by age,
    by source, by block."""
    def count(rows):
        return {v: sum(r["verdict"] == v for r in rows) for v in VERDICTS}

    flagged = [r for r in votes if r["z"] is not None and abs(r["z"]) >= bottom]
    ages = []
    for lo, hi in zip(AGE_EDGES, AGE_EDGES[1:]):
        mine = [r for r in votes if lo <= r["age_days"] < hi]
        answered = [sum(a["move"] is not None for a in r["answers"]) for r in mine]
        reach = sorted({a["source"] for r in mine for a in r["answers"] if a["move"] is not None})
        ages.append({"from_days": lo, "to_days": hi, "votes": len(mine), **count(mine),
                     "answers_a_vote": round(float(np.mean(answered)), 2) if answered else None,
                     "sources_answering": reach})
    sources: "dict[str, dict]" = {}
    for r in votes:
        for a in r["answers"]:
            s = sources.setdefault(a["source"], {"asked": 0, "saw": 0, "did_not": 0, "outage": 0})
            s["asked"] += 1
            if a["move"] is None:
                s["outage"] += 1
            elif a["saw"]:
                s["saw"] += 1
            else:
                s["did_not"] += 1
    blocks = {}
    for b in sorted({r["block"] for r in votes}):
        blocks[b] = count([r for r in votes if r["block"] == b])
    return {"votes": len(votes), "by_verdict": count(votes),
            "flagged": len(flagged), "flagged_by_verdict": count(flagged),
            "by_age": ages, "by_source": sources, "by_block": blocks}


# --- the checks -------------------------------------------------------------------

def checks(result: dict) -> "list[dict]":
    """Cross-additions of the result: each a name, whether it held, and what it compared."""
    out = []

    def check(name, ok, detail):
        out.append({"name": name, "ok": bool(ok), "detail": detail})

    missing = [c["ticker"] for c in result["coverage"] if c["first"] is None]
    check("every instrument scored", not missing and not result["meta"]["failures"],
          f"no metrics: {missing}; failures: {result['meta']['failures']}")
    for reading, wins in (("detector", result["windows"]),
                          ("voted", result["windows"][:1] if result.get("votes") else [])):
        for w in wins:
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
    years = sum(y["events"] for y in result["archive"])
    check("the archive's years add up", years == result["events"],
          f"years {years}, events {result['events']}")
    votes = result.get("votes")
    if votes:
        t = votes["tables"]
        ages = sum(a["votes"] for a in t["by_age"])
        check("the votes' ages add up", ages == t["votes"], f"ages {ages}, votes {t['votes']}")
        verdicts = sum(t["by_verdict"].values())
        check("the votes' verdicts add up", verdicts == t["votes"],
              f"verdicts {verdicts}, votes {t['votes']}")
        bad = [n for n, s in t["by_source"].items()
               if s["asked"] != s["saw"] + s["did_not"] + s["outage"]]
        check("each source's answers add up to its asks", not bad, f"not adding up: {bad}")
        listed = len(votes["list"])
        check("every vote is listed", listed == t["votes"], f"listed {listed}, votes {t['votes']}")
    return out


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def measure(bars_dir: str, voters_dir: "str | None", work_dir: str) -> dict:
    from jump import pipeline

    basket = load_basket()
    window_days, levels = jumps.settings()
    metrics_dir = os.path.join(work_dir, "metrics")
    failures: "list[tuple[str, str]]" = []
    pipeline.write_all(basket, bars_dir, metrics_dir, full=True, failures=failures)
    fetch = read_fetch(voters_dir) if voters_dir else None
    end = fetch["at"] // 3600 * 3600 if fetch else \
        int(datetime.now(timezone.utc).timestamp()) // 3600 * 3600
    wins = windows(end)
    no_record = os.path.join(work_dir, "no-record.csv")             # never written
    detector = event_table(jumps.run(metrics_dir, now=end, verified_path=no_record,
                                     failures=failures))
    events = {"detector": detector}
    votes = None
    if fetch:
        rows, record = take_votes(basket, bars_dir, metrics_dir, voters_dir, end)
        path = os.path.join(work_dir, "votes.csv")
        write_record(record, path)
        events["voted"] = event_table(jumps.run(metrics_dir, now=end, verified_path=path))
        votes = {"fetched": fetch, "days": VOTE_DAYS, "list": rows,
                 "tables": vote_tables(rows, levels[0])}
    cover = coverage(basket, metrics_dir)
    result = {
        "meta": {"commit": os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD"),
                 "subject": _git("log", "-1", "--format=%s"),
                 "branch": os.environ.get("GITHUB_REF_NAME") or _git("branch", "--show-current"),
                 "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                 "end": end, "instruments": len(basket.instruments),
                 "levels": list(levels), "window_days": window_days,
                 "push_words": list(routing.PUSH_TIERS),
                 "last_bar": max((c["last"] for c in cover if c["last"] is not None),
                                 default=None),
                 "failures": [f"{a}: {e}" for a, e in failures]},
        "windows": wins,
        "events": int(len(detector[detector["event_start"] < end])),
        "volume": {"detector": {w["name"]: volume(detector, w) for w in wins}},
        "by_block": {"detector": {w["name"]: split(detector, w, "block") for w in wins}},
        "by_instrument": {"detector": {w["name"]: split(detector, w, "ticker") for w in wins}},
        "coverage": cover,
        "archive": archive(detector[detector["event_start"] < end], cover, end),
        "biggest_hours": biggest_hours(basket, metrics_dir, end),
        "votes": votes,
    }
    if votes:
        first = wins[0]
        voted = events["voted"]
        result["volume"]["voted"] = {first["name"]: volume(voted, first)}
        result["by_block"]["voted"] = {first["name"]: split(voted, first, "block")}
        result["by_instrument"]["voted"] = {first["name"]: split(voted, first, "ticker")}
    result["checks"] = checks(result)
    return result


def main(argv: "list[str] | None" = None) -> int:
    from jump import bars

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--bars-dir", default=bars.DEFAULT_BARS_DIR)
    parser.add_argument("--voters", default=None,
                        help="tools/voter_bars.py's output; without it, no votes")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    with tempfile.TemporaryDirectory() as tmp:
        result = measure(args.bars_dir, args.voters, tmp)
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
