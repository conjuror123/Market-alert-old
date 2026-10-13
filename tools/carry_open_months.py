"""One-off: the October hours of the four instruments MarketWatch serves only about
nine trading days back - the Bund, the long gilt, TTF and Japan's 10-year yield -
laid into the live store's open months.

    PYTHONPATH=. python -m tools.carry_open_months [--carry DIR] [--bars-dir DIR]

The development branch fetched them (the gilt's 10-01 and 10-02 are Dukascopy's,
from its history build); open months live on the release, not in git
(tools/hot_bars.sh), so they come as files in data/jump/carry, one per store, and
the hourly run lays them down after restoring the open months and saves them with
its own. Only hours the store lacks are passed on: in an open month bars.merge lets
the incoming row win, and a bar the live run fetched since is the fresher. Deleted,
with its step in price-monitor.yml and data/jump/carry, once the archive holds them
(the manual's rule).
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import pandas as pd

from jump import bars

CARRY_DIR = os.path.join("data", "jump", "carry")


def carry(carry_dir: str = CARRY_DIR, bars_dir: str = bars.DEFAULT_BARS_DIR) -> "dict[str, int]":
    """{store: hours added} for each carry file."""
    out = {}
    for path in sorted(glob.glob(os.path.join(carry_dir, "*.csv"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        store = bars.store_path(bars_dir, stem)
        have = set(bars.load(store)["hour_utc"].astype(int))
        rows = pd.read_csv(path)
        out[stem] = bars.merge(store, rows[~rows["hour_utc"].astype(int).isin(have)])
    return out


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Lay the carried October hours into the store")
    parser.add_argument("--carry", default=CARRY_DIR)
    parser.add_argument("--bars-dir", default=bars.DEFAULT_BARS_DIR)
    args = parser.parse_args(argv)
    for stem, added in carry(args.carry, args.bars_dir).items():
        print(f"{stem}: {added} hours added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
