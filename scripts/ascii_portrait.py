#!/usr/bin/env python3
"""Render a photograph as portable, GitHub-safe ASCII assets.

The generated SVGs contain all animation and dark-mode CSS internally, so they
remain animated when GitHub renders them through an ``<img>`` tag.
"""

from __future__ import annotations

import argparse
import html
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

RAMPS = {
    "classic": "@%#*+=-:. ",
    "blocks": "█▓▒░ ",
    # A dense, intentionally varied Unicode Braille ramp for high-detail output.
    "braille": "⣿⣷⣶⣤⣄⣀⡀⠁ ",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Photo -> static and animated ASCII SVGs")
    parser.add_argument("input", type=Path, help="source image (JPG, PNG, or PPM)")
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    parser.add_argument("--name", default="ascii-portrait", help="output basename")
    parser.add_argument("--width", type=int, default=62, help="character columns (32-100)")
    parser.add_argument("--ramp", choices=RAMPS, default="classic")
    parser.add_argument("--edge", action="store_true", help="mix an edge pass into luminance")
    parser.add_argument("--color", action="store_true", help="preserve colour in SVG and ANSI text")
    parser.add_argument(
        "--animation",
        choices=("all", "none", "scanline", "shimmer"),
        default="all",
        help="which animated SVG variant(s) to create",
    )
    return parser.parse_args()


def load_pixels(path: Path, columns: int, edge: bool) -> tuple[np.ndarray, np.ndarray]:
    if not 32 <= columns <= 100:
        raise ValueError("--width must be between 32 and 100")
    image = Image.open(path).convert("RGB")
    # Terminal characters are roughly twice as high as they are wide.
    rows = max(12, round(image.height / image.width * columns * 0.48))
    image = ImageOps.fit(image, (columns, rows), method=Image.Resampling.LANCZOS)
    colour = np.asarray(image)
    luminance = np.asarray(image.convert("L"), dtype=np.float32)
    if edge:
        edges = np.asarray(image.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
        luminance = np.clip(luminance * 0.76 + (255 - edges) * 0.24, 0, 255)
    return luminance, colour


def character_grid(luminance: np.ndarray, ramp_name: str) -> list[list[str]]:
    ramp = RAMPS[ramp_name]
    levels = len(ramp) - 1
    return [[ramp[round(value / 255 * levels)] for value in row] for row in luminance]


def ansi_text(chars: list[list[str]], colours: np.ndarray) -> str:
    lines = []
    for row, rgb_row in zip(chars, colours):
        fragments = [f"\033[38;2;{r};{g};{b}m{char}" for char, (r, g, b) in zip(row, rgb_row)]
        lines.append("".join(fragments) + "\033[0m")
    return "\n".join(lines) + "\n"


def plain_text(chars: list[list[str]]) -> str:
    return "\n".join("".join(row) for row in chars) + "\n"


def text_spans(row: list[str], rgb_row: np.ndarray | None, shimmer: bool, seed: int) -> str:
    if rgb_row is None:
        return html.escape("".join(row))
    randomizer = random.Random(seed)
    spans = []
    for char, (r, g, b) in zip(row, rgb_row):
        classes = " class=\"spark\"" if shimmer and randomizer.random() < 0.075 else ""
        delay = f" style=\"animation-delay:{randomizer.uniform(0, 2.8):.2f}s\"" if classes else ""
        spans.append(f"<tspan fill=\"rgb({r},{g},{b})\"{classes}{delay}>{html.escape(char)}</tspan>")
    return "".join(spans)


def svg(chars: list[list[str]], colours: np.ndarray, name: str, animation: str, colour_mode: bool) -> str:
    font_size, line_height, padding = 13, 16, 20
    width = min(800, max(440, len(chars[0]) * 8 + padding * 2))
    height = len(chars) * line_height + padding * 2
    css = """
      :root { --ink: #1f1748; --glow: #6d4aff; }
      @media (prefers-color-scheme: dark) { :root { --ink: #e9e1ff; --glow: #a78bfa; } }
      .row { fill: var(--ink); font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; font-size: 13px; }
      .spark { animation: shimmer 2.9s ease-in-out infinite; transform-origin: center; }
      @keyframes shimmer { 0%, 100% { opacity: .52; filter: none; } 50% { opacity: 1; filter: drop-shadow(0 0 3px var(--glow)); } }
      @keyframes reveal { from { opacity: 0; transform: translateX(-12px); } to { opacity: 1; transform: translateX(0); } }
      @keyframes scan { 0% { transform: translateY(-20px); opacity: 0; } 35% { opacity: .55; } 100% { transform: translateY(100%); opacity: 0; } }
      .reveal { opacity: 0; animation: reveal .5s ease-out forwards; }
      .scanline { animation: scan 3.2s linear infinite; }
    """
    body = []
    for i, row in enumerate(chars):
        attrs = ""
        if animation == "scanline":
            attrs = f' class="row reveal" style="animation-delay:{i * 0.055:.2f}s"'
        else:
            attrs = ' class="row"'
        payload = text_spans(row, colours[i] if colour_mode else None, animation == "shimmer", i)
        body.append(f'<text x="{padding}" y="{padding + font_size + i * line_height}"{attrs}>{payload}</text>')
    scan = f'<rect class="scanline" x="0" y="0" width="{width}" height="2" fill="var(--glow)" opacity=".55"/>' if animation == "scanline" else ""
    title = html.escape(f"ASCII portrait: {name}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{title}</title><desc id="desc">An ASCII-art portrait rendered from a photograph.</desc>
  <style>{css}</style>
  <rect width="100%" height="100%" rx="14" fill="transparent"/>
  <g>{''.join(body)}</g>{scan}
</svg>\n'''


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    luminance, colours = load_pixels(args.input, args.width, args.edge)
    chars = character_grid(luminance, args.ramp)
    base = args.output_dir / args.name
    base.with_suffix(".txt").write_text(plain_text(chars), encoding="utf-8")
    if args.color:
        base.with_name(f"{args.name}-color").with_suffix(".txt").write_text(ansi_text(chars, colours), encoding="utf-8")
    base.with_name(f"{args.name}-static").with_suffix(".svg").write_text(svg(chars, colours, args.name, "none", args.color), encoding="utf-8")
    animations = ("scanline", "shimmer") if args.animation == "all" else (args.animation,)
    for animation in animations:
        if animation != "none":
            base.with_name(f"{args.name}-{animation}").with_suffix(".svg").write_text(svg(chars, colours, args.name, animation, args.color), encoding="utf-8")
    print(f"Wrote ASCII assets to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
