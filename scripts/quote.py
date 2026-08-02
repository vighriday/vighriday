#!/usr/bin/env python3
"""Print the quote of the day.

Deliberately offline. A jokes/quotes API is one more service that can rate
limit, go down, or start returning something you would not want rendered on
your own profile unattended. Rotating a curated list by day-of-year gives the
same "it changed today" effect with none of that exposure, and it still works
when the runner has no network.

``--source api`` is available if you would rather take the risk; it falls back
to the local list on any failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime

QUOTES: list[str] = [
    "Evidence before prediction. Verification before shipping.",
    "A system you cannot observe is a system you do not operate.",
    "Programs must be written for people to read, and only incidentally for machines to execute.",
    "Simplicity is prerequisite for reliability.",
    "Make it work, make it right, make it fast.",
    "The most damaging phrase in the language is: we have always done it this way.",
    "Testing shows the presence, not the absence of bugs.",
    "Premature optimisation is the root of all evil.",
    "Any fool can write code a computer understands. Good programmers write code humans understand.",
    "Deleted code is debugged code.",
    "If you cannot roll it back, you have not shipped it - you have gambled.",
    "An autonomous system without a stop button is not autonomy, it is abdication.",
    "Controlling complexity is the essence of computer programming.",
    "The cheapest, fastest and most reliable components are those that are not there.",
    "First, solve the problem. Then, write the code.",
    "Everything should be made as simple as possible, but not simpler.",
    "Weeks of coding can save you hours of planning.",
    "It is not a bug, it is an undocumented invariant.",
    "Good architecture makes the system easy to change in the ways it is likely to change.",
    "Talk is cheap. Show me the code.",
    "The best error message is the one that never shows up.",
    "Legacy code is simply code without tests.",
    "Debugging is twice as hard as writing the code in the first place.",
    "Measure. Do not guess. Then measure again.",
    "A model that cannot explain itself cannot be held accountable.",
    "Documentation is a love letter you write to your future self.",
    "The function of good software is to make the complex appear simple.",
    "There are two ways of constructing software: make it so simple there are obviously no deficiencies, or so complex there are no obvious deficiencies.",
    "Fast is fine, but accuracy is everything.",
    "Complexity kills. It sucks the life out of developers and makes products hard to plan and build.",
    "You cannot improve what you do not measure, and you cannot trust what you do not verify.",
    "Every line of code is a liability until it earns its place.",
    "An agent that cannot be interrupted is not a tool, it is a hazard.",
    "Correctness is not a feature you add later.",
    "The purpose of abstraction is not to be vague, but to create a new semantic level in which one can be absolutely precise.",
    "Optimism is an occupational hazard of programming; feedback is the treatment.",
    "Ship small, ship often, and keep the rollback path warm.",
    "Reliability is invisible until the moment it is not.",
]


def local_quote(when: datetime) -> str:
    return QUOTES[when.timetuple().tm_yday % len(QUOTES)]


def api_quote(timeout: int = 10) -> str | None:
    try:
        request = urllib.request.Request(
            "https://api.quotable.io/random?tags=technology|wisdom&maxLength=140",
            headers={"User-Agent": "profile-readme/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
        content = str(payload.get("content", "")).strip()
        return content or None
    except Exception as exc:  # noqa: BLE001 - any failure means "use the local list"
        print(f"quote: API unavailable ({exc}); using the local list", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=("local", "api"), default="local")
    args = parser.parse_args()

    quote = (api_quote() if args.source == "api" else None) or local_quote(datetime.now(UTC))
    print(quote)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
