#!/usr/bin/env python3
"""Amber CRT - the single source of truth for every colour on the profile.

Nothing else in this repository is allowed to hard-code a hex value. Generated
SVGs import ``THEME``; third-party card URLs get their query parameters from
``card_params()``; ``retheme.py`` rewrites README.md from the same table.

Change a colour here, run ``python scripts/build.py``, and the entire profile
follows - assets, cards, badges, and README alike.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
# The look is a phosphor terminal: a narrow amber ramp over a warm near-black,
# mirrored into a warm off-white for readers browsing GitHub in light mode.

THEME: dict[str, str] = {
    # Accent ramp - shared by both modes so the brand colour never shifts.
    "accent": "#FFB000",       # primary phosphor amber
    "accent_deep": "#FF8A00",  # saturated shadow of the accent
    "accent_soft": "#FFD37A",  # highlight / hover tone
    # Dark mode
    "bg_dark": "#0B0906",
    "surface_dark": "#14100A",
    "ink_dark": "#FFE9BE",
    "muted_dark": "#B8925A",
    "grid_dark": "#3A2C12",
    # Light mode
    "bg_light": "#FFFBF2",
    "surface_light": "#FFF6E6",
    "ink_light": "#241802",
    "muted_light": "#7A5A1E",
    "grid_light": "#F0DFBE",
}

#: Every shields.io badge on the profile uses this one style. No exceptions.
BADGE_STYLE = "for-the-badge"

#: Timezone offset used by any "commits by hour" visual (IST).
UTC_OFFSET = 5.5

#: Identity. Kept beside the palette so one file drives every generated string.
USERNAME = "vighriday"
DISPLAY_NAME = "Hriday Vig"
TAGLINE = "Software Engineer / AI Systems Builder / Cloud Native"

#: Branch that GitHub Actions publishes generated assets to.
OUTPUT_BRANCH = "output"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def bare(key: str) -> str:
    """Hex without the leading ``#`` - the form most card services expect."""
    return THEME[key].lstrip("#")


def css_vars(extra_light: dict[str, str] | None = None, extra_dark: dict[str, str] | None = None) -> str:
    """Emit the ``:root`` + ``prefers-color-scheme`` block shared by every SVG.

    Generated SVGs are loaded through ``<img>``, where GitHub's sanitizer never
    runs and JavaScript never executes - but CSS, including media queries, does.
    That is the only reliable way to make one asset work in both GitHub themes.
    """
    light = {
        "bg": THEME["bg_light"],
        "surface": THEME["surface_light"],
        "ink": THEME["ink_light"],
        "muted": THEME["muted_light"],
        "grid": THEME["grid_light"],
        "accent": THEME["accent_deep"],
        "glow": THEME["accent"],
        **(extra_light or {}),
    }
    dark = {
        "bg": THEME["bg_dark"],
        "surface": THEME["surface_dark"],
        "ink": THEME["ink_dark"],
        "muted": THEME["muted_dark"],
        "grid": THEME["grid_dark"],
        "accent": THEME["accent"],
        "glow": THEME["accent_soft"],
        **(extra_dark or {}),
    }
    light_body = "".join(f"--{k}:{v};" for k, v in light.items())
    dark_body = "".join(f"--{k}:{v};" for k, v in dark.items())
    return (
        f":root{{{light_body}}}"
        f"@media(prefers-color-scheme:dark){{:root{{{dark_body}}}}}"
    )


#: Monospace stack that resolves on every platform GitHub is read on.
MONO_STACK = (
    "ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,"
    "'DejaVu Sans Mono','Liberation Mono',monospace"
)

#: Sans stack for banner/label text inside generated SVGs.
SANS_STACK = (
    "ui-sans-serif,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
)


def card_params(kind: str) -> str:
    """Return the themed query string for a third-party card service.

    Every service is fed the identical palette so the page reads as one system
    rather than a scrapbook of default themes.
    """
    d, l = "dark", "light"  # noqa: E741 - short names keep the table readable

    tables: dict[str, dict[str, str]] = {
        # anuraghazra/github-readme-stats - stats, top-langs, and pin cards
        "stats": {
            d: (
                f"title_color={bare('accent')}&text_color={bare('ink_dark')}"
                f"&icon_color={bare('accent_soft')}&bg_color={bare('bg_dark')}"
                f"&border_color={bare('grid_dark')}"
            ),
            l: (
                f"title_color={bare('accent_deep')}&text_color={bare('ink_light')}"
                f"&icon_color={bare('accent_deep')}&bg_color={bare('bg_light')}"
                f"&border_color={bare('grid_light')}"
            ),
        },
        # DenverCoder1/github-readme-streak-stats
        "streak": {
            d: (
                f"background={bare('bg_dark')}&border={bare('grid_dark')}"
                f"&stroke={bare('grid_dark')}&ring={bare('accent')}"
                f"&fire={bare('accent_soft')}&currStreakLabel={bare('accent')}"
                f"&sideLabels={bare('muted_dark')}&currStreakNum={bare('ink_dark')}"
                f"&sideNums={bare('ink_dark')}&dates={bare('muted_dark')}"
            ),
            l: (
                f"background={bare('bg_light')}&border={bare('grid_light')}"
                f"&stroke={bare('grid_light')}&ring={bare('accent_deep')}"
                f"&fire={bare('accent_deep')}&currStreakLabel={bare('accent_deep')}"
                f"&sideLabels={bare('muted_light')}&currStreakNum={bare('ink_light')}"
                f"&sideNums={bare('ink_light')}&dates={bare('muted_light')}"
            ),
        },
        # ashutosh00710/github-readme-activity-graph
        "activity": {
            d: (
                f"bg_color={bare('bg_dark')}&color={bare('ink_dark')}"
                f"&line={bare('accent')}&point={bare('accent_soft')}"
                f"&area_color={bare('accent')}&title_color={bare('accent')}"
                "&area=true&hide_border=true"
            ),
            l: (
                f"bg_color={bare('bg_light')}&color={bare('ink_light')}"
                f"&line={bare('accent_deep')}&point={bare('accent_deep')}"
                f"&area_color={bare('accent')}&title_color={bare('accent_deep')}"
                "&area=true&hide_border=true"
            ),
        },
    }
    if kind not in tables:
        raise KeyError(f"unknown card kind: {kind!r}")
    return f"{tables[kind]['dark']}||{tables[kind]['light']}"


def badge(label: str, colour_key: str = "accent", label_colour_key: str = "bg_dark") -> str:
    """Build a shields.io static badge in the one approved style."""
    safe = label.replace("-", "--").replace("_", "__").replace(" ", "_")
    return (
        f"https://img.shields.io/badge/{safe}-{bare(colour_key)}"
        f"?style={BADGE_STYLE}&labelColor={bare(label_colour_key)}"
    )


if __name__ == "__main__":  # pragma: no cover - convenience dump
    print(f"# Amber CRT theme for {DISPLAY_NAME} (@{USERNAME})")
    for key, value in THEME.items():
        print(f"{key:<14} {value}")
    print(f"\nbadge style    {BADGE_STYLE}")
    print(f"output branch  {OUTPUT_BRANCH}")
