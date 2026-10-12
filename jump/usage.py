"""What one fetch asked of each provider: answers counted by host, and the quota
a provider says is left, so a budget running short shows in the log before a 429.

Counted on the HTTP session (a response hook), so no client changes. An answer
is counted whatever its status, since a 429 or a 500 uses quota too. A request
that times out has no answer and is not counted. Only what goes through a
session made here is seen.

WHAT A DAY SPENT. A run given a usage file (the USAGE_FILE environment variable)
adds its count to that file: one row per UTC day, provider and purpose (PURPOSES),
with the last figure the provider gave of what is left. Each workflow writes its
own file - the hourly run data/jump/usage/hourly.csv, the history walks manual.csv
- because two committing the same row would stop each other's push (their
rebases stop on a conflict). `calls` is what the provider counts against its
limit: Twelve Data's credits, one per symbol asked (a batch of seven is seven),
everyone else's requests.

THE LIMITS (LIMITS_PATH): each keyed provider's limit per window, and its shares -
the live run's, the room kept for manual fetches, the dashboard's, the votes'.
`warnings` names, once, a day or month that passes WARN_SHARE of a limit, and a
provider whose own count of the day runs GAP_MARGIN ahead of ours: another caller
on the key, or one of ours not counted. Only Twelve Data's figure is known to be
the day's (`api-credits-left`, credits left until 00:00 UTC); SiftingIO's
counts a short window (price_monitor.sifting), and Tiingo's is recorded until its
window is known.
"""
from __future__ import annotations

import glob
import os
import threading
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import requests

# Each provider by the host it is asked at. Anything else is named by its host.
PROVIDERS = {
    "api.tiingo.com": "tiingo",
    "api.sifting.io": "sifting",
    "api.twelvedata.com": "twelvedata",
    "data.alpaca.markets": "alpaca",
    "query1.finance.yahoo.com": "yahoo",
    "data-api.binance.vision": "binance",
    "finance.sina.com.cn": "sina",
    "stock.finance.sina.com.cn": "sina",
    "gu.sina.cn": "sina",
    "api.wsj.net": "marketwatch",
    "api.stlouisfed.org": "fred",
    "cdn.cboe.com": "cboe",
    "cdn-api.cboe.com": "cboe",
    "datafeed.dukascopy.com": "dukascopy",
    "api.exchange.coinbase.com": "coinbase",
    "api.kraken.com": "kraken",
    "api-ddc-wscn.awtmt.com": "wallstreetcn",
    "markets.ft.com": "ft",
}

# The headers a provider says what is left in: Tiingo, SiftingIO, Twelve Data.
# SiftingIO's counts a short window, not its monthly quota (price_monitor.sifting).
REMAINING = ("X-RateLimit-Remaining", "X-Quota-Remaining", "api-credits-left")

# What a call was for: the hourly fetch, the vote (jump.verify), a history walk,
# repair or the dividend table, the dashboard's measurement.
PURPOSES = ("fetch", "votes", "manual", "dashboard")
USAGE_FILE_ENV = "USAGE_FILE"
USAGE_DIR = os.path.join("data", "jump", "usage")
COLUMNS = ["day", "provider", "purpose", "calls", "left", "left_at"]
LIMITS_PATH = os.path.join("config", "provider_limits.csv")
WARN_SHARE = 0.8
# Twelve Data's count of the day ahead of ours by more than this many credits.
GAP_MARGIN = 20


def credits(provider: str, response) -> int:
    """What one answer costs against the provider's limit: Twelve Data's credits
    (its own header, else one per symbol asked), one request for the rest."""
    if provider != "twelvedata":
        return 1
    used = response.headers.get("api-credits-used")
    if used is not None and str(used).strip().isdigit():
        return int(used)
    symbols = parse_qs(urlsplit(response.url).query).get("symbol", [""])[0]
    return max(1, len([s for s in symbols.split(",") if s.strip()]))


class Usage:
    """One run's count. Thread-safe: the Twelve Data batch runs in a thread."""

    def __init__(self) -> None:
        self.answers: Counter = Counter()
        self.spent: Counter = Counter()             # (provider, purpose) -> calls
        self.left: dict[str, str] = {}
        self.left_purpose: dict[str, str] = {}
        self._lock = threading.Lock()

    def session(self, purpose: str = "fetch") -> requests.Session:
        """A session whose every answer is counted here, for `purpose`."""
        if purpose not in PURPOSES:
            raise ValueError(f"unknown purpose {purpose!r}")
        session = requests.Session()
        session.hooks["response"].append(
            lambda response, *a, **k: self.seen(response, purpose=purpose))
        return session

    def seen(self, response, *args, purpose: str = "fetch", **kwargs):
        host = urlsplit(response.url).hostname or "?"
        provider = PROVIDERS.get(host, host)
        left = next((response.headers[h] for h in REMAINING if h in response.headers), None)
        with self._lock:
            self.answers[provider] += 1
            self.spent[(provider, purpose)] += credits(provider, response)
            if left is not None:
                self.left[provider] = left
                self.left_purpose[provider] = purpose
        return response

    def line(self) -> str:
        """`requests: tiingo 27 (left 4973), sifting 17, ...`, most asked first."""
        if not self.answers:
            return "requests: none"
        parts = []
        for provider, n in sorted(self.answers.items(), key=lambda kv: (-kv[1], kv[0])):
            left = self.left.get(provider)
            parts.append(f"{provider} {n}" + (f" (left {left})" if left is not None else ""))
        return "requests: " + ", ".join(parts)

    def rows(self, now: "datetime | None" = None) -> pd.DataFrame:
        """This run's count as usage rows of the day it ends in."""
        now = now or datetime.now(timezone.utc)
        day, at = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
        out = []
        for (provider, purpose), calls in sorted(self.spent.items()):
            mine = self.left_purpose.get(provider) == purpose
            out.append({"day": day, "provider": provider, "purpose": purpose,
                        "calls": int(calls), "left": self.left[provider] if mine else "",
                        "left_at": at if mine else ""})
        return pd.DataFrame(out, columns=COLUMNS)

    def record(self, path: "str | None" = None, now: "datetime | None" = None
               ) -> "str | None":
        """Add this run's count to the usage file (`path`, else USAGE_FILE): a
        day's row grows by each run; the last figure left replaces the one
        before. No file named, nothing written. Returns the path written."""
        path = path or os.environ.get(USAGE_FILE_ENV, "").strip()
        if not path or not self.spent:
            return None
        from jump import atomic

        table = add(read(path), self.rows(now))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        atomic.write_csv(path, table, index=False, lineterminator="\n")
        return path


