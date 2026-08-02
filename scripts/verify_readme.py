#!/usr/bin/env python3
"""A test suite for a README.

A profile README is a program that runs inside GitHub's HTML sanitizer, and it
fails the way sanitized HTML always fails: silently. A ``<style>`` block does
not error, it vanishes. An ``<img>`` missing ``alt`` does not error, it just
excludes every screen-reader user. A table 1200px wide does not error, it makes
the page scroll sideways on a phone. A ``<picture>`` whose dark source 404s does
not error, it shows nothing at all in dark mode.

None of that is visible from looking at the source, and none of it is visible
from looking at the rendered page in one theme on one device. So it gets
asserted instead, on every push, the same as any other code.

Checks
------
sanitizer  no script/style/iframe/form, no ``style=``, no ``on*=`` handlers,
           no tag outside GitHub's allowlist
assets     every relative ``src``/``srcset`` resolves on disk
a11y       every ``<img>`` carries meaningful ``alt`` text
layout     nothing declares a width past the mobile-safe ceiling
structure  every HTML tag and every ``<!-- X:START -->`` marker is balanced
theme      every hex colour and every badge style comes from ``theme.py``
svg        every generated SVG is well-formed XML with no script and no
           external reference

Run ``--self-test`` to verify the verifier: it feeds itself known-bad documents
and asserts each one is rejected for the right reason.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from theme import BADGE_STYLE, THEME  # noqa: E402

# GitHub renders Markdown through html-pipeline's SanitizationFilter. Anything
# outside this list is deleted from the output without warning.
ALLOWED_TAGS = {
    "a", "abbr", "b", "bdo", "blockquote", "br", "caption", "cite", "code",
    "dd", "del", "details", "dfn", "div", "dl", "dt", "em", "figcaption",
    "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins",
    "kbd", "li", "mark", "ol", "p", "picture", "pre", "q", "rp", "rt", "ruby",
    "s", "samp", "small", "source", "span", "strike", "strong", "sub",
    "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time",
    "tr", "tt", "ul", "var", "wbr",
}

# Tags that are not merely dropped but actively signal a broken mental model of
# what a README can do.
FATAL_TAGS = {"script", "style", "iframe", "form", "input", "object", "embed",
              "link", "meta", "base", "button", "select", "textarea", "svg"}

VOID_TAGS = {"br", "hr", "img", "source", "wbr", "col", "input", "meta", "link"}

MAX_WIDTH = 830  # widest a GitHub README column renders before it scrolls

TAG_RE = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>")
ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
# Only treat a hex run as a colour when it is introduced like one (``#fff000``,
# ``bg_color=fff000``, ``0:fff000``). A bare word match would flag English words
# that happen to be six hex characters - "decade", "facade", "efface".
HEX_RE = re.compile(r"(?:#|(?<=[=:,]))([0-9A-Fa-f]{6})(?![0-9A-Za-z])")


@dataclass
class Finding:
    level: str      # "error" or "warn"
    check: str
    line: int
    message: str

    def __str__(self) -> str:
        mark = "ERROR" if self.level == "error" else "warn "
        return f"  {mark} [{self.check}] line {self.line}: {self.message}"


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def strip_code_blocks(text: str) -> str:
    """Blank out fenced code and inline code so examples are not linted.

    Replaced with spaces rather than removed so every reported line number
    still matches the real file.
    """
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    text = re.sub(r"```.*?```", blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", blank, text)
    return text


def parse_attrs(raw: str) -> dict[str, str]:
    return {
        name.lower(): value.strip("\"'")
        for name, value in ATTR_RE.findall(raw)
    }


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def check_markup(source: str, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    body = strip_code_blocks(source)
    stack: list[tuple[str, int]] = []
    palette = {value.lower() for value in THEME.values()}

    for match in TAG_RE.finditer(body):
        closing, tag, raw = match.group(1) == "/", match.group(2).lower(), match.group(3)
        line = line_of(body, match.start())
        self_closing = raw.rstrip().endswith("/")
        attrs = parse_attrs(raw)

        if tag in FATAL_TAGS:
            findings.append(Finding(
                "error", "sanitizer", line,
                f"<{tag}> is removed by GitHub's sanitizer - the markup will silently vanish",
            ))
            continue
        if tag not in ALLOWED_TAGS:
            findings.append(Finding(
                "error", "sanitizer", line,
                f"<{tag}> is not on GitHub's tag allowlist",
            ))
            continue

        if not closing:
            for name in attrs:
                if name == "style":
                    findings.append(Finding(
                        "error", "sanitizer", line,
                        f"inline style= on <{tag}> is stripped; move the styling into an SVG asset",
                    ))
                elif name.startswith("on"):
                    findings.append(Finding(
                        "error", "sanitizer", line,
                        f"event handler {name}= on <{tag}> is stripped; README HTML cannot script",
                    ))

            if tag == "img":
                alt = attrs.get("alt", "").strip()
                if not alt:
                    findings.append(Finding("error", "a11y", line, "<img> has no alt text"))
                elif len(alt) < 4:
                    findings.append(Finding("warn", "a11y", line, f"alt text {alt!r} is too terse to be useful"))

            for dimension in ("width",):
                value = attrs.get(dimension, "")
                if value.isdigit() and int(value) > MAX_WIDTH:
                    findings.append(Finding(
                        "error", "layout", line,
                        f"{dimension}={value} exceeds the {MAX_WIDTH}px mobile-safe ceiling",
                    ))

            for name in ("src", "srcset"):
                value = attrs.get(name, "").split()[0] if attrs.get(name) else ""
                if not value or value.startswith(("http://", "https://", "data:", "#")):
                    continue
                target = (root / value.split("#")[0].split("?")[0]).resolve()
                if not target.exists():
                    findings.append(Finding(
                        "error", "assets", line,
                        f"{name}={value!r} does not resolve to a file in the repository",
                    ))

            if tag == "a" and attrs.get("href", "").startswith("http://"):
                findings.append(Finding("warn", "assets", line, "plain http:// link; prefer https://"))

        # Balance tracking
        if tag in VOID_TAGS or self_closing:
            continue
        if closing:
            if not stack:
                findings.append(Finding("error", "structure", line, f"closing </{tag}> with nothing open"))
            elif stack[-1][0] != tag:
                open_tag, open_line = stack[-1]
                findings.append(Finding(
                    "error", "structure", line,
                    f"</{tag}> closes out of order; <{open_tag}> from line {open_line} is still open",
                ))
                stack.pop()
            else:
                stack.pop()
        else:
            stack.append((tag, line))

    for tag, line in stack:
        findings.append(Finding("error", "structure", line, f"<{tag}> is never closed"))

    # Theme: every colour in the document must come from the palette.
    for match in HEX_RE.finditer(body):
        value = f"#{match.group(1).lower()}"
        if value not in palette:
            findings.append(Finding(
                "error", "theme", line_of(body, match.start()),
                f"{value} is not in the theme palette; run scripts/retheme.py instead of hand-editing colours",
            ))

    # Badges: one style family, everywhere.
    for match in re.finditer(r"https://img\.shields\.io/[^\s\"'<>)]+", body):
        url = match.group(0)
        style = re.search(r"[?&]style=([a-z-]+)", url)
        if style and style.group(1) != BADGE_STYLE:
            findings.append(Finding(
                "error", "theme", line_of(body, match.start()),
                f"badge style {style.group(1)!r} breaks the single {BADGE_STYLE!r} family",
            ))
        elif not style:
            findings.append(Finding(
                "warn", "theme", line_of(body, match.start()),
                f"badge has no explicit style= and will fall back off-theme: {url[:70]}",
            ))

    return findings


def check_markers(source: str) -> list[Finding]:
    """Auto-updating sections need both of their comment markers to survive."""
    findings: list[Finding] = []
    starts = dict(
        (match.group(1), line_of(source, match.start()))
        for match in re.finditer(r"<!--\s*(?:START_SECTION:)?([A-Za-z-]+)(?:-LIST)?:?START\s*-->", source)
    )
    for match in re.finditer(r"<!--\s*([A-Z-]+):START\s*-->", source):
        name = match.group(1)
        if f"<!-- {name}:END -->" not in source and f"<!--{name}:END-->" not in source:
            findings.append(Finding(
                "error", "structure", line_of(source, match.start()),
                f"marker {name}:START has no matching {name}:END - the updater will not find its slot",
            ))
    for match in re.finditer(r"<!--\s*START_SECTION:([a-z_]+)\s*-->", source):
        name = match.group(1)
        if f"<!--END_SECTION:{name}-->" not in source.replace(" ", ""):
            findings.append(Finding(
                "error", "structure", line_of(source, match.start()),
                f"START_SECTION:{name} has no matching END_SECTION",
            ))
    _ = starts
    return findings


OUTPUT_REF_RE = re.compile(
    r"raw\.githubusercontent\.com/[^/\s\"']+/[^/\s\"']+/output/([A-Za-z0-9._-]+)"
)


def check_output_branch(source: str, workflows: Path) -> list[Finding]:
    """Every output-branch asset must be produced *and* seeded by a workflow.

    This exists because of a specific, invisible failure: a ``<picture>`` does
    **not** fall back to its ``<img>`` when a ``<source>`` fails to *load* - only
    when no ``<source>`` *matches*. So a dark-mode source pointing at a file that
    no workflow has published yet renders nothing at all, and the profile looks
    broken in dark mode until someone happens to notice.

    Referencing the output branch is therefore a contract: some workflow has to
    write that exact filename, and something has to seed it before the first
    real run. This check enforces both halves.
    """
    findings: list[Finding] = []
    if not workflows.is_dir():
        return findings

    produced: set[str] = set()
    seeded: set[str] = set()
    for path in sorted(workflows.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        # Two ways a workflow can produce an output-branch file:
        #   1. write it into dist/ and hand that to the publish action
        #   2. hand `filename:` to an action that commits to the branch itself
        #      (lowlighter/metrics runs in Docker and can only do the latter)
        produced.update(re.findall(r"dist/([A-Za-z0-9._-]+\.(?:svg|json))", text))
        if re.search(r"committer_branch:\s*output", text):
            produced.update(re.findall(r"^\s*filename:\s*([A-Za-z0-9._-]+\.(?:svg|json))", text, re.M))
        seeded.update(re.findall(r"^\s*seed\s+([A-Za-z0-9._-]+)\s", text, re.M))

    for match in OUTPUT_REF_RE.finditer(source):
        name = match.group(1)
        line = line_of(source, match.start())
        if name not in produced:
            findings.append(Finding(
                "error", "assets", line,
                f"{name} is loaded from the output branch but no workflow writes dist/{name}",
            ))
        elif name not in seeded and "<source" in source[max(0, match.start() - 400):match.start() + 40]:
            findings.append(Finding(
                "error", "assets", line,
                f"{name} is a <picture> source on the output branch but is never seeded. "
                "Before its workflow first runs the file 404s, and <picture> does not "
                "fall back to <img> on a load error - dark mode renders nothing. "
                "Add a seed line in refresh.yml.",
            ))
    return findings


def check_raw_ascii(source: str) -> list[Finding]:
    """Raw ASCII art in Markdown reflows and shatters. It must be an asset."""
    findings: list[Finding] = []
    body = strip_code_blocks(source)
    art = re.compile(r"^[^\n]*[░▒▓█]{6,}", re.M)
    for match in art.finditer(body):
        findings.append(Finding(
            "error", "layout", line_of(body, match.start()),
            "raw block-drawing art outside a code fence will reflow; render it as an SVG asset instead",
        ))
    return findings


#: A DTD is the entry point for both XXE and billion-laughs. Nothing this
#: repository generates needs one, so any occurrence is rejected *before*
#: the document reaches the stdlib parser rather than hardening the parser.
DTD_RE = re.compile(r"<!\s*(DOCTYPE|ENTITY)\b", re.I)


def check_svgs(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if DTD_RE.search(text):
            findings.append(Finding(
                "error", "svg", 1,
                f"{path.name} declares a DTD or entity; refusing to parse "
                "(entity expansion is an XXE / billion-laughs vector and no generated asset needs one)",
            ))
            continue
        try:
            ET.fromstring(text)
        except ET.ParseError as exc:
            findings.append(Finding("error", "svg", 1, f"{path.name} is not well-formed XML: {exc}"))
            continue
        if "<script" in text.lower():
            findings.append(Finding("error", "svg", 1, f"{path.name} contains a script element (never executes in <img>, and is a red flag)"))
        if re.search(r"\son[a-z]+\s*=", text):
            findings.append(Finding("error", "svg", 1, f"{path.name} contains an inline event handler"))
        for match in re.finditer(r'(?:xlink:href|href|src)\s*=\s*"(https?://[^"]+)"', text):
            findings.append(Finding(
                "error", "svg", 1,
                f"{path.name} references an external resource ({match.group(1)[:50]}); "
                "GitHub blocks it and the asset renders incomplete",
            ))
        if "prefers-color-scheme" not in text:
            findings.append(Finding(
                "warn", "svg", 1,
                f"{path.name} has no prefers-color-scheme rule and will look wrong in one GitHub theme",
            ))
    return findings


# --------------------------------------------------------------------------
def verify(readme: Path, assets: Path) -> list[Finding]:
    source = readme.read_text(encoding="utf-8")
    root = readme.parent
    findings = check_markup(source, root)
    findings += check_markers(source)
    findings += check_raw_ascii(source)
    findings += check_output_branch(source, root / ".github" / "workflows")
    if assets.is_dir():
        findings += check_svgs(sorted(assets.glob("*.svg")))
    return findings


SELF_TESTS: list[tuple[str, str, str]] = [
    ("script tag", "<script>alert(1)</script>", "sanitizer"),
    ("style block", "<style>body{color:red}</style>", "sanitizer"),
    ("inline style", '<div style="color:red">x</div>', "sanitizer"),
    ("event handler", '<a href="#" onclick="x()">y</a>', "sanitizer"),
    ("iframe", '<iframe src="https://example.com"></iframe>', "sanitizer"),
    ("missing alt", '<img src="assets/signature-divider.svg">', "a11y"),
    ("oversize width", '<img src="assets/signature-divider.svg" alt="divider art" width="1400">', "layout"),
    ("missing asset", '<img src="assets/does-not-exist.svg" alt="a missing asset">', "assets"),
    ("unclosed tag", "<div align=\"center\">", "structure"),
    ("mismatched tag", "<div><p>text</div></p>", "structure"),
    ("off-theme colour", "<!-- accent #FF00FF -->", "theme"),
    ("off-theme badge", "https://img.shields.io/badge/x-blue?style=plastic", "theme"),
    ("raw ascii art", "████████ raw art", "layout"),
    ("orphan marker", "<!-- BLOG-POST-LIST:START -->", "structure"),
    (
        "unproduced output asset",
        '<img src="https://raw.githubusercontent.com/u/u/output/nobody-writes-this.svg" alt="an orphan asset">',
        "assets",
    ),
]


def self_test(root: Path) -> int:
    """Feed the verifier known-bad documents and assert each is caught."""
    import tempfile

    failures = 0
    for name, snippet, expected in SELF_TESTS:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "README.md"
            (Path(tmp) / "assets").mkdir()
            for real in (root / "assets").glob("signature-divider.svg"):
                (Path(tmp) / "assets" / real.name).write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
            # The output-branch check reads the real workflows to learn which
            # filenames are produced and seeded, so the fixture needs them too.
            workflows = Path(tmp) / ".github" / "workflows"
            workflows.mkdir(parents=True)
            for real in (root / ".github" / "workflows").glob("*.yml"):
                (workflows / real.name).write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
            fake.write_text(snippet + "\n", encoding="utf-8")
            found = verify(fake, Path(tmp) / "assets")
            checks = {f.check for f in found if f.level == "error"}
            if expected in checks:
                print(f"  pass  {name:<20} -> {expected}")
            else:
                print(f"  FAIL  {name:<20} -> expected {expected}, got {sorted(checks) or 'nothing'}")
                failures += 1

    clean = verify(root / "README.md", root / "assets") if (root / "README.md").exists() else []
    real_errors = [f for f in clean if f.level == "error"]
    if real_errors:
        print(f"  FAIL  {'real README':<20} -> {len(real_errors)} errors (expected 0)")
        failures += 1
    else:
        print(f"  pass  {'real README':<20} -> 0 errors")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--assets", type=Path, default=Path("assets"))
    parser.add_argument("--self-test", action="store_true", help="verify the verifier, then exit")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    if args.self_test:
        print("verify_readme: self-test")
        failures = self_test(Path.cwd())
        print("verify_readme: self-test " + ("FAILED" if failures else "passed"))
        return 1 if failures else 0

    findings = verify(args.readme, args.assets)
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warn"]

    by_check: dict[str, list[Finding]] = {}
    for finding in findings:
        by_check.setdefault(finding.check, []).append(finding)

    print(f"verify_readme: {args.readme}")
    for check in ("sanitizer", "assets", "a11y", "layout", "structure", "theme", "svg"):
        items = by_check.get(check, [])
        bad = [f for f in items if f.level == "error"]
        status = "FAIL" if bad else "ok  "
        print(f"  {status}  {check:<10} {len(items)} finding(s)")
        for finding in sorted(items, key=lambda f: f.line):
            print(finding)

    print(f"verify_readme: {len(errors)} error(s), {len(warnings)} warning(s)")
    if errors:
        return 1
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
