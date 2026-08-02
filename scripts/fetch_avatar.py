#!/usr/bin/env python3
"""Download a GitHub avatar to use as the ASCII portrait source.

Kept separate from ``ascii_portrait.py`` so the renderer never needs network
access - CI regenerates the portrait from a committed file, not a live fetch.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import USERNAME  # noqa: E402

UA = "Mozilla/5.0 (compatible; profile-readme-build/1.0)"


def fetch(username: str, size: int, destination: Path) -> Path:
    url = f"https://github.com/{username}.png?size={size}"
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    if len(payload) < 1024:
        raise SystemExit(f"avatar for {username!r} came back empty ({len(payload)} bytes)")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=USERNAME)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--out", type=Path, default=Path("assets/portrait-source.png"))
    args = parser.parse_args()
    path = fetch(args.username, args.size, args.out)
    print(f"fetch_avatar: {args.username} -> {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
