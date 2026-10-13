"""One-off: each provider's calls a day over the last DAYS, from the runs' own logs -
the starting point of data/jump/usage (jump.usage).

    python -m tools.usage_from_logs OUT_DIR [--days 30]

Through GitHub's API (GITHUB_TOKEN, GITHUB_REPOSITORY), reads every run in the
window of the hourly workflow (price-monitor.yml) and the history walks
(backfill-jump-bars.yml) on the default branch, and of the dashboard (measure.yml)
on any branch. In each log, the lines `requests: tiingo 27 (left 4973), sifting
17, ...` (jump.usage.Usage.line) are added up per UTC day, by the line's own time,
and provider: the hourly run's as fetch (its vote's calls among them: one session
then), the walks' as manual, the dashboard's as dashboard. Twelve Data counts
credits, which the line does not: the live run asks its TWELVEDATA_BATCH funds in one
request an hour, so a request is that many credits (its `api-credits-left` is the
minute's, not the day's). Writes hourly.csv, manual.csv and dashboard.csv in jump.usage's form, and
prints them. Deleted once its rows are committed (the manual's rule).
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from jump import usage

API = "https://api.github.com"
WORKFLOWS = {"price-monitor.yml": "fetch", "backfill-jump-bars.yml": "manual",
             "measure.yml": "dashboard"}
FILES = {"fetch": "hourly.csv", "manual": "manual.csv", "dashboard": "dashboard.csv"}
TWELVEDATA_BATCH = 7          # the live basket's Twelve Data funds, one batch
LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\S*\s.*?requests: (.+)$")
PART = re.compile(r"([\w.\-]+) (\d+)(?: \(left ([^)]*)\))?")
# Leaves GitHub's API this many of its hourly requests for everything else.
API_FLOOR = 100


def parse(text: str) -> "list[tuple[str, str, int, str]]":
    """(time, provider, requests, left) for each provider on each requests line."""
    out = []
    for line in text.splitlines():
        m = LINE.match(line.strip("\ufeff"))
        if not m or m.group(2).strip() == "none":
            continue
        for part in PART.finditer(m.group(2)):
            out.append((m.group(1), part.group(1), int(part.group(2)), part.group(3) or ""))
    return out


def day_rows(seen: "list[tuple[str, str, int, str]]", purpose: str) -> pd.DataFrame:
    """jump.usage rows: requests summed per day and provider (Twelve Data's as
    credits), the last figure left kept."""
    if not seen:
        return pd.DataFrame(columns=usage.COLUMNS)
    frame = pd.DataFrame(seen, columns=["at", "provider", "calls", "left"]).sort_values("at")
    frame["day"], frame["left_at"] = frame["at"].str[:10], frame["at"].str[11:16]
    rows = []
    for (day, provider), g in frame.groupby(["day", "provider"]):
        with_left = g[g["left"] != ""]
        left = with_left.iloc[-1] if len(with_left) else None
        calls = int(g["calls"].sum())
        if provider == "twelvedata":
            calls *= TWELVEDATA_BATCH
        rows.append({"day": day, "provider": provider, "purpose": purpose, "calls": calls,
                     "reported": "", "left": "" if left is None else left["left"],
                     "left_at": "" if left is None else left["left_at"]})
    return pd.DataFrame(rows, columns=usage.COLUMNS)


class GitHub:
    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}",
                                     "Accept": "application/vnd.github+json"})
        self.left = None

    def get(self, path: str, **params):
        if self.left is not None and self.left < API_FLOOR:
            raise RuntimeError(f"GitHub's API has {self.left} requests left this hour")
        resp = self.session.get(f"{API}/repos/{self.repo}{path}", params=params, timeout=60)
        self.left = int(resp.headers.get("X-RateLimit-Remaining", "1000"))
        resp.raise_for_status()
        return resp

    def runs(self, workflow: str, since: datetime, branch: "str | None"):
        page = 1
        while True:
            params = {"per_page": 100, "page": page,
                      "created": f">={since:%Y-%m-%dT%H:%M:%SZ}"}
            if branch:
                params["branch"] = branch
            got = self.get(f"/actions/workflows/{workflow}/runs", **params).json()
            runs = got.get("workflow_runs", [])
            yield from runs
            if len(runs) < 100:
                return
            page += 1

    def log_text(self, run_id: int) -> str:
        resp = self.get(f"/actions/runs/{run_id}/logs")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            # The whole-job files hold every step's lines; the per-step files repeat them.
            names = [n for n in z.namelist() if "/" not in n] or z.namelist()
            return "\n".join(z.read(n).decode("utf-8", "replace") for n in names)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)
    gh = GitHub(os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    default = gh.get("").json()["default_branch"]
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    os.makedirs(args.out_dir, exist_ok=True)
    for workflow, purpose in WORKFLOWS.items():
        seen, runs, gone = [], 0, 0
        branch = None if purpose == "dashboard" else default
        for run in gh.runs(workflow, since, branch):
            try:
                seen += parse(gh.log_text(run["id"]))
                runs += 1
            except requests.HTTPError:
                gone += 1                    # a log expired or never written
            except RuntimeError as exc:
                print(f"stopped: {exc}", file=sys.stderr)
                break
            time.sleep(0.2)
        rows = day_rows(seen, purpose)
        path = os.path.join(args.out_dir, FILES[purpose])
        rows.to_csv(path, index=False, lineterminator="\n")
        print(f"== {workflow}: {runs} runs read, {gone} without a log, "
              f"{len(rows)} rows -> {path}")
        print(rows.to_csv(index=False, lineterminator="\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