def read(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLUMNS)
    table = pd.read_csv(path, dtype=str, keep_default_na=False)
    table["calls"] = pd.to_numeric(table["calls"]).astype(int)
    return table[COLUMNS]


def add(table: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """`table` with `rows` added: calls summed per day, provider and purpose,
    and a newer figure left kept over an older one."""
    both = pd.concat([table, rows], ignore_index=True)
    if both.empty:
        return pd.DataFrame(columns=COLUMNS)
    key = ["day", "provider", "purpose"]
    calls = both.groupby(key, as_index=False)["calls"].sum()
    with_left = both[both["left"].astype(str) != ""]
    latest = with_left.groupby(key, as_index=False).last()[key + ["left", "left_at"]]
    out = calls.merge(latest, on=key, how="left").fillna({"left": "", "left_at": ""})
    return out.sort_values(key).reset_index(drop=True)[COLUMNS]


def read_all(directory: str = USAGE_DIR) -> pd.DataFrame:
    """Every workflow's usage file, together."""
    frames = [read(p) for p in sorted(glob.glob(os.path.join(directory, "*.csv")))]
    frames = [f for f in frames if not f.empty]
    return add(pd.concat(frames, ignore_index=True), pd.DataFrame(columns=COLUMNS)) \
        if frames else pd.DataFrame(columns=COLUMNS)


def limits(path: str = LIMITS_PATH) -> pd.DataFrame:
    """Each provider's limit per window and its shares; a share not decided
    yet reads 0."""
    table = pd.read_csv(path, comment="#")
    for col in ("limit", "live", "manual", "dashboard", "votes"):
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).astype(int)
    return table


def spent_in(table: pd.DataFrame, provider: str, window: str, now: datetime) -> int:
    """Calls of `provider` in the day or month `now` is in."""
    if table.empty:
        return 0
    day = now.strftime("%Y-%m-%d")
    mine = table[table["provider"] == provider]
    if window == "day":
        mine = mine[mine["day"] == day]
    elif window == "month":
        mine = mine[mine["day"].str[:7] == day[:7]]
    else:
        return 0                          # hours and minutes: the provider's 429
    return int(mine["calls"].sum())


def _reported_used(table: pd.DataFrame, provider: str, limit: int, now: datetime
                   ) -> "int | None":
    """What the provider says it counted today: its limit less its last figure
    left today. Twelve Data's only."""
    if provider != "twelvedata" or table.empty:
        return None
    today = table[(table["provider"] == provider)
                  & (table["day"] == now.strftime("%Y-%m-%d"))
                  & (table["left"].astype(str).str.strip().str.isdigit())]
    if today.empty:
        return None
    last = today.sort_values("left_at").iloc[-1]
    return limit - int(last["left"])


def warnings(before: pd.DataFrame, after: pd.DataFrame, table: pd.DataFrame,
             now: "datetime | None" = None) -> "list[str]":
    """What this run's count newly crossed: a day or month past WARN_SHARE of a
    limit, or Twelve Data's own count ahead of ours by more than GAP_MARGIN.
    Each is named by the run that crosses it, not by every run after."""
    now = now or datetime.now(timezone.utc)
    out = []
    for row in table.itertuples():
        if row.window not in ("day", "month") or row.limit <= 0:
            continue
        was = spent_in(before, row.provider, row.window, now)
        is_ = spent_in(after, row.provider, row.window, now)
        line = WARN_SHARE * row.limit
        if was < line <= is_:
            out.append(f"{row.provider}: {is_:,} of {row.limit:,} this {row.window} "
                       f"({is_ / row.limit:.0%})")
        if row.window == "day":
            told, said = _reported_used(before, row.provider, row.limit, now), \
                _reported_used(after, row.provider, row.limit, now)
            if said is not None and said - is_ > GAP_MARGIN and \
                    (told is None or told - was <= GAP_MARGIN):
                out.append(f"{row.provider} counts {said:,} today, we counted {is_:,}: "
                           "another caller on the key, or one of ours not counted")
    return out
