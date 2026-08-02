#!/usr/bin/env python3
"""Photo -> GitHub-safe ASCII portrait assets (Amber CRT).

Why this file is not three lines of ``luminance // 25``
------------------------------------------------------
Naive photo-to-ASCII looks bad for four specific, fixable reasons. Each stage
below exists to kill one of them:

1. *Flat, muddy output.* Raw luminance uses maybe a third of the character
   ramp. Fixed by percentile autocontrast + a gamma pull + optional
   illumination flattening (divide by a heavy blur, which cancels uneven
   lighting the way a homomorphic filter would).
2. *Banding.* Quantising a smooth gradient to nine characters produces visible
   terraces. Fixed with Floyd-Steinberg error diffusion, which trades banding
   for high-frequency noise the eye reads as extra detail.
3. *Wrong subject framing.* A square avatar is mostly backdrop. Fixed with an
   edge-energy crop search that puts the face in the frame.
4. *Rows that do not line up.* Every renderer has a different monospace advance,
   so any hard-coded "characters are 8px wide" guess drifts. Fixed by pinning
   each row with ``textLength`` + ``lengthAdjust="spacing"``: rows all carry the
   same column count and the same target width, so alignment is exact on every
   font, browser and OS - the renderer absorbs the difference into letter
   spacing instead of into cumulative drift.

Dark mode is handled by rendering *two* glyph layers into one file. On a dark
background a dense glyph like ``@`` reads as bright, so the luminance mapping
has to invert; CSS cannot rewrite text content, but it can hide a whole layer.
``prefers-color-scheme`` therefore toggles ``display`` between a light-tuned
layer and a dark-tuned layer inside the same SVG.

Everything animates through CSS embedded in the SVG. GitHub loads these through
``<img>``, where CSS (including media queries and keyframes) runs and
JavaScript does not - so no script is used anywhere in the output.
"""

from __future__ import annotations

import argparse
import html
import random
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import MONO_STACK, THEME, css_vars  # noqa: E402

# --------------------------------------------------------------------------
# Character ramps - always ordered DENSEST -> SPARSEST.
# --------------------------------------------------------------------------
RAMPS: dict[str, str] = {
    # Bob Bemer's classic ten-step ramp: reliable, reads as "terminal".
    "classic": "@%#*+=-:. ",
    # Longer ramp: more tonal steps, better on large renders.
    "fine": "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. ",
    # Unicode block elements: solid, poster-like, excellent at small sizes.
    "blocks": "\u2588\u2593\u2592\u2591 ",
    # Braille is not a ramp - it is handled by real 2x4 dot packing. See
    # ``braille_cells``. The entry exists so ``--ramp braille`` validates.
    "braille": "",
}

#: Braille dot bit positions for U+2800. Column-major, 2 wide x 4 tall.
#: dots 1-3 and 7 fill the left column top-to-bottom, 4-6 and 8 the right.
BRAILLE_BITS = ((0, 3), (1, 4), (2, 5), (6, 7))


# --------------------------------------------------------------------------
# Stage 1 - load
# --------------------------------------------------------------------------
def load_rgb(path: Path) -> Image.Image:
    """Open an image and flatten any alpha onto its own border colour.

    GitHub avatars are circular PNGs: the corners are transparent. Compositing
    them onto white would ring the head with a hard bright square. Compositing
    onto the median colour of the opaque border instead makes the corners
    disappear into the real backdrop.
    """
    image = Image.open(path)
    if image.mode not in ("RGBA", "LA", "P"):
        return image.convert("RGB")

    image = image.convert("RGBA")
    rgba = np.asarray(image, dtype=np.float32)
    alpha = rgba[..., 3] / 255.0
    opaque = alpha > 0.9
    if opaque.any():
        # Sample a one-pixel ring just inside the opaque region.
        eroded = np.zeros_like(opaque)
        eroded[1:-1, 1:-1] = (
            opaque[1:-1, 1:-1] & opaque[:-2, 1:-1] & opaque[2:, 1:-1] & opaque[1:-1, :-2] & opaque[1:-1, 2:]
        )
        ring = opaque & ~eroded
        sample = rgba[..., :3][ring if ring.any() else opaque]
        backdrop = np.median(sample, axis=0)
    else:
        backdrop = np.array([255.0, 255.0, 255.0])

    flat = rgba[..., :3] * alpha[..., None] + backdrop * (1.0 - alpha[..., None])
    return Image.fromarray(flat.round().astype(np.uint8), "RGB")


