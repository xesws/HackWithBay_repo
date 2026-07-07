#!/usr/bin/env python3
"""Install the repo's GraphJudge RocketRide node into a local engine tree."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "rocketride_nodes" / "graphjudge_runner"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine-dir",
        default="/workspace/dl/rocketride-engine",
        help="RocketRide engine directory containing the nodes/ folder.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine_dir = Path(args.engine_dir).resolve()
    target = engine_dir / "nodes" / "graphjudge_runner"
    if not (engine_dir / "nodes").is_dir():
        raise SystemExit(f"RocketRide nodes directory not found: {engine_dir / 'nodes'}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SOURCE, target)
    print(f"installed {SOURCE} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
