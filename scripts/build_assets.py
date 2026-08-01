#!/usr/bin/env python3
"""Build dependency-free SVG assets for the profile's single indigo theme."""

from __future__ import annotations

import argparse
import html
from datetime import UTC, datetime
from pathlib import Path

THEME = {
    "accent": "#7C5CFC",
    "accent_soft": "#A78BFA",
    "ink_light": "#21174A",
    "ink_dark": "#EEEAFF",
    "muted_light": "#675E87",
    "muted_dark": "#BDB4DA",
    "grid_light": "#DDD7F2",
    "grid_dark": "#352D55",
}


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def divider() -> str:
    dots = "".join(f'<circle cx="{x}" cy="20" r="{2 if x % 32 else 3}"/>' for x in range(8, 793, 12))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="40" viewBox="0 0 800 40" role="img" aria-label="Animated indigo constellation divider">
<style>
:root {{ --line:{THEME['accent']}; --faint:{THEME['grid_light']}; }}
@media (prefers-color-scheme:dark) {{ :root {{ --line:{THEME['accent_soft']}; --faint:{THEME['grid_dark']}; }} }}
.rail {{ stroke:var(--faint); stroke-width:1; }} .star {{ fill:var(--line); }} .drift {{ animation: drift 7s linear infinite; }}
@keyframes drift {{ from {{ transform:translateX(-42px); }} to {{ transform:translateX(42px); }} }}
</style><path class="rail" d="M0 20H800"/><g class="star drift">{dots}</g></svg>\n'''


def hero_fallback() -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="220" viewBox="0 0 800 220" role="img" aria-labelledby="t d">
<title id="t">Hriday Vig - software engineer and AI systems builder</title><desc id="d">Indigo animated fallback hero banner.</desc>
<style>
:root {{ --bg:#f9f7ff; --ink:{THEME['ink_light']}; --muted:{THEME['muted_light']}; --accent:{THEME['accent']}; }}
@media(prefers-color-scheme:dark) {{ :root {{ --bg:#0f0b1d; --ink:{THEME['ink_dark']}; --muted:{THEME['muted_dark']}; --accent:{THEME['accent_soft']}; }} }}
.orb {{ animation: orbit 9s ease-in-out infinite alternate; }} .pulse {{ animation:pulse 3.4s ease-in-out infinite; }}
@keyframes orbit {{ to {{ transform:translate(112px,-14px); }} }} @keyframes pulse {{ 50% {{ opacity:.35; transform:scale(1.18); }} }}
</style><rect width="800" height="220" rx="22" fill="var(--bg)"/><g class="orb" fill="var(--accent)" opacity=".15"><circle cx="650" cy="60" r="88"/><circle cx="710" cy="135" r="46"/></g><circle class="pulse" cx="650" cy="60" r="8" fill="var(--accent)"/><text x="50" y="96" fill="var(--ink)" font-family="Arial, sans-serif" font-size="38" font-weight="700">Hriday Vig</text><text x="50" y="130" fill="var(--muted)" font-family="Arial, sans-serif" font-size="18">Software engineer · AI systems builder · cloud native</text><path d="M50 160H390" stroke="var(--accent)" stroke-width="3"/></svg>\n'''


