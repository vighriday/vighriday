#!/usr/bin/env python3
"""Generate every self-hosted SVG on the profile, in one Amber CRT theme.

Everything here is authored rather than fetched, for two reasons:

* **It cannot 404.** Third-party card services go down, get rate limited, or
  change their API. A committed SVG renders forever.
* **It animates.** GitHub strips ``<script>`` from Markdown but renders images
  untouched, and CSS inside an SVG loaded through ``<img>`` runs normally -
  including ``@keyframes`` and ``prefers-color-scheme``. That is the entire
  animation budget available on a profile README, so it is used deliberately.

No file produced here contains a script element, an event handler attribute, or
an external reference. ``verify_readme.py`` asserts that on every push.
"""

from __future__ import annotations

import argparse
import html
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import (  # noqa: E402
    DISPLAY_NAME,
    MONO_STACK,
    SANS_STACK,
    TAGLINE,
    THEME,
    css_vars,
)

WIDTH = 830  # the widest anything on the page is allowed to be

# Phrases cycled by the hero's terminal typing animation.
HERO_LINES = (
    "AI product manager. I scope it, build it, and ship it.",
    "Generative AI and agent systems, made accountable.",
    "From problem statement to production, end to end.",
    "Evidence before prediction. Verification before shipping.",
)


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def svg_open(width: float, height: float, title: str, desc: str, ids: str = "t d") -> str:
    tid, did = ids.split()
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}" role="img" aria-labelledby="{tid} {did}">'
        f'<title id="{tid}">{html.escape(title)}</title>'
        f'<desc id="{did}">{html.escape(desc)}</desc>'
    )


def crt_defs(prefix: str, width: float, height: float) -> str:
    """Scanline pattern, vignette and phosphor bloom, namespaced per file.

    Ids are prefixed because several of these SVGs can end up inlined into the
    same document by other tooling, and duplicate ids silently cross-wire.
    """
    return (
        "<defs>"
        f'<pattern id="{prefix}scan" width="4" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="4" height="1" fill="var(--scanInk)" opacity="var(--scanOp)"/></pattern>'
        f'<radialGradient id="{prefix}vig" cx="50%" cy="50%" r="75%">'
        '<stop offset="52%" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#000" stop-opacity="var(--vig)"/></radialGradient>'
        f'<linearGradient id="{prefix}glowline" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="var(--accent)" stop-opacity="0"/>'
        '<stop offset="50%" stop-color="var(--accent)" stop-opacity="1"/>'
        '<stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient>'
        "</defs>"
    )


CRT_VARS = dict(
    extra_light={"scanInk": "#7A5A1E", "scanOp": ".06", "vig": ".08"},
    extra_dark={"scanInk": "#000000", "scanOp": ".30", "vig": ".42"},
)


