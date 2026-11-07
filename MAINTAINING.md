# Maintaining this profile

The profile has one visual system, one contribution snapshot, one project explorer, and one game. The README is intentionally short; the portfolio contains the full project stories.

## Local commands

Use Node.js 22 and `npm ci --ignore-scripts`.

```sh
npm test
npm run build
npm run build:check
npm run verify
```

`npm run build` is offline and reproduces the SVGs from committed fonts and data. `npm run build:check` checks their reproducibility. `npm run refresh` fetches current public contribution data and rebuilds only the activity chart. The header and project illustrations use outlined Manrope and Newsreader from the website. Font sources and licenses are in `fonts/`.

The header retains the original profile portrait as vector cells. Its 64-by-46 tonal map is in `src/portrait.json`; it does not fetch a photograph or depend on system block-character fonts. The three selected-work illustrations share a frame, while their diagrams reference evidence sheets, agent connections, and a football decision. Keep the project descriptions and links in native Markdown beneath the artwork.

Font paths use the finite-coordinate exporter in `src/lettering.mjs`. The font library's decimal formatter can emit `NaN` for near-integer values and silently drop parts of letters. Regression tests cover the affected glyphs, and verification rejects invalid coordinates in every generated SVG.

The header's three accent pixels introduce themselves for 3.3 seconds, and each project diagram draws its highlighted path once over 2.2 seconds. All lettering stays still. These self-contained CSS introductions settle without looping and are disabled by `prefers-reduced-motion`.

## What the chart measures

`data/activity.json` records exactly 90 completed UTC dates ending yesterday, every explicit daily count, their sum, the number of active days, the peak daily count, and the successful fetch timestamp. The source is GitHub's **publicly visible profile contribution calendar**. Counts follow GitHub's contribution rules; they are not commit counts, coding hours, proficiency, or a productivity score. Anonymized private activity is included only if GitHub already exposes it on the public profile.

The public HTML endpoint requires no token. A 90-day range needs one request normally and two if it crosses a year boundary. The parser checks date/tooltip identities and exact integer counts. Missing or changed markup is an error, never inferred zero activity. A failed request or validation leaves the last good file and timestamp intact. The source endpoint is unversioned, so the refresh job must be repaired if GitHub changes its markup.

## Automation

- **Verify profile:** read-only tests, README/asset checks, and deterministic artwork checks on changes.
- **Refresh public activity:** daily at 05:37 UTC (11:07 IST), manually, or after changes to the generator. It fetches, validates, renders, tests, and atomically commits only the JSON snapshot and SVG using the repository's built-in `GITHUB_TOKEN`. No personal access token or external chart service is required.

There is one scheduled writer. It refuses an outdated checkout and never force-pushes. A failure is visible as a failed Action; the chart continues to show the last successful update. GitHub may delay schedules or disable them on inactive public repositories; the manual action can refresh the snapshot. Bot commits made with `GITHUB_TOKEN` do not recursively trigger workflows.

The old output branch remains as history and is no longer read or written. Legacy metrics, time-tracking, game generators, placeholders and health claims have been removed from the active profile. Existing unused secrets do not need to be read or rotated for this implementation.

## The single game

Signal Run is an original keyboard/pointer/touch paddle game in `play/`. Its board is independent of contribution data. A static poster in the README links to GitHub Pages; scripts do not run inside GitHub Markdown. It starts only after a user action, supports pause/reset and reduced-motion preferences, and has a separately tested physics engine.

GitHub Pages serves `main` from `/` with `.nojekyll`. The game URL is `https://vighriday.github.io/vighriday/play/`.

## Content and interaction

Keep substantive text in Markdown, with short project explanations and links to evidence. Use native disclosures for background details. Avoid inline scripts/styles, remote badges, simulated health statuses, and duplicate activity visualizations. Update project descriptions and the portfolio together when their scope changes.

`explore/` is a small explanatory interface, separate from the single game. Four project selectors and three lenses change the workflow labels and factual notes. Diagram nodes reveal details within the selected lens and animate the route emphasis once. The URL preserves the selected project, perspective, and node, supports browser history, and can be shared. It uses local assets and has no accounts, analytics, or remote inference. Initial Veris content remains readable without JavaScript. Native README disclosures contain additional design notes for readers who stay on GitHub.

Primary rendering references: [GitHub Markup](https://github.com/github/markup), [collapsed sections](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections), [SVG image restrictions](https://github.com/mdn/content/blob/main/files/en-us/web/svg/guides/svg_as_an_image/index.md), and [workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