# --------------------------------------------------------------------------
# Stage 2 - content-aware crop
# --------------------------------------------------------------------------
def edge_energy(image: Image.Image) -> np.ndarray:
    grey = np.asarray(image.convert("L"), dtype=np.float32)
    gx = np.abs(np.diff(grey, axis=1, prepend=grey[:, :1]))
    gy = np.abs(np.diff(grey, axis=0, prepend=grey[:1, :]))
    return gx + gy


def energy_crop(image: Image.Image, aspect: float, head_bias: float = 0.62) -> Image.Image:
    """Find the sub-rectangle of ``aspect`` (w/h) carrying the most detail.

    Uses a summed-area table so every candidate window costs four lookups.
    A vertical prior nudges the window upward: in a portrait the eyes sit above
    centre, and centring on raw energy alone tends to frame the collar.
    """
    energy = edge_energy(image)
    height, width = energy.shape
    integral = np.zeros((height + 1, width + 1), dtype=np.float64)
    integral[1:, 1:] = energy.cumsum(axis=0).cumsum(axis=1)

    def window_sum(top: int, left: int, box_h: int, box_w: int) -> float:
        return float(
            integral[top + box_h, left + box_w]
            - integral[top, left + box_w]
            - integral[top + box_h, left]
            + integral[top, left]
        )

    best = None
    for scale in (1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64):
        box_h = int(min(height, width / aspect) * scale)
        box_w = int(box_h * aspect)
        if box_h < 16 or box_w < 16 or box_h > height or box_w > width:
            continue
        stride = max(2, min(box_h, box_w) // 24)
        for top in range(0, height - box_h + 1, stride):
            for left in range(0, width - box_w + 1, stride):
                density = window_sum(top, left, box_h, box_w) / (box_h * box_w)
                # Prefer windows whose centre sits near the upper-middle third.
                cy = (top + box_h / 2) / height
                cx = (left + box_w / 2) / width
                prior = 1.0 - 0.55 * abs(cy - (1.0 - head_bias)) - 0.45 * abs(cx - 0.5)
                score = density * max(prior, 0.05) * (0.90 + 0.10 * scale)
                if best is None or score > best[0]:
                    best = (score, left, top, box_w, box_h)

    if best is None:
        return image
    _, left, top, box_w, box_h = best
    return image.crop((left, top, left + box_w, top + box_h))


# --------------------------------------------------------------------------
# Stage 3 - tone preparation
# --------------------------------------------------------------------------
def prepare_luma(
    image: Image.Image,
    *,
    gamma: float,
    clip: float,
    sharpen: float,
    flatten: float,
    edge: float = 0.0,
) -> np.ndarray:
    """Return a perceptual 0..1 luminance plane, tuned for a short ramp."""
    if sharpen > 0:
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=int(sharpen * 100), threshold=2))

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    # sRGB -> linear -> Rec.709 luminance -> back to a perceptual curve.
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    luma = linear @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    luma = np.clip(luma, 1e-6, 1.0) ** (1 / 2.2)

    if flatten > 0:
        # Divide out slow illumination changes; keeps local structure only.
        blur = np.asarray(
            Image.fromarray((luma * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(radius=max(image.width, image.height) / 12)
            ),
            dtype=np.float32,
        ) / 255.0
        corrected = luma / np.clip(blur, 0.08, None) * float(np.mean(blur))
        luma = (1 - flatten) * luma + flatten * corrected

    if edge > 0:
        # Darken along gradients. A well-lit face is tonally flat, so pure
        # luminance loses the eyes, nostrils and lip line entirely; pushing
        # edges toward the dark end of the ramp draws them back in as outlines
        # that read correctly in both the light and the inverted dark layer.
        energy = edge_energy(image)
        strength = np.percentile(energy, 97)
        if strength > 1e-3:
            luma = luma - edge * np.clip(energy / strength, 0.0, 1.0)

    if clip > 0:
        low, high = np.percentile(luma, [clip * 100, 100 - clip * 100])
        if high - low > 1e-4:
            luma = (luma - low) / (high - low)
    luma = np.clip(luma, 0.0, 1.0) ** gamma
    return np.clip(luma, 0.0, 1.0)


def resample(plane: np.ndarray, cols: int, rows: int) -> np.ndarray:
    img = Image.fromarray((plane * 255).round().astype(np.uint8), "L")
    img = img.resize((cols, rows), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


# --------------------------------------------------------------------------
# Stage 4 - dithering
# --------------------------------------------------------------------------
def floyd_steinberg(plane: np.ndarray, levels: int) -> np.ndarray:
    """Quantise to ``levels`` steps with error diffusion.

    Returns integer indices in ``0..levels-1`` where 0 is the darkest step.
    Diffusion is what buys back the detail a short ramp would otherwise throw
    away - it is the single biggest visual win in this file.
    """
    work = plane.astype(np.float64).copy()
    rows, cols = work.shape
    out = np.zeros((rows, cols), dtype=np.int16)
    top = levels - 1
    for y in range(rows):
        for x in range(cols):
            old = work[y, x]
            level = int(np.clip(round(old * top), 0, top))
            out[y, x] = level
            error = old - level / top
            if x + 1 < cols:
                work[y, x + 1] += error * 7 / 16
            if y + 1 < rows:
                if x > 0:
                    work[y + 1, x - 1] += error * 3 / 16
                work[y + 1, x] += error * 5 / 16
                if x + 1 < cols:
                    work[y + 1, x + 1] += error * 1 / 16
    return out


# --------------------------------------------------------------------------
# Stage 5 - characters
# --------------------------------------------------------------------------
def ramp_cells(plane: np.ndarray, ramp: str, dither: bool) -> tuple[list[list[str]], list[list[str]]]:
    """Map a luminance grid to (light-mode grid, dark-mode grid).

    ``ramp`` runs densest -> sparsest. On a light background a dense glyph is
    dark ink, so dark pixels take dense glyphs. On a dark background the same
    glyph is bright phosphor, so the mapping is mirrored.
    """
    levels = len(ramp)
    if dither:
        index = floyd_steinberg(plane, levels)
    else:
        index = np.clip((plane * (levels - 1)).round(), 0, levels - 1).astype(np.int16)
    light = [[ramp[value] for value in row] for row in index]
    dark = [[ramp[levels - 1 - value] for value in row] for row in index]
    return light, dark


def braille_cells(plane: np.ndarray, dither: bool) -> tuple[list[list[str]], list[list[str]]]:
    """Real Braille packing: each glyph carries a 2x4 bitmap.

    This is why the mode exists. Treating Braille glyphs as just another
    luminance ramp - which the previous version of this script did - throws
    away the entire point: one Braille cell encodes eight independent dots, so
    the effective resolution is 2x horizontally and 4x vertically, not 1x1.
    """
    rows, cols = plane.shape
    assert rows % 4 == 0 and cols % 2 == 0, "braille grid must be a multiple of 2x4"
    bits = floyd_steinberg(plane, 2) if dither else (plane >= 0.5).astype(np.int16)

    light: list[list[str]] = []
    dark: list[list[str]] = []
    for cell_y in range(rows // 4):
        light_row: list[str] = []
        dark_row: list[str] = []
        for cell_x in range(cols // 2):
            mask = 0
            for dy in range(4):
                for dx in range(2):
                    # bits==0 means dark pixel -> ink on a light background.
                    if bits[cell_y * 4 + dy, cell_x * 2 + dx] == 0:
                        mask |= 1 << BRAILLE_BITS[dy][dx]
            light_row.append(chr(0x2800 + mask))
            dark_row.append(chr(0x2800 + (mask ^ 0xFF)))
        light.append(light_row)
        dark.append(dark_row)
    return light, dark


def matte_mask(plane: np.ndarray, energy: np.ndarray, tolerance: float) -> np.ndarray:
    """Flood the flat backdrop inward from the border.

    Cells that match the border tone and carry no edge detail become blank in
    *both* layers, so the head floats on the terminal background instead of
    sitting in a rectangle of noise.
    """
    rows, cols = plane.shape
    border = np.concatenate([plane[0], plane[-1], plane[:, 0], plane[:, -1]])
    seed = float(np.median(border))
    energy_cut = float(np.percentile(energy, 62))

    mask = np.zeros((rows, cols), dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for y in range(rows):
        for x in (0, cols - 1):
            queue.append((y, x))
    for x in range(cols):
        for y in (0, rows - 1):
            queue.append((y, x))

    while queue:
        y, x = queue.popleft()
        if mask[y, x]:
            continue
        if abs(plane[y, x] - seed) > tolerance or energy[y, x] > energy_cut:
            continue
        mask[y, x] = True
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < rows and 0 <= nx < cols and not mask[ny, nx]:
                queue.append((ny, nx))
    return mask


def apply_matte(grid: list[list[str]], mask: np.ndarray) -> list[list[str]]:
    return [
        [" " if mask[y, x] else char for x, char in enumerate(row)]
        for y, row in enumerate(grid)
    ]


# --------------------------------------------------------------------------
# Stage 6 - SVG
# --------------------------------------------------------------------------
FONT_SIZE = 13.0
CELL_W = FONT_SIZE * 0.60   # target advance; textLength pins it exactly
CELL_H = FONT_SIZE * 1.02   # line box; tuned so the grid reads square-ish


def _rows_markup(
    grid: list[list[str]],
    *,
    layer: str,
    pad_x: float,
    pad_y: float,
    text_len: float,
    animation: str,
    sparkle: random.Random | None,
) -> str:
    parts: list[str] = []
    for index, row in enumerate(grid):
        y = pad_y + FONT_SIZE + index * CELL_H
        classes = f"r {layer}r{index}" if animation == "scanline" else "r"
        if animation == "shimmer" and sparkle is not None:
            payload = _sparkle_spans(row, sparkle)
        else:
            payload = html.escape("".join(row))
        parts.append(
            f'<text class="{classes}" x="{pad_x:.1f}" y="{y:.1f}" '
            f'textLength="{text_len:.1f}" lengthAdjust="spacing" '
            f'xml:space="preserve">{payload}</text>'
        )
    return "".join(parts)


def _sparkle_spans(row: list[str], rng: random.Random) -> str:
    """Run-length encode a row, tagging a few runs as flickering phosphor.

    Splitting every cell into its own ``<tspan>`` would quadruple the file for
    no visual gain, so identical neighbours are merged first.
    """
    out: list[str] = []
    buffer: list[str] = []
    bucket = -1

    def flush() -> None:
        if not buffer:
            return
        text = html.escape("".join(buffer))
        out.append(text if bucket < 0 else f'<tspan class="s{bucket}">{text}</tspan>')

    for char in row:
        want = rng.randrange(6) if (char != " " and rng.random() < 0.055) else -1
        if want != bucket and buffer:
            flush()
            buffer = []
        bucket = want
        buffer.append(char)
    flush()
    return "".join(out)


def _bezel_defs(width: float, height: float) -> str:
    return (
        "<defs>"
        f'<linearGradient id="shell" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="var(--shellA)"/>'
        f'<stop offset="1" stop-color="var(--shellB)"/></linearGradient>'
        f'<radialGradient id="vignette" cx="50%" cy="46%" r="72%">'
        f'<stop offset="55%" stop-color="#000" stop-opacity="0"/>'
        f'<stop offset="100%" stop-color="#000" stop-opacity="var(--vig)"/></radialGradient>'
        f'<radialGradient id="bloom" cx="50%" cy="44%" r="66%">'
        f'<stop offset="0" stop-color="var(--glow)" stop-opacity="var(--bloom)"/>'
        f'<stop offset="100%" stop-color="var(--glow)" stop-opacity="0"/></radialGradient>'
        '<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="1" fill="var(--scanInk)" opacity="var(--scanOp)"/></pattern>'
        "</defs>"
    )


def build_svg(
    light: list[list[str]],
    dark: list[list[str]],
    *,
    label: str,
    animation: str,
    bezel: bool,
    seed: int,
) -> str:
    rows, cols = len(light), len(light[0])
    grid_w = cols * CELL_W
    grid_h = rows * CELL_H
    frame = 16.0 if bezel else 0.0
    pad_x = frame + 14.0
    pad_y = frame + 12.0
    caption_h = 22.0 if bezel else 0.0
    width = round(grid_w + pad_x * 2, 1)
    height = round(grid_h + pad_y * 2 + caption_h, 1)

    stagger = "".join(
        f".lightr{i},.darkr{i}{{animation-delay:{i * 0.035:.3f}s}}" for i in range(rows)
    ) if animation == "scanline" else ""

    sparkle_css = "".join(
        f".s{i}{{animation:flick 2.4s ease-in-out infinite;animation-delay:{i * 0.37:.2f}s}}"
        for i in range(6)
    ) if animation == "shimmer" else ""

    anim_css = ""
    if animation == "scanline":
        # The reveal runs ONCE and holds (`forwards`); only the beam loops.
        # An infinite reveal spends part of every cycle at opacity 0, which on a
        # profile page means visitors periodically see a black rectangle where
        # the portrait should be. The image reloads on each page view, so the
        # boot-up still plays every time someone lands on the profile.
        anim_css = (
            ".r{opacity:0;animation:rv .55s ease-out forwards}"
            "@keyframes rv{from{opacity:0}to{opacity:1}}"
            ".beam{animation:sweep 9s linear infinite}"
            f"@keyframes sweep{{0%{{transform:translateY(0);opacity:0}}"
            f"4%{{opacity:.85}}55%{{opacity:.5}}"
            f"100%{{transform:translateY({grid_h + pad_y:.0f}px);opacity:0}}}}"
        )
    elif animation == "shimmer":
        anim_css = "@keyframes flick{0%,100%{opacity:1}45%{opacity:.35}55%{opacity:1}}"

    crt_css = (
        ".screen{animation:hum 7.2s ease-in-out infinite}"
        "@keyframes hum{0%,100%{opacity:1}47%{opacity:.955}49%{opacity:1}}"
    ) if bezel else ""

    css = (
        css_vars(
            extra_light={
                "shellA": THEME["grid_light"],
                "shellB": THEME["surface_light"],
                "scanInk": "#7A5A1E",
                "scanOp": ".07",
                "vig": ".10",
                "bloom": ".07",
            },
            extra_dark={
                "shellA": "#241B0E",
                "shellB": "#0E0A05",
                "scanInk": "#000000",
                "scanOp": ".34",
                "vig": ".46",
                "bloom": ".16",
            },
        )
        + f".r{{fill:var(--ink);font-family:{MONO_STACK};font-size:{FONT_SIZE}px;"
        "font-weight:500;letter-spacing:0;white-space:pre}"
        ".dark{display:none}"
        "@media(prefers-color-scheme:dark){.light{display:none}.dark{display:inline}}"
        f".cap{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:1.4px}}"
        + crt_css
        + anim_css
        + stagger
        + sparkle_css
    )

    rng_light = random.Random(seed)
    rng_dark = random.Random(seed)
    body_light = _rows_markup(
        light, layer="light", pad_x=pad_x, pad_y=pad_y, text_len=grid_w,
        animation=animation, sparkle=rng_light if animation == "shimmer" else None,
    )
    body_dark = _rows_markup(
        dark, layer="dark", pad_x=pad_x, pad_y=pad_y, text_len=grid_w,
        animation=animation, sparkle=rng_dark if animation == "shimmer" else None,
    )

    shell = ""
    overlay = ""
    caption = ""
    if bezel:
        inner_r = 10
        shell = (
            f'<rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="url(#shell)"/>'
            f'<rect x="{frame / 2:.0f}" y="{frame / 2:.0f}" width="{width - frame:.0f}" '
            f'height="{height - frame - caption_h:.0f}" rx="{inner_r}" fill="var(--bg)"/>'
            f'<rect x="{frame / 2:.0f}" y="{frame / 2:.0f}" width="{width - frame:.0f}" '
            f'height="{height - frame - caption_h:.0f}" rx="{inner_r}" fill="url(#bloom)"/>'
        )
        overlay = (
            f'<rect x="{frame / 2:.0f}" y="{frame / 2:.0f}" width="{width - frame:.0f}" '
            f'height="{height - frame - caption_h:.0f}" rx="{inner_r}" fill="url(#scan)"/>'
            f'<rect x="{frame / 2:.0f}" y="{frame / 2:.0f}" width="{width - frame:.0f}" '
            f'height="{height - frame - caption_h:.0f}" rx="{inner_r}" fill="url(#vignette)"/>'
            f'<rect x="{frame / 2:.0f}" y="{frame / 2:.0f}" width="{width - frame:.0f}" '
            f'height="{height - frame - caption_h:.0f}" rx="{inner_r}" fill="none" '
            'stroke="var(--grid)" stroke-width="1"/>'
        )
        caption = (
            f'<circle cx="{frame + 4:.0f}" cy="{height - caption_h / 2 - 1:.0f}" r="3" fill="var(--accent)"/>'
            f'<text class="cap" x="{frame + 14:.0f}" y="{height - caption_h / 2 + 3:.0f}">'
            f'{html.escape(label)}</text>'
        )

    beam = ""
    if animation == "scanline":
        beam = (
            f'<g class="beam"><rect x="{pad_x - 6:.0f}" y="{pad_y - 4:.0f}" '
            f'width="{grid_w + 12:.0f}" height="2" fill="var(--glow)" opacity=".6"/>'
            f'<rect x="{pad_x - 6:.0f}" y="{pad_y - 2:.0f}" '
            f'width="{grid_w + 12:.0f}" height="10" fill="var(--glow)" opacity=".10"/></g>'
        )

    title = html.escape(f"ASCII portrait of {label}")
    desc = html.escape(
        "A photograph rendered as monospace ASCII art inside an amber CRT frame. "
        "Separate glyph layers are swapped by prefers-color-scheme so the tonal "
        "mapping stays correct in both GitHub themes."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="ttl dsc">'
        f'<title id="ttl">{title}</title><desc id="dsc">{desc}</desc>'
        + (_bezel_defs(width, height) if bezel else "")
        + f"<style>{css}</style>"
        + shell
        + '<g class="screen">'
        + f'<g class="light">{body_light}</g>'
        + f'<g class="dark">{body_dark}</g>'
        + beam
        + overlay
        + "</g>"
        + caption
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Preview - renders exactly what the SVG will show, for local eyeballing
# --------------------------------------------------------------------------
def render_preview(grid: list[list[str]], path: Path, *, dark: bool, scale: int = 2) -> None:
    from PIL import ImageDraw, ImageFont

    cell_w, cell_h = CELL_W * scale, CELL_H * scale
    width = int(len(grid[0]) * cell_w) + 28 * scale
    height = int(len(grid) * cell_h) + 24 * scale
    bg = THEME["bg_dark"] if dark else THEME["bg_light"]
    ink = THEME["ink_dark"] if dark else THEME["ink_light"]
    canvas = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(canvas)

    font = None
    for candidate in (
        r"C:\Windows\Fonts\consola.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        if Path(candidate).exists():
            font = ImageFont.truetype(candidate, int(FONT_SIZE * scale))
            break
    if font is None:
        font = ImageFont.load_default()

    # Draw cell by cell: this reproduces the textLength pinning exactly.
    for y, row in enumerate(grid):
        for x, char in enumerate(row):
            if char == " ":
                continue
            draw.text((14 * scale + x * cell_w, 12 * scale + y * cell_h), char, font=font, fill=ink)
    canvas.save(path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a photograph into animated, dark-mode-aware ASCII SVGs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="source image (JPG/PNG/PPM/WEBP)")
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    parser.add_argument("--name", default="ascii-portrait", help="output basename")
    parser.add_argument("--width", type=int, default=64, help="character columns (24-140)")
    parser.add_argument(
        "--ramp",
        choices=sorted(RAMPS),
        default="blocks",
        help="blocks wins at README scale: at ~6px per cell the eye reads density, not glyph shape",
    )
    parser.add_argument("--aspect", type=float, default=0.82, help="crop aspect ratio, width/height")
    parser.add_argument("--crop", choices=("auto", "none"), default="auto")
    parser.add_argument("--gamma", type=float, default=1.30, help=">1 deepens shadows")
    parser.add_argument("--clip", type=float, default=0.10, help="percentile autocontrast, per side")
    parser.add_argument("--sharpen", type=float, default=1.30, help="unsharp amount, 0 disables")
    parser.add_argument(
        "--flatten",
        type=float,
        default=0.0,
        help="illumination flattening, 0-1; leave off for portraits (it erases the modelling that makes a face read as 3D)",
    )
    parser.add_argument("--edge", type=float, default=0.28, help="darken along gradients, 0 disables")
    parser.add_argument("--matte", type=float, default=0.16, help="backdrop knockout tolerance, 0 disables")
    parser.add_argument("--no-dither", dest="dither", action="store_false", help="disable error diffusion")
    parser.add_argument("--no-bezel", dest="bezel", action="store_false", help="omit the CRT frame")
    parser.add_argument("--label", default=None, help="caption printed on the CRT bezel")
    parser.add_argument("--seed", type=int, default=7, help="seed for shimmer cell selection")
    parser.add_argument("--preview", action="store_true", help="also write PNG previews for local review")
    parser.add_argument("--preview-dir", type=Path, default=Path("preview"))
    parser.add_argument(
        "--animation",
        choices=("all", "none", "scanline", "shimmer"),
        default="all",
        help="which animated variants to emit (a static variant is always written)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 24 <= args.width <= 140:
        raise SystemExit("--width must be between 24 and 140")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    image = load_rgb(args.input)
    if args.crop == "auto":
        image = energy_crop(image, args.aspect)

    braille = args.ramp == "braille"
    # CELL_W / CELL_H is the on-screen aspect of one character box; the source
    # has to be squashed by the same factor or the face comes out stretched.
    # Sizing is always computed in *cells* first - for Braille the sample grid
    # is then 2x wider and 4x taller, because that is what one glyph holds.
    cell_cols = args.width
    cell_rows = max(8, round(image.height / image.width * cell_cols * (CELL_W / CELL_H)))
    cols, rows = (cell_cols * 2, cell_rows * 4) if braille else (cell_cols, cell_rows)

    luma = prepare_luma(
        image,
        gamma=args.gamma,
        clip=args.clip,
        sharpen=args.sharpen,
        flatten=args.flatten,
        edge=args.edge,
    )
    plane = resample(luma, cols, rows)

    if braille:
        light, dark = braille_cells(plane, args.dither)
        mask_plane = resample(luma, cell_cols, cell_rows)
    else:
        light, dark = ramp_cells(plane, RAMPS[args.ramp], args.dither)
        mask_plane = plane

    if args.matte > 0:
        energy = resample(
            np.clip(edge_energy(image) / 255.0, 0, 1), len(light[0]), len(light)
        )
        mask = matte_mask(mask_plane, energy, args.matte)
        light = apply_matte(light, mask)
        dark = apply_matte(dark, mask)

    base = args.output_dir / args.name
    label = args.label or f"HRIDAY.CRT  {len(light[0])}x{len(light)}  AMBER P3"

    base.with_suffix(".txt").write_text(
        "\n".join("".join(row) for row in light) + "\n", encoding="utf-8"
    )
    base.with_name(f"{args.name}-dark").with_suffix(".txt").write_text(
        "\n".join("".join(row) for row in dark) + "\n", encoding="utf-8"
    )

    variants = ["none"]
    if args.animation == "all":
        variants += ["scanline", "shimmer"]
    elif args.animation != "none":
        variants.append(args.animation)

    written: list[Path] = []
    for variant in variants:
        suffix = "static" if variant == "none" else variant
        path = base.with_name(f"{args.name}-{suffix}").with_suffix(".svg")
        path.write_text(
            build_svg(light, dark, label=label, animation=variant, bezel=args.bezel, seed=args.seed),
            encoding="utf-8",
        )
        written.append(path)

    if args.preview:
        preview_dir = args.preview_dir
        preview_dir.mkdir(parents=True, exist_ok=True)
        render_preview(light, preview_dir / f"{args.name}-light.png", dark=False)
        render_preview(dark, preview_dir / f"{args.name}-dark.png", dark=True)
        written.append(preview_dir)

    grid = f"{len(light[0])}x{len(light)}"
    print(f"ascii_portrait: {args.input} -> {grid} cells, ramp={args.ramp}, dither={args.dither}")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