def placeholder() -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="300" viewBox="0 0 800 300" role="img" aria-label="Generated-content placeholder">
<style>:root{{--bg:#faf9ff;--ink:{THEME['ink_light']};--line:{THEME['grid_light']};}}@media(prefers-color-scheme:dark){{:root{{--bg:#120d21;--ink:{THEME['ink_dark']};--line:{THEME['grid_dark']};}}}}.dash{{stroke:var(--line);stroke-width:1;stroke-dasharray:5 7;animation:dash 12s linear infinite}}@keyframes dash{{to{{stroke-dashoffset:-120}}}}</style><rect width="800" height="300" rx="18" fill="var(--bg)"/><rect x="18" y="18" width="764" height="264" rx="12" fill="none" class="dash"/><text x="400" y="142" text-anchor="middle" fill="var(--ink)" font-family="Arial, sans-serif" font-size="20" font-weight="700">DYNAMIC ASSET PENDING</text><text x="400" y="174" text-anchor="middle" fill="var(--ink)" opacity=".65" font-family="Arial, sans-serif" font-size="14">Run its workflow once to replace this graceful fallback.</text></svg>\n'''


def signal(timestamp: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="58" viewBox="0 0 800 58" role="img" aria-label="Profile system status: online">
<style>:root{{--ink:{THEME['ink_light']};--muted:{THEME['muted_light']};--accent:{THEME['accent']};}}@media(prefers-color-scheme:dark){{:root{{--ink:{THEME['ink_dark']};--muted:{THEME['muted_dark']};--accent:{THEME['accent_soft']};}}}}.dot{{animation:blink 2.2s ease-in-out infinite}}@keyframes blink{{50%{{opacity:.25;transform:scale(.75)}}}}</style><circle class="dot" cx="28" cy="29" r="8" fill="var(--accent)"/><text x="50" y="26" fill="var(--ink)" font-family="monospace" font-size="14" font-weight="700">SYSTEM STATUS: BUILDING IN PUBLIC</text><text x="50" y="45" fill="var(--muted)" font-family="monospace" font-size="11">LAST REFRESHED: {timestamp}</text></svg>\n'''


def quote_card(quote: str) -> str:
    clean = " ".join(quote.split())[:150]
    words = clean.split()
    midpoint = max(1, len(words) // 2)
    line_one = html.escape(" ".join(words[:midpoint]))
    line_two = html.escape(" ".join(words[midpoint:]))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="112" viewBox="0 0 800 112" role="img" aria-label="Programming quote of the day">
<style>:root{{--bg:#F9F7FF;--ink:{THEME['ink_light']};--muted:{THEME['muted_light']};--accent:{THEME['accent']};}}@media(prefers-color-scheme:dark){{:root{{--bg:#0F0B1D;--ink:{THEME['ink_dark']};--muted:{THEME['muted_dark']};--accent:{THEME['accent_soft']};}}}}.mark{{animation:pulse 3s ease-in-out infinite}}@keyframes pulse{{50%{{opacity:.4;transform:scale(.9)}}}}</style><rect width="800" height="112" rx="16" fill="var(--bg)"/><text class="mark" x="34" y="61" fill="var(--accent)" font-family="Georgia, serif" font-size="54">“</text><text x="82" y="48" fill="var(--ink)" font-family="Arial, sans-serif" font-size="18" font-weight="600">{line_one}</text><text x="82" y="74" fill="var(--ink)" font-family="Arial, sans-serif" font-size="18" font-weight="600">{line_two}</text><text x="82" y="96" fill="var(--muted)" font-family="monospace" font-size="10">PROGRAMMING SIGNAL / REFRESHED DAILY</text></svg>\n'''


def ppm() -> str:
    # A small, abstract indigo avatar in P3 text format; pillow opens it anywhere.
    width = height = 72
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            dx, dy = x - 36, y - 33
            if dx * dx + dy * dy < 17 * 17:
                value = (230, 222, 255) if y < 45 else (124, 92, 252)
            elif 13 < y < 70 and 16 < x < 56 and abs(dx) < (y - 12) * 0.52:
                value = (80, 59, 152)
            elif (x - 36) ** 2 + (y - 33) ** 2 < 25 * 25:
                value = (42, 29, 87)
            else:
                value = (245, 243, 255)
            row.extend(map(str, value))
        pixels.append(" ".join(row))
    return f"P3\n# Replace this placeholder with your photo\n{width} {height}\n255\n" + "\n".join(pixels) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--quote", default="Verification turns shipping into engineering.")
    args = parser.parse_args()
    stamp = args.timestamp or datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    write(args.output_dir / "signature-divider.svg", divider())
    write(args.output_dir / "hero-fallback.svg", hero_fallback())
    write(args.output_dir / "dynamic-placeholder.svg", placeholder())
    write(args.output_dir / "profile-signal.svg", signal(stamp))
    write(args.output_dir / "quote-card.svg", quote_card(args.quote))
    write(args.output_dir / "portrait-placeholder.ppm", ppm())
    print(f"Wrote themed assets to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
