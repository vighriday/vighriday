#!/usr/bin/env python3
"""Rebuild every generated artefact on the profile, in dependency order.

    python scripts/build.py              # full local rebuild + verify
    python scripts/build.py --no-network # skip anything that needs the internet
    python scripts/build.py --fast       # assets only, skip the portrait

The same entry point runs locally and in ``refresh.yml``, so what you see on
your machine is what CI publishes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PORTRAIT_SOURCE = ROOT / "assets" / "portrait-source.png"


def run(step: str, argv: list[str], *, optional: bool = False) -> bool:
    print(f"\n=== {step} ===", flush=True)
    result = subprocess.run([sys.executable, *argv], cwd=ROOT)
    if result.returncode == 0:
        return True
    if optional:
        print(f"--- {step} failed ({result.returncode}); continuing because it is optional", flush=True)
        return False
    print(f"--- {step} FAILED ({result.returncode})", flush=True)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-network", action="store_true", help="skip avatar fetch and GitHub API charts")
    parser.add_argument("--fast", action="store_true", help="skip the ASCII portrait (the slow step)")
    parser.add_argument("--preview", action="store_true", help="also write local PNG previews of the portrait")
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--quote", default=None)
    args = parser.parse_args()

    failures: list[str] = []

    # 1. Theme drift first: the README must be repainted before it is verified.
    if not run("retheme", [str(SCRIPTS / "retheme.py")]):
        failures.append("retheme")

    # 2. Portrait source. Optional: a committed source beats a live fetch.
    if not args.no_network and not PORTRAIT_SOURCE.exists():
        run("fetch avatar", [str(SCRIPTS / "fetch_avatar.py")], optional=True)

    # 3. ASCII portrait.
    if not args.fast:
        if PORTRAIT_SOURCE.exists():
            portrait = [str(SCRIPTS / "ascii_portrait.py"), str(PORTRAIT_SOURCE)]
            if args.preview:
                portrait.append("--preview")
            if not run("ascii portrait", portrait):
                failures.append("ascii portrait")
        else:
            print("\n=== ascii portrait ===\nskipped: assets/portrait-source.png is missing", flush=True)

    # 4. Static themed SVGs.
    assets = [str(SCRIPTS / "build_assets.py")]
    if args.timestamp:
        assets += ["--timestamp", args.timestamp]
    if args.quote:
        assets += ["--quote", args.quote]
    if not run("themed assets", assets):
        failures.append("themed assets")

    # 5. Charts from the GitHub API. Degrade rather than fail: no token locally
    #    means placeholders, which is the correct offline behaviour.
    if not args.no_network:
        run("github charts", [str(SCRIPTS / "gh_charts.py")], optional=True)

    # 6. The gate.
    if not run("verify", [str(SCRIPTS / "verify_readme.py")]):
        failures.append("verify")

    print("\n" + "=" * 60)
    if failures:
        print(f"build: FAILED - {', '.join(failures)}")
        return 1
    print("build: all steps passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
