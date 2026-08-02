#!/usr/bin/env python3
"""Self-hosted GitHub charts - the ones that can never 404.

Every third-party card service on a profile README is a dependency you do not
control: Vercel free tiers get rate limited, upstream repos get archived, and
the card silently turns into a broken image on *your* profile. The charts here
are rendered from the GitHub API into committed SVGs, so the only thing that
can break them is GitHub itself.

Outputs
-------
``oscilloscope.svg``   a year of contributions drawn as a CRT scope trace
``commit-clock.svg``   commits by hour of day - night owl vs early bird
``language-bars.svg``  language mix, weighted by bytes
``stars.json``         shields.io endpoint payload for a live total-stars badge
``pulse.json``         shields.io endpoint payload for the contribution total

Every fetch degrades rather than fails: if the API is unreachable or a token is
missing, the chart falls back to a labelled placeholder and the workflow still
goes green. A profile that half-renders beats a workflow that blocks.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_assets import WIDTH, placeholder, svg_open, write  # noqa: E402
from theme import MONO_STACK, THEME, USERNAME, UTC_OFFSET, css_vars  # noqa: E402

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"

CRT_VARS = dict(
    extra_light={"scanInk": "#7A5A1E", "scanOp": ".06", "vig": ".08"},
    extra_dark={"scanInk": "#000000", "scanOp": ".26", "vig": ".38"},
)


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------
def _request(url: str, token: str | None, payload: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-charts/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def contribution_calendar(username: str, token: str | None) -> tuple[list[list[int]], int] | None:
    """Weeks of daily contribution counts, newest week last.

    Requires a token: the contributions calendar is only exposed through the
    GraphQL API, which rejects anonymous requests outright.
    """
    if not token:
        return None
    query = """
    query($login:String!){
      user(login:$login){
        contributionsCollection{
          contributionCalendar{
            totalContributions
            weeks{ contributionDays{ contributionCount weekday } }
          }
        }
      }
    }
    """
    try:
        body = _request(GRAPHQL, token, {"query": query, "variables": {"login": username}})
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"gh_charts: contribution calendar unavailable ({exc})", file=sys.stderr)
        return None
    if not isinstance(body, dict) or body.get("errors"):
        print(f"gh_charts: GraphQL rejected the query ({body.get('errors') if isinstance(body, dict) else body})", file=sys.stderr)
        return None
    try:
        calendar = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except (KeyError, TypeError):
        return None
    weeks = [[day["contributionCount"] for day in week["contributionDays"]] for week in calendar["weeks"]]
    return weeks, int(calendar["totalContributions"])


def public_events(username: str, token: str | None, pages: int = 3) -> list[dict]:
    events: list[dict] = []
    for page in range(1, pages + 1):
        try:
            batch = _request(f"{API}/users/{username}/events/public?per_page=100&page={page}", token)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"gh_charts: events page {page} unavailable ({exc})", file=sys.stderr)
            break
        if not isinstance(batch, list) or not batch:
            break
        events.extend(batch)
    return events


def profile(username: str, token: str | None) -> dict:
    try:
        body = _request(f"{API}/users/{username}", token)
        return body if isinstance(body, dict) else {}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"gh_charts: profile unavailable ({exc})", file=sys.stderr)
        return {}


def search_count(query: str, token: str | None, commits: bool = False) -> int | None:
    """Total hits for a search query, or None if the API declined.

    The search endpoint is rate limited far more aggressively than the rest of
    the API (10/min unauthenticated), so every caller has to tolerate a miss.
    """
    kind = "commits" if commits else "issues"
    url = f"{API}/search/{kind}?q={urllib.parse.quote(query)}&per_page=1"
    try:
        body = _request(url, token)
        return int(body["total_count"]) if isinstance(body, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        print(f"gh_charts: search '{query}' unavailable ({exc})", file=sys.stderr)
        return None


def owned_repos(username: str, token: str | None) -> list[dict]:
    repos: list[dict] = []
    for page in range(1, 5):
        try:
            batch = _request(
                f"{API}/users/{username}/repos?per_page=100&page={page}&type=owner&sort=updated", token
            )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"gh_charts: repo page {page} unavailable ({exc})", file=sys.stderr)
            break
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
    return repos


# --------------------------------------------------------------------------
# Chart 1 - the contribution oscilloscope
# --------------------------------------------------------------------------
def oscilloscope(weeks: list[list[int]], total: int, width: int = WIDTH) -> str:
    """A year of commits as a phosphor scope trace.

    A contribution graph is a heatmap because a heatmap is what fits in a grid.
    Given a full-width strip, the same data reads far better as a waveform: the
    eye picks out rhythm, bursts and dead weeks instantly. The sweeping beam and
    the decaying afterglow are the CRT metaphor carried through honestly - the
    trace is real data, only the presentation is borrowed.
    """
    height = 190
    pad_l, pad_r, pad_t, pad_b = 46, 20, 26, 30
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    series = [sum(week) for week in weeks] or [0]
    peak = max(series) or 1
    step = plot_w / max(len(series) - 1, 1)

    points = [
        (pad_l + i * step, pad_t + plot_h - (value / peak) * plot_h)
        for i, value in enumerate(series)
    ]
    # Catmull-Rom style smoothing keeps the trace continuous without overshoot.
    path = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        mid = (x0 + x1) / 2
        path.append(f"C{mid:.1f} {y0:.1f} {mid:.1f} {y1:.1f} {x1:.1f} {y1:.1f}")
    trace = "".join(path)
    fill = f"{trace}L{points[-1][0]:.1f} {pad_t + plot_h:.1f}L{points[0][0]:.1f} {pad_t + plot_h:.1f}Z"

    grid = "".join(
        f'<line x1="{pad_l}" y1="{pad_t + plot_h * f:.1f}" x2="{width - pad_r}" '
        f'y2="{pad_t + plot_h * f:.1f}" stroke="var(--grid)" stroke-width="1"/>'
        for f in (0, 0.25, 0.5, 0.75, 1)
    )
    labels = "".join(
        f'<text class="ax" x="{pad_l - 8}" y="{pad_t + plot_h * f + 3:.1f}" text-anchor="end">'
        f"{round(peak * (1 - f))}</text>"
        for f in (0, 0.5, 1)
    )

    length = int(plot_w * 1.35)
    css = (
        css_vars(**CRT_VARS)
        + f".ax{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px}}"
        + f".hd{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:2px}}"
        + f".val{{fill:var(--accent);font-family:{MONO_STACK};font-size:13px;font-weight:700}}"
        ".area{fill:var(--accent);opacity:.10}"
        ".trace{fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round;"
        f"stroke-dasharray:{length};stroke-dashoffset:{length};"
        "animation:draw 6s ease-in-out infinite}"
        f"@keyframes draw{{0%{{stroke-dashoffset:{length}}}55%{{stroke-dashoffset:0}}"
        f"92%{{stroke-dashoffset:0;opacity:1}}100%{{stroke-dashoffset:0;opacity:.25}}}}"
        ".ghost{fill:none;stroke:var(--accent);stroke-width:6;opacity:.10}"
        ".beam{animation:beam 6s ease-in-out infinite}"
        f"@keyframes beam{{0%{{transform:translateX(0);opacity:0}}6%{{opacity:.9}}"
        f"55%{{transform:translateX({plot_w:.0f}px);opacity:.9}}"
        f"60%{{transform:translateX({plot_w:.0f}px);opacity:0}}"
        f"100%{{transform:translateX({plot_w:.0f}px);opacity:0}}}}"
    )
    return (
        svg_open(
            width,
            height,
            "Contribution oscilloscope",
            f"A year of GitHub contributions drawn as an oscilloscope trace. "
            f"{total} contributions, peaking at {peak} in a single week.",
            ids="ot od",
        )
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)" stroke="var(--grid)"/>'
        + grid
        + labels
        + f'<path class="area" d="{fill}"/>'
        + f'<path class="ghost" d="{trace}"/>'
        + f'<path class="trace" d="{trace}"/>'
        + f'<g class="beam"><rect x="{pad_l}" y="{pad_t}" width="1.5" height="{plot_h:.0f}" '
        'fill="var(--accent)" opacity=".8"/>'
        + f'<rect x="{pad_l - 5}" y="{pad_t}" width="11" height="{plot_h:.0f}" '
        'fill="var(--accent)" opacity=".07"/></g>'
        + f'<text class="hd" x="{pad_l}" y="16">CONTRIBUTIONS / 52 WEEKS</text>'
        + f'<text class="val" x="{width - pad_r}" y="17" text-anchor="end">{total}</text>'
        + f'<text class="ax" x="{pad_l}" y="{height - 10}">52 weeks ago</text>'
        + f'<text class="ax" x="{width - pad_r}" y="{height - 10}" text-anchor="end">today</text>'
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Chart 2 - commits by hour
# --------------------------------------------------------------------------
def commit_clock(hours: Counter, width: int = 405) -> str:
    """Radial histogram of push activity by local hour."""
    height = 220
    cx, cy = width / 2, height / 2 + 6
    r_inner, r_outer = 38, 84
    peak = max(hours.values()) if hours else 1

    wedges = []
    for hour in range(24):
        value = hours.get(hour, 0)
        extent = r_inner + (r_outer - r_inner) * (value / peak if peak else 0)
        a0 = math.radians(hour * 15 - 90 + 1.6)
        a1 = math.radians((hour + 1) * 15 - 90 - 1.6)
        x0, y0 = cx + r_inner * math.cos(a0), cy + r_inner * math.sin(a0)
        x1, y1 = cx + r_inner * math.cos(a1), cy + r_inner * math.sin(a1)
        x2, y2 = cx + extent * math.cos(a1), cy + extent * math.sin(a1)
        x3, y3 = cx + extent * math.cos(a0), cy + extent * math.sin(a0)
        wedges.append(
            f'<path class="w w{hour % 6}" d="M{x0:.1f} {y0:.1f}A{r_inner} {r_inner} 0 0 1 {x1:.1f} {y1:.1f}'
            f"L{x2:.1f} {y2:.1f}A{extent:.1f} {extent:.1f} 0 0 0 {x3:.1f} {y3:.1f}Z\"/>"
        )

    marks = "".join(
        f'<text class="hr" x="{cx + (r_outer + 14) * math.cos(math.radians(h * 15 - 90)):.1f}" '
        f'y="{cy + (r_outer + 14) * math.sin(math.radians(h * 15 - 90)) + 3:.1f}" '
        f'text-anchor="middle">{h:02d}</text>'
        for h in (0, 6, 12, 18)
    )

    night = sum(hours.get(h, 0) for h in list(range(22, 24)) + list(range(0, 6)))
    total = sum(hours.values()) or 1
    verdict = "NIGHT OWL" if night / total > 0.34 else "DAYLIGHT SHIPPER"

    css = (
        css_vars(**CRT_VARS)
        + ".w{fill:var(--accent);animation:rise 3.4s ease-out infinite}"
        + "".join(f".w{i}{{animation-delay:{i * 0.09:.2f}s}}" for i in range(6))
        + "@keyframes rise{0%{opacity:.25}18%{opacity:1}80%{opacity:1}100%{opacity:.25}}"
        + f".hr{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px}}"
        + f".hd{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:2px}}"
        + f".vd{{fill:var(--accent);font-family:{MONO_STACK};font-size:12px;font-weight:700;letter-spacing:1.4px}}"
    )
    return (
        svg_open(
            width,
            height,
            "Commits by hour of day",
            f"Radial histogram of push activity by local hour (UTC{UTC_OFFSET:+g}). "
            f"Profile reads as {verdict.lower()}.",
            ids="ct cd",
        )
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)" stroke="var(--grid)"/>'
        + f'<text class="hd" x="18" y="20">COMMIT HOURS / UTC{UTC_OFFSET:+g}</text>'
        + f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r_inner}" fill="none" stroke="var(--grid)"/>'
        + f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r_outer}" fill="none" stroke="var(--grid)" stroke-dasharray="2 4"/>'
        + "".join(wedges)
        + marks
        + f'<text class="vd" x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle">{verdict}</text>'
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Chart 3 - language mix
# --------------------------------------------------------------------------
def language_bars(languages: list[tuple[str, int]], width: int = 405) -> str:
    rows = languages[:6]
    height = 44 + len(rows) * 26 + 14
    total = sum(count for _, count in rows) or 1
    bar_x, bar_w = 118, width - 118 - 62

    body = []
    for index, (name, count) in enumerate(rows):
        y = 44 + index * 26
        share = count / total
        body.append(
            f'<text class="nm" x="18" y="{y + 11}">{name[:14]}</text>'
            f'<rect x="{bar_x}" y="{y + 1}" width="{bar_w}" height="12" rx="6" fill="var(--grid)"/>'
            f'<rect class="bar b{index}" x="{bar_x}" y="{y + 1}" width="{bar_w * share:.1f}" '
            f'height="12" rx="6" fill="var(--accent)"/>'
            f'<text class="pc" x="{width - 18}" y="{y + 11}" text-anchor="end">{share * 100:.1f}%</text>'
        )

    css = (
        css_vars(**CRT_VARS)
        + f".nm{{fill:var(--ink);font-family:{MONO_STACK};font-size:11px;font-weight:600}}"
        + f".pc{{fill:var(--muted);font-family:{MONO_STACK};font-size:10px}}"
        + f".hd{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:2px}}"
        + ".bar{transform-origin:left center;animation:grow 4s ease-out infinite}"
        + "".join(f".b{i}{{animation-delay:{i * 0.11:.2f}s}}" for i in range(6))
        + "@keyframes grow{0%{transform:scaleX(0)}30%{transform:scaleX(1)}"
        "88%{transform:scaleX(1)}100%{transform:scaleX(1)}}"
    )
    return (
        svg_open(
            width,
            height,
            "Language mix",
            "Share of code by language across public repositories, weighted by bytes.",
            ids="lt ld",
        )
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)" stroke="var(--grid)"/>'
        + '<text class="hd" x="18" y="22">LANGUAGE MIX / BY BYTES</text>'
        + "".join(body)
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Chart 4 - profile statistics
# --------------------------------------------------------------------------
def _fmt(value: int | None) -> str:
    if value is None:
        return "—"
    if value >= 10_000:
        return f"{value / 1000:.1f}k"
    return str(value)


def stats_card(rows: list[tuple[str, int | None]], name: str, width: int = 405) -> str:
    """The self-hosted replacement for github-readme-stats.

    Written after the shared instance answered 503 for every card on the page.
    A profile that depends on someone else's free Vercel quota is a profile that
    is blank at random.
    """
    cols = 2
    cell_h = 46
    lines = (len(rows) + cols - 1) // cols
    height = 52 + lines * cell_h + 12
    cell_w = (width - 36) / cols

    body = []
    for index, (label, value) in enumerate(rows):
        cx = 18 + (index % cols) * cell_w
        cy = 52 + (index // cols) * cell_h
        body.append(
            f'<text class="v s{index % 6}" x="{cx:.0f}" y="{cy + 20:.0f}">{_fmt(value)}</text>'
            f'<text class="k" x="{cx:.0f}" y="{cy + 34:.0f}">{html.escape(label.upper())}</text>'
        )

    css = (
        css_vars(**CRT_VARS)
        + f".hd{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:2px}}"
        + f".v{{fill:var(--accent);font-family:{MONO_STACK};font-size:20px;font-weight:700}}"
        + f".k{{fill:var(--muted);font-family:{MONO_STACK};font-size:8.5px;letter-spacing:1.3px}}"
        + ".v{animation:pop 4s ease-out infinite}"
        + "".join(f".s{i}{{animation-delay:{i * 0.12:.2f}s}}" for i in range(6))
        + "@keyframes pop{0%{opacity:.3}14%{opacity:1}90%{opacity:1}100%{opacity:.3}}"
    )
    return (
        svg_open(
            width, height, f"GitHub statistics for {name}",
            "Stars, repositories, followers, pull requests and issues, rendered "
            "directly from the GitHub API.",
            ids="st2 sd2",
        )
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)" stroke="var(--grid)"/>'
        + '<text class="hd" x="18" y="26">GITHUB STATISTICS</text>'
        + f'<rect x="18" y="34" width="{width - 36}" height="1" fill="var(--grid)"/>'
        + "".join(body)
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Chart 5 - repository pins
# --------------------------------------------------------------------------
def repo_pins(repos: list[dict], width: int = 830) -> str:
    """The self-hosted replacement for github-readme-stats pin cards."""
    cols = 2
    card_h = 104
    gap = 12
    rows = (len(repos) + cols - 1) // cols
    height = 40 + rows * (card_h + gap)
    card_w = (width - 36 - gap) / cols

    def wrap(text: str, limit: int, lines: int) -> list[str]:
        words, out, current = text.split(), [], ""
        for word in words:
            if len(current) + len(word) + 1 > limit:
                out.append(current)
                current = word
                if len(out) == lines:
                    break
            else:
                current = f"{current} {word}".strip()
        if current and len(out) < lines:
            out.append(current)
        if out and len(" ".join(words)) > limit * lines:
            out[-1] = out[-1][: limit - 1] + "…"
        return out

    body = []
    for index, repo in enumerate(repos[: cols * rows]):
        x = 18 + (index % cols) * (card_w + gap)
        y = 40 + (index // cols) * (card_h + gap)
        desc = wrap(repo.get("description") or "No description.", 52, 2)
        meta = []
        if repo.get("language"):
            meta.append(repo["language"])
        meta.append(f"★ {repo.get('stargazers_count', 0)}")
        meta.append(f"⚇ {repo.get('forks_count', 0)}")

        body.append(
            f'<rect x="{x:.0f}" y="{y}" width="{card_w:.0f}" height="{card_h}" rx="12" '
            'fill="var(--surface)" stroke="var(--grid)"/>'
            f'<rect class="tick t{index % 4}" x="{x:.0f}" y="{y}" width="3" height="{card_h}" fill="var(--accent)"/>'
            f'<text class="rn" x="{x + 16:.0f}" y="{y + 26}">{html.escape(repo["name"])}</text>'
            + "".join(
                f'<text class="rd" x="{x + 16:.0f}" y="{y + 48 + i * 15}">{html.escape(line)}</text>'
                for i, line in enumerate(desc)
            )
            + f'<text class="rm" x="{x + 16:.0f}" y="{y + card_h - 14}">'
            f'{html.escape("  ·  ".join(meta))}</text>'
        )

    css = (
        css_vars(**CRT_VARS)
        + f".hd{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:2px}}"
        + f".rn{{fill:var(--accent);font-family:{MONO_STACK};font-size:14px;font-weight:700}}"
        + f".rd{{fill:var(--ink);font-family:{MONO_STACK};font-size:10.5px}}"
        + f".rm{{fill:var(--muted);font-family:{MONO_STACK};font-size:9.5px}}"
        + ".tick{animation:tick 5s ease-in-out infinite}"
        + "".join(f".t{i}{{animation-delay:{i * 0.25:.2f}s}}" for i in range(4))
        + "@keyframes tick{0%,100%{opacity:.35}50%{opacity:1}}"
    )
    return (
        svg_open(
            width, height, "Featured repositories",
            "Cards for the most notable public repositories, rendered directly "
            "from the GitHub API.",
            ids="rt rd2",
        )
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)" stroke="var(--grid)"/>'
        + '<text class="hd" x="18" y="26">FEATURED REPOSITORIES</text>'
        + "".join(body)
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
# Chart 6 - achievements
# --------------------------------------------------------------------------
def achievements(tiles: list[tuple[str, str]], width: int = 830) -> str:
    """The self-hosted replacement for github-profile-trophy.

    Written after that service answered 402 Payment Required - its Vercel
    account had exceeded its billing limit, which is a recurring condition
    rather than a blip. Every tile here is computed from real API data.
    """
    height = 132
    count = max(len(tiles), 1)
    gap = 10
    tile_w = (width - 36 - gap * (count - 1)) / count

    body = []
    for index, (value, label) in enumerate(tiles):
        x = 18 + index * (tile_w + gap)
        cx = x + tile_w / 2
        body.append(
            f'<rect x="{x:.1f}" y="34" width="{tile_w:.1f}" height="82" rx="10" '
            'fill="var(--surface)" stroke="var(--grid)"/>'
            f'<circle class="halo h{index % 5}" cx="{cx:.1f}" cy="60" r="13" '
            'fill="none" stroke="var(--accent)" stroke-width="1.5"/>'
            f'<text class="tv" x="{cx:.1f}" y="65" text-anchor="middle">{html.escape(value)}</text>'
            f'<text class="tl" x="{cx:.1f}" y="98" text-anchor="middle">{html.escape(label.upper())}</text>'
        )

    css = (
        css_vars(**CRT_VARS)
        + f".hd{{fill:var(--muted);font-family:{MONO_STACK};font-size:9px;letter-spacing:2px}}"
        + f".tv{{fill:var(--accent);font-family:{MONO_STACK};font-size:13px;font-weight:700}}"
        + f".tl{{fill:var(--muted);font-family:{MONO_STACK};font-size:8px;letter-spacing:1.1px}}"
        + ".halo{animation:halo 3.6s ease-in-out infinite}"
        + "".join(f".h{i}{{animation-delay:{i * 0.22:.2f}s}}" for i in range(5))
        + "@keyframes halo{0%,100%{opacity:.35;r:13}50%{opacity:1;r:15}}"
    )
    return (
        svg_open(
            width, height, "Profile achievements",
            "Achievement tiles computed from live GitHub API data.",
            ids="at ad",
        )
        + f"<style>{css}</style>"
        + f'<rect width="{width}" height="{height}" rx="14" fill="var(--bg)" stroke="var(--grid)"/>'
        + '<text class="hd" x="18" y="24">ACHIEVEMENTS</text>'
        + "".join(body)
        + "</svg>\n"
    )


# --------------------------------------------------------------------------
def shields_endpoint(label: str, message: str) -> str:
    """A shields.io ``endpoint`` payload, themed to match every other badge."""
    return json.dumps(
        {
            "schemaVersion": 1,
            "label": label,
            "message": message,
            "color": THEME["accent"].lstrip("#"),
            "labelColor": THEME["bg_dark"].lstrip("#"),
            "style": "for-the-badge",
        },
        indent=2,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=USERNAME)
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    parser.add_argument("--token", default=os.environ.get("GH_CHART_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    parser.add_argument(
        "--featured",
        nargs="*",
        default=["Veris", "Pulse", "offside-june-2026", "janus"],
        help="repositories to pin, in order; missing ones fall back to star ranking",
    )
    args = parser.parse_args()
    out = args.output_dir
    token = args.token or None

    # --- oscilloscope -----------------------------------------------------
    calendar = contribution_calendar(args.username, token)
    if calendar:
        weeks, total = calendar
        write(out / "oscilloscope.svg", oscilloscope(weeks, total))
        print(f"gh_charts: oscilloscope -> {total} contributions over {len(weeks)} weeks")
    else:
        total = 0
        write(
            out / "oscilloscope.svg",
            placeholder(
                "Contribution oscilloscope pending",
                "refresh.yml needs a token with read:user to reach the contributions API.",
                height=190,
            ),
        )
        print("gh_charts: oscilloscope -> placeholder (no calendar access)")

    # --- commit clock -----------------------------------------------------
    events = public_events(args.username, token)
    hours: Counter = Counter()
    for event in events:
        if event.get("type") != "PushEvent":
            continue
        stamp = event.get("created_at")
        if not stamp:
            continue
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
        local = (moment.hour + moment.minute / 60 + UTC_OFFSET) % 24
        hours[int(local)] += 1
    if hours:
        write(out / "commit-clock.svg", commit_clock(hours))
        print(f"gh_charts: commit-clock -> {sum(hours.values())} push events")
    else:
        write(
            out / "commit-clock.svg",
            placeholder("Commit clock pending", "No push events visible yet.", width=405, height=220),
        )
        print("gh_charts: commit-clock -> placeholder (no push events)")

    # --- languages and stars ---------------------------------------------
    repos = owned_repos(args.username, token)
    stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    counter: Counter = Counter()
    for repo in repos:
        if repo.get("fork") or repo.get("archived"):
            continue
        language = repo.get("language")
        if language:
            # size is a rough byte proxy and avoids one API call per repository.
            counter[language] += max(int(repo.get("size", 0)), 1)
    if counter:
        write(out / "language-bars.svg", language_bars(counter.most_common()))
        print(f"gh_charts: language-bars -> {len(counter)} languages across {len(repos)} repos")
    else:
        write(
            out / "language-bars.svg",
            placeholder("Language mix pending", "No public repositories detected yet.", width=405, height=200),
        )
        print("gh_charts: language-bars -> placeholder (no languages)")

    write(out / "stars.json", shields_endpoint("total stars", str(stars)))
    write(out / "pulse.json", shields_endpoint("contributions", f"{total}/yr" if total else "warming up"))
    print(f"gh_charts: badges -> {stars} stars, {total} contributions")

    # --- stats card, pins and achievements -------------------------------
    # These three exist because their third-party equivalents were observed
    # returning 503 (github-readme-stats) and 402 (github-profile-trophy).
    me = profile(args.username, token)
    prs = search_count(f"author:{args.username} type:pr", token)
    issues = search_count(f"author:{args.username} type:issue", token)
    commits = search_count(f"author:{args.username}", token, commits=True)

    write(
        out / "stats-card.svg",
        stats_card(
            [
                ("total stars", stars),
                ("contributions", total or None),
                ("public repos", me.get("public_repos", len(repos) or None)),
                ("followers", me.get("followers")),
                ("pull requests", prs),
                ("commits", commits),
            ],
            me.get("name") or args.username,
        ),
    )
    print(f"gh_charts: stats-card -> stars={stars} prs={prs} issues={issues} commits={commits}")

    # Curated first, ranked as a fallback. Star count is a terrible proxy for
    # "what I want on my profile" when the interesting work is new.
    by_name = {r["name"].lower(): r for r in repos}
    ranked = [by_name[n.lower()] for n in args.featured if n.lower() in by_name]
    if len(ranked) < 4:
        rest = sorted(
            (
                r for r in repos
                if not r.get("fork") and not r.get("archived") and r.get("description")
                and r["name"].lower() not in {p["name"].lower() for p in ranked}
            ),
            key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")),
            reverse=True,
        )
        ranked += rest[: 4 - len(ranked)]
    if ranked:
        write(out / "repo-pins.svg", repo_pins(ranked[:4]))
        print(f"gh_charts: repo-pins -> {', '.join(r['name'] for r in ranked[:4])}")
    else:
        write(out / "repo-pins.svg", placeholder("Featured repositories pending", "No described public repositories yet."))

    tiles: list[tuple[str, str]] = [
        (_fmt(stars), "stars earned"),
        (_fmt(me.get("public_repos", len(repos))), "public repos"),
        (_fmt(len(counter)), "languages"),
        (_fmt(me.get("followers")), "followers"),
        (_fmt(prs), "pull requests"),
        (_fmt(total or None), "contributions"),
        ("npm", "published"),
    ]
    write(out / "achievements.svg", achievements(tiles))
    print(f"gh_charts: achievements -> {len(tiles)} tiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