# --------------------------------------------------------------------------
# Signature divider - the element reused between every section
# --------------------------------------------------------------------------
def divider(width: int = WIDTH) -> str:
    """An oscilloscope rail: marching dashes plus a packet running the trace.

    ``stroke-dashoffset`` is animated rather than the element's position, so the
    motion is continuous and seamless at the loop point.
    """
    height = 26
    mid = height / 2
    ticks = "".join(
        f'<rect x="{x}" y="{mid - 4:g}" width="1" height="8" fill="var(--grid)"/>'
        for x in range(0, width + 1, 40)
    )
    css = (
        css_vars()
        + ".rail{stroke:var(--grid);stroke-width:1;fill:none}"
        ".trace{stroke:var(--accent);stroke-width:1.6;fill:none;stroke-dasharray:6 10;"
        "animation:march 2.6s linear infinite}"
        "@keyframes march{to{stroke-dashoffset:-32}}"
        ".packet{animation:run 6.5s cubic-bezier(.45,0,.55,1) infinite}"
        f"@keyframes run{{0%{{transform:translateX(0);opacity:0}}6%{{opacity:1}}"
        f"94%{{opacity:1}}100%{{transform:translateX({width}px);opacity:0}}}}"
    )
    return (
        svg_open(width, height, "Section divider", "An animated amber oscilloscope rail.")
        + f"<style>{css}</style>"
        + ticks
        + f'<path class="rail" d="M0 {mid:g}H{width}"/>'
        + f'<path class="trace" d="M0 {mid:g}H{width}"/>'
        + f'<g class="packet"><circle cx="0" cy="{mid:g}" r="3.2" fill="var(--accent)"/>'
        + f'<circle cx="0" cy="{mid:g}" r="7" fill="var(--accent)" opacity=".18"/></g>'
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Hero - a CRT terminal that types
# --------------------------------------------------------------------------
def hero(width: int = WIDTH, lines: tuple[str, ...] = HERO_LINES) -> str:
    """A power-on terminal panel whose prompt types itself, in pure CSS.

    Each phrase gets a clip rectangle whose width animates from 0 to the exact
    ``textLength`` of that phrase under a ``steps()`` timing function, which is
    what makes it read as typing rather than as a wipe. A caret translates on
    the same schedule so it always sits on the last character.
    """
    height = 186
    char_w = 8.4         # advance of the 14px mono face used below
    font_size = 14
    prompt_x = 34
    base_y = 152
    slot = 4.6           # seconds each phrase owns
    cycle = slot * len(lines)

    keyframes: list[str] = []
    bodies: list[str] = []
    for index, text in enumerate(lines):
        length = len(text) * char_w
        start = index * slot / cycle
        typed = start + (slot * 0.42) / cycle
        hold = start + (slot * 0.86) / cycle
        end = start + slot / cycle
        pct = lambda v: f"{v * 100:.3f}%"  # noqa: E731 - local formatting shorthand

        keyframes.append(
            f"@keyframes type{index}{{"
            f"0%,{pct(start)}{{width:0}}"
            f"{pct(typed)}{{width:{length:.1f}px}}"
            f"{pct(hold)}{{width:{length:.1f}px}}"
            f"{pct(end)}{{width:0}}"
            f"100%{{width:0}}}}"
            f"@keyframes caret{index}{{"
            f"0%,{pct(start)}{{transform:translateX(0);opacity:0}}"
            f"{pct(start + 0.0005)}{{opacity:1}}"
            f"{pct(typed)}{{transform:translateX({length:.1f}px);opacity:1}}"
            f"{pct(hold)}{{transform:translateX({length:.1f}px);opacity:1}}"
            f"{pct(end)}{{transform:translateX(0);opacity:0}}"
            f"100%{{opacity:0}}}}"
        )
        keyframes.append(
            f".clip{index} rect{{animation:type{index} {cycle:g}s steps({len(text)},end) infinite}}"
            f".caret{index}{{animation:caret{index} {cycle:g}s steps({len(text)},end) infinite}}"
        )
        bodies.append(
            f'<defs><clipPath id="clip{index}" class="clip{index}">'
            f'<rect x="{prompt_x + 20}" y="{base_y - font_size:g}" width="0" height="{font_size + 8:g}"/>'
            f"</clipPath></defs>"
            f'<g clip-path="url(#clip{index})">'
            f'<text class="line" x="{prompt_x + 20}" y="{base_y:g}" '
            f'textLength="{length:.1f}" lengthAdjust="spacing" xml:space="preserve">'
            f"{html.escape(text)}</text></g>"
            f'<rect class="caret caret{index}" x="{prompt_x + 20:g}" y="{base_y - font_size + 2:g}" '
            f'width="{char_w:.1f}" height="{font_size:g}" fill="var(--accent)"/>'
        )

    css = (
        css_vars(**CRT_VARS)
        + f".name{{fill:var(--ink);font-family:{SANS_STACK};font-size:44px;font-weight:800;letter-spacing:-1px}}"
        + f".tag{{fill:var(--muted);font-family:{MONO_STACK};font-size:12px;letter-spacing:3.2px}}"
        + f".line{{fill:var(--accent);font-family:{MONO_STACK};font-size:{font_size}px}}"
        + f".sig{{fill:var(--muted);font-family:{MONO_STACK};font-size:10px;letter-spacing:2px}}"
        + f".ps1{{fill:var(--muted);font-family:{MONO_STACK};font-size:{font_size}px}}"
        ".screen{animation:hum 7s ease-in-out infinite}"
        "@keyframes hum{0%,100%{opacity:1}46%{opacity:.96}48%{opacity:1}}"
        ".led{animation:led 2.4s ease-in-out infinite}"
        "@keyframes led{0%,100%{opacity:1}50%{opacity:.25}}"
        ".sweep{animation:sweep 7s linear infinite}"
        f"@keyframes sweep{{0%{{transform:translateY(0);opacity:0}}8%{{opacity:.55}}"
        f"92%{{opacity:.2}}100%{{transform:translateY({height}px);opacity:0}}}}"
        + "".join(keyframes)
    )

    return (
        svg_open(
            width,
            height,
            f"{DISPLAY_NAME} - profile banner",
            "An amber CRT terminal panel that types four rotating lines describing "
            f"{DISPLAY_NAME}'s work, animated with CSS embedded in the SVG.",
        )
        + crt_defs("h", width, height)
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="16" fill="var(--bg)"/>'
        + '<g class="screen">'
        + f'<text class="name" x="{prompt_x}" y="76">{html.escape(DISPLAY_NAME)}</text>'
        + f'<text class="tag" x="{prompt_x + 2}" y="102">{html.escape(TAGLINE)}</text>'
        + f'<rect x="{prompt_x}" y="116" width="240" height="2" fill="url(#hglowline)"/>'
        + f'<text class="ps1" x="{prompt_x}" y="{base_y:g}">&#187;</text>'
        + "".join(bodies)
        + f'<g class="sweep"><rect x="0" y="0" width="{width}" height="1.5" fill="var(--accent)" opacity=".5"/>'
        + f'<rect x="0" y="1.5" width="{width}" height="14" fill="var(--accent)" opacity=".05"/></g>'
        + f'<rect width="{width}" height="{height}" rx="16" fill="url(#hscan)"/>'
        + f'<rect width="{width}" height="{height}" rx="16" fill="url(#hvig)"/>'
        + "</g>"
        + f'<circle class="led" cx="{width - 30}" cy="30" r="4" fill="var(--accent)"/>'
        + f'<text class="sig" x="{width - 44}" y="34" text-anchor="end">ONLINE</text>'
        + f'<rect width="{width}" height="{height}" rx="16" fill="none" stroke="var(--grid)" stroke-width="1"/>'
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Graceful fallbacks - what shows before the first Actions run
# --------------------------------------------------------------------------
def placeholder(label: str, note: str, width: int = WIDTH, height: int = 240) -> str:
    css = (
        css_vars(**CRT_VARS)
        + ".dash{stroke:var(--grid);stroke-width:1;stroke-dasharray:5 8;fill:none;"
        "animation:dash 14s linear infinite}"
        "@keyframes dash{to{stroke-dashoffset:-130}}"
        f".hl{{fill:var(--ink);font-family:{MONO_STACK};font-size:15px;font-weight:700;letter-spacing:2.4px}}"
        f".nt{{fill:var(--muted);font-family:{MONO_STACK};font-size:11px;letter-spacing:.6px}}"
        ".dot{animation:blink 1.6s steps(2,end) infinite}"
        "@keyframes blink{50%{opacity:.2}}"
    )
    return (
        svg_open(width, height, label, note, ids="pt pd")
        + crt_defs("p", width, height)
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)"/>'
        + f'<rect class="dash" x="14" y="14" width="{width - 28}" height="{height - 28}" rx="10"/>'
        + f'<circle class="dot" cx="{width / 2 - 118:g}" cy="{height / 2 - 6:g}" r="4" fill="var(--accent)"/>'
        + f'<text class="hl" x="{width / 2:g}" y="{height / 2:g}" text-anchor="middle">'
        + f"{html.escape(label.upper())}</text>"
        + f'<text class="nt" x="{width / 2:g}" y="{height / 2 + 24:g}" text-anchor="middle">'
        + f"{html.escape(note)}</text>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="url(#pscan)"/>'
        + "</svg>\n"
    )


def signal(timestamp: str, extras: dict[str, str] | None = None, width: int = WIDTH) -> str:
    """The heartbeat strip: proves the whole Actions pipeline is still alive."""
    height = 64
    fields = {"LAST REFRESH": timestamp, **(extras or {})}
    cells = []
    x = 58
    for key, value in fields.items():
        cells.append(
            f'<text class="k" x="{x}" y="26">{html.escape(key)}</text>'
            f'<text class="v" x="{x}" y="45">{html.escape(value)}</text>'
        )
        x += max(150, (len(key) + 4) * 8, (len(value) + 2) * 8)
    css = (
        css_vars(**CRT_VARS)
        + f".k{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:1.8px}}"
        + f".v{{fill:var(--ink);font-family:{MONO_STACK};font-size:12px;font-weight:600}}"
        ".pulse{animation:pulse 2.1s ease-in-out infinite}"
        "@keyframes pulse{0%,100%{opacity:1;r:6}50%{opacity:.3;r:4}}"
        ".ring{animation:ring 2.1s ease-out infinite}"
        "@keyframes ring{0%{r:6;opacity:.5}100%{r:16;opacity:0}}"
    )
    return (
        svg_open(width, height, "Pipeline status", f"All profile workflows healthy. {timestamp}.", ids="st sd")
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="12" fill="var(--bg)" stroke="var(--grid)"/>'
        + '<circle class="ring" cx="30" cy="32" r="6" fill="none" stroke="var(--accent)"/>'
        + '<circle class="pulse" cx="30" cy="32" r="6" fill="var(--accent)"/>'
        + "".join(cells)
        + "</svg>\n"
    )


def quote_card(quote: str, attribution: str = "", width: int = WIDTH) -> str:
    height = 118
    words = " ".join(quote.split())[:190].split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > 74:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    lines = lines[:2]

    css = (
        css_vars(**CRT_VARS)
        + f".q{{fill:var(--ink);font-family:{MONO_STACK};font-size:14px}}"
        + f".by{{fill:var(--muted);font-family:{MONO_STACK};font-size:10px;letter-spacing:1.6px}}"
        ".mk{animation:mk 3.4s ease-in-out infinite}"
        "@keyframes mk{0%,100%{opacity:.9}50%{opacity:.35}}"
    )
    body = "".join(
        f'<text class="q" x="76" y="{46 + i * 22}">{html.escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    return (
        svg_open(width, height, "Quote of the day", quote, ids="qt qd")
        + crt_defs("q", width, height)
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)" stroke="var(--grid)"/>'
        + '<text class="mk" x="30" y="56" fill="var(--accent)" font-family="Georgia, serif" font-size="52">&#8220;</text>'
        + body
        + f'<text class="by" x="76" y="{46 + len(lines) * 22 + 8}">'
        + f"{html.escape(attribution.upper() or 'REFRESHED DAILY BY refresh.yml')}</text>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="url(#qscan)"/>'
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--quote", default="Evidence before prediction. Verification before shipping.")
    parser.add_argument("--attribution", default="")
    parser.add_argument("--streak", default="")
    args = parser.parse_args()

    stamp = args.timestamp or datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    extras = {"BUILD": "PASSING", "THEME": "AMBER CRT"}
    if args.streak:
        extras["STREAK"] = args.streak

    written = [
        write(args.output_dir / "signature-divider.svg", divider()),
        write(args.output_dir / "hero-crt.svg", hero()),
        write(args.output_dir / "profile-signal.svg", signal(stamp, extras)),
        write(args.output_dir / "quote-card.svg", quote_card(args.quote, args.attribution)),
        write(
            args.output_dir / "dynamic-placeholder.svg",
            placeholder(
                "Generated asset pending",
                "Run this section's workflow once and the real asset replaces this card.",
            ),
        ),
        write(
            args.output_dir / "snake-placeholder.svg",
            placeholder(
                "Contribution snake pending",
                "snake.yml publishes the real animation to the output branch.",
                height=200,
            ),
        ),
        write(
            args.output_dir / "metrics-placeholder.svg",
            placeholder(
                "Metrics dashboard pending",
                "metrics.yml needs METRICS_TOKEN before its first run. See SETUP.md.",
                height=300,
            ),
        ),
    ]
    for path in written:
        print(f"build_assets: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
