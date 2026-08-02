#!/usr/bin/env python3
"""Repaint the whole profile from one palette edit.

The README hard-codes ~60 hex values, because every third-party card service
takes its colours as query parameters and there is no variable to point them at.
That makes "change the theme" a find-and-replace across dozens of URLs, which is
exactly the kind of job that gets done 95% correctly and leaves one stubborn
off-palette card behind.

So the palette that was last written to disk is recorded in ``.theme-lock.json``.
This script diffs the lock against the live ``THEME``, builds an old-to-new
colour map, and rewrites every occurrence in one pass - then updates the lock.

    1. edit THEME in scripts/theme.py
    2. python scripts/build.py

``verify_readme.py`` then fails CI if any colour outside the palette survived.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import THEME  # noqa: E402

LOCK = Path(".theme-lock.json")


def load_lock(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build_map(old: dict[str, str], new: dict[str, str]) -> dict[str, str]:
    """Map every changed colour, in both ``#RRGGBB`` and bare ``RRGGBB`` form."""
    mapping: dict[str, str] = {}
    for key, new_value in new.items():
        old_value = old.get(key)
        if not old_value or old_value.lower() == new_value.lower():
            continue
        bare_old, bare_new = old_value.lstrip("#"), new_value.lstrip("#")
        for variant in (bare_old.lower(), bare_old.upper()):
            mapping[f"#{variant}"] = new_value
            mapping[variant] = bare_new
    return mapping


def repaint(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    if not mapping:
        return text, 0
    # Longest first so "#RRGGBB" is consumed before the bare "RRGGBB" inside it.
    pattern = re.compile("|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))
    count = 0

    def swap(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return mapping[match.group(0)]

    return pattern.sub(swap, text), count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--files", nargs="*", type=Path, default=[Path("README.md"), Path("SETUP.md")])
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()

    old = load_lock(args.lock)
    mapping = build_map(old, THEME)

    if not old:
        args.lock.write_text(json.dumps(THEME, indent=2) + "\n", encoding="utf-8")
        print(f"retheme: initialised {args.lock} from the current palette; nothing to repaint")
        return 0

    if not mapping:
        print("retheme: palette unchanged since the last build")
        return 0

    changed = {k: (old[k], v) for k, v in THEME.items() if old.get(k, "").lower() != v.lower()}
    print(f"retheme: {len(changed)} colour(s) changed")
    for key, (was, now) in changed.items():
        print(f"  {key:<14} {was} -> {now}")

    total = 0
    for path in args.files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        updated, count = repaint(text, mapping)
        total += count
        if count and not args.check:
            path.write_text(updated, encoding="utf-8")
        print(f"  {path}: {count} replacement(s){' (dry run)' if args.check else ''}")

    if args.check:
        return 1 if total else 0
    args.lock.write_text(json.dumps(THEME, indent=2) + "\n", encoding="utf-8")
    print(f"retheme: {total} replacement(s) written; lock updated")
    print("retheme: now run scripts/build_assets.py and scripts/ascii_portrait.py to repaint the SVGs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
