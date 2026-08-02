# SETUP

Everything needed to run this profile, in the order you need it.

The profile is a build, not a document. Nine workflows generate assets on a
schedule; a tenth asserts the result is safe to render. This file covers the
manual steps that cannot be automated, what breaks when they are skipped, and
how to fix each failure.

---

## 0. Ten-minute go-live checklist

| # | Step | Time |
|---|------|------|
| 1 | Repo `vighriday/vighriday` exists and is **public** | 1 min |
| 2 | **Settings → Actions → General → Workflow permissions → Read and write** | 1 min |
| 3 | Create the `output` branch (§3) | 1 min |
| 4 | Add the `METRICS_TOKEN` secret (§4) | 3 min |
| 5 | Push `main` | 1 min |
| 6 | Run `verify` — must be green before anything else | 1 min |
| 7 | Run `refresh`, then `snake`, `pacman`, `3d-contrib`, `metrics`, `activity` (§6) | 2 min |
| 8 | Hard-reload your profile page in both light and dark mode | 1 min |

Everything else on this page is optional.

---

## 1. What works with zero configuration

These render the moment you push, before any workflow has ever run:

- Amber CRT hero banner (`assets/hero-crt.svg`) — self-hosted, animated
- ASCII portrait, all three variants — self-hosted, animated, dual-theme
- Every section divider — self-hosted, animated
- Contribution oscilloscope, commit clock, language bars — self-hosted
- Quote card and pipeline-status strip — self-hosted
- All shields.io badges, skillicons rows, and social buttons
- capsule-render wave header and footer
- readme-typing-svg intro line
- github-readme-stats, top-langs, streak, activity graph, trophies, pin cards
- Every `<details>` section, with a themed placeholder inside

Anything not in that list falls back to a labelled placeholder card, so the
page never shows a broken image.

### Why the self-hosted charts are plain `<img>`, not `<picture>`

Every SVG generated in this repo carries its own
`@media (prefers-color-scheme: dark)` rules, so one file is already correct in
both themes. A `<picture>` would add nothing except a second URL that can fail.

That matters more than it sounds, because of a trap worth knowing:

> **A `<picture>` does not fall back to its `<img>` when a `<source>` fails to
> *load*. It only falls back when no `<source>` *matches*.**

So a dark-mode `<source>` pointing at a file that no workflow has published yet
renders *nothing at all* in dark mode — not the fallback image. The profile
looks broken to every dark-mode visitor, and it looks fine to you if you browse
in light mode.

Two defences are in place:

1. `refresh.yml` **seeds** the output branch with themed placeholders for
   `snake`, `pacman`, `contrib-3d` and `metrics` on its first run, so those URLs
   resolve before their own workflows have ever run. Seeding is idempotent — a
   file already on the branch is never overwritten.
2. `verify_readme.py` fails the build if the README loads an output-branch file
   that no workflow writes, or uses one as a `<picture>` source without a
   matching seed line.

---

## 2. Repository basics

The repo name must exactly equal the username: `vighriday/vighriday`. GitHub
only renders a README on your profile for that one repository, and only if it
is **public**. A private repo of the same name renders nothing, silently.

```bash
git clone https://github.com/vighriday/vighriday.git
cd vighriday
pip install -r requirements.txt
python scripts/build.py          # rebuild everything and verify
```

**Settings → Actions → General:**

- Actions permissions: *Allow all actions and reusable workflows*
- Workflow permissions: **Read and write permissions** ← required

Without read/write, every workflow that commits fails with
`remote: Permission to ... denied to github-actions[bot]`.

---

## 3. The `output` branch

Generated assets are published to a dedicated `output` branch rather than
`main`, so a daily regeneration never floods your commit history and never
touches source. The README pulls them from
`raw.githubusercontent.com/vighriday/vighriday/output/...`.

Create it once:

```bash
git switch --orphan output
git commit --allow-empty -m "output: initialise generated asset branch"
git push -u origin output
git switch main
```

Every publishing workflow uses `keep_files: true`, so each one adds its files
without deleting the others. They also share a `concurrency` group
(`profile-output-branch`), which serialises them — otherwise two workflows
finishing in the same minute would race and one would lose its push.

---

## 4. Secrets and variables

**Settings → Secrets and variables → Actions**

| Name | Kind | Required for | How to get it |
|------|------|--------------|---------------|
| `METRICS_TOKEN` | Secret | `metrics.yml` only | [Classic PAT](https://github.com/settings/tokens/new?scopes=public_repo,read:user) with `public_repo` + `read:user` |
| `WAKATIME_API_KEY` | Secret | `wakatime.yml` | <https://wakatime.com/settings/api-key> |
| `BLOG_FEED_URLS` | **Variable** | `blog-posts.yml` | Your RSS URL(s), comma-separated |

`GITHUB_TOKEN` is provided automatically — never create it yourself.

> **On `.env`:** GitHub Actions cannot read a `.env` file from your machine, and
> committing one would publish the key to a public repo. `.env` is gitignored
> here for that reason. Secrets go in the repository secrets UI, full stop.

### Why `refresh.yml` also reaches for `METRICS_TOKEN`

The contribution calendar is only exposed through GitHub's GraphQL API, which
rejects anonymous requests outright. `refresh.yml` prefers `METRICS_TOKEN` and
falls back to `GITHUB_TOKEN`.

**In practice the fallback is enough** — verified on the first run, where the
default `GITHUB_TOKEN` returned the full calendar and the oscilloscope rendered
real data. So `METRICS_TOKEN` is only genuinely required by `metrics.yml`. If
neither token works, the oscilloscope renders a labelled placeholder and the
workflow still passes.

### WakaTime

1. Sign up at <https://wakatime.com> and install the plugin for your editor —
   without a plugin sending heartbeats, the API returns zeros forever.
2. Copy the key from <https://wakatime.com/settings/api-key>.
3. Add it as the `WAKATIME_API_KEY` repository secret.
4. Run `wakatime.yml` manually once.

Until the secret exists, `wakatime.yml` logs a notice and exits cleanly.

---

## 5. Dynamic feeds

### Blog posts

Set the repository **variable** `BLOG_FEED_URLS`, for example:

```
https://yoursite.com/rss.xml,https://dev.to/feed/vighriday,https://medium.com/feed/@vighriday
```

`blog-posts.yml` runs every 6 hours and rewrites the block between
`<!-- BLOG-POST-LIST:START -->` and `<!-- BLOG-POST-LIST:END -->`. **Never
delete those comments** — they are the only thing telling the updater where to
write. `verify_readme.py` fails the build if a `START` marker loses its `END`.

With no variable set, the workflow exits without touching the README, so the
"no feed connected yet" placeholder stays.

### Recent activity

`activity.yml` needs nothing. It rewrites the `START_SECTION:activity` block
every 12 hours from your public event feed.

---

## 6. First-run order

Run these manually from the **Actions** tab (each has a *Run workflow* button).
Order matters: `verify` first proves the README is sound, `refresh` seeds the
output branch, and the rest fill in around it.

1. **verify** — must be green. If it fails, nothing else is worth running.
2. **refresh** — oscilloscope, commit clock, language bars, quote, status strip, stars badge
3. **snake**
4. **pacman**
5. **3d-contrib**
6. **metrics** — only after `METRICS_TOKEN` exists
7. **activity**
8. **blog-posts** — only after `BLOG_FEED_URLS` exists
9. **wakatime** — only after `WAKATIME_API_KEY` exists

`ascii-regen` runs by itself whenever you push a new `assets/portrait-source.png`.

### Schedule

Crons are staggered so they never fire in the same minute and never queue
behind each other on the output branch:

| Workflow | Cron (UTC) |
|----------|-----------|
| `snake` | `17 2 * * *` |
| `pacman` | `47 2 * * *` |
| `3d-contrib` | `17 3 * * *` |
| `metrics` | `47 3 * * *` |
| `refresh` | `17 4 * * *` |
| `wakatime` | `47 4 * * *` |
| `blog-posts` | `7 */6 * * *` |
| `activity` | `23 */12 * * *` |

> GitHub deprioritises scheduled workflows on busy runners; a cron can drift by
> 10–30 minutes. That is normal and not a failure.

---

## 7. The ASCII portrait

### Regenerating from your own photo

```bash
# Option A - use your GitHub avatar (what is committed now)
python scripts/fetch_avatar.py

# Option B - use any photo
cp /path/to/photo.jpg assets/portrait-source.png

python scripts/ascii_portrait.py assets/portrait-source.png --preview
```

`--preview` writes `preview/ascii-portrait-{light,dark}.png`, which is exactly
what the SVG will render. **Look at those before committing** — the tuning below
is photo-dependent and the previews are the fastest way to judge it.

**Commit:** `assets/portrait-source.png` and every `assets/ascii-portrait-*`.
The `preview/` directory is gitignored.

Or skip local Python entirely: commit a new `assets/portrait-source.png`, push,
and `ascii-regen.yml` rebuilds and commits the portrait for you. That workflow
also accepts ramp/width/edge overrides via *Run workflow*.

### Tuning

| Flag | Default | What it does |
|------|---------|--------------|
| `--ramp` | `blocks` | `blocks` wins at README scale — at ~6px per cell the eye reads density, not glyph shape. `classic` and `fine` look better rendered large. `braille` packs a real 2×4 bitmap per glyph for maximum detail, but Braille glyph coverage varies by font. |
| `--width` | `64` | Character columns. Higher is more detailed and less legible at 370px. |
| `--edge` | `0.28` | Darkens along gradients. **The single most important flag for faces** — a well-lit face is tonally flat, so pure luminance loses the eyes and mouth entirely. |
| `--gamma` | `1.30` | Above 1 deepens shadows. |
| `--clip` | `0.10` | Percentile autocontrast per side. |
| `--matte` | `0.16` | Floods the flat backdrop to blank so the head floats. Raise it if background noise survives; lower it if it eats the subject. |
| `--flatten` | `0.0` | Illumination flattening. **Leave off for portraits** — it erases the large-scale shading that makes a face read as three-dimensional. |
| `--no-dither` | off | Disables Floyd–Steinberg error diffusion. Try it if the output looks noisy rather than detailed. |

Best source material: head-and-shoulders, plain background, even lighting,
subject clearly brighter or darker than the backdrop.

### Why the SVG has two glyph layers

On a light background a dense glyph is dark ink, so dark pixels take dense
glyphs. On a dark background that same glyph is bright phosphor, so the mapping
has to invert — otherwise dark mode shows a photographic negative.

CSS cannot rewrite text content, but it can hide an entire group. So both
layers ship in one file and `prefers-color-scheme` toggles `display` between
them. That is also why the file is ~25 KB rather than ~13 KB.

---

## 8. Changing the theme

One edit, one command:

```bash
# 1. edit THEME in scripts/theme.py
# 2. rebuild everything
python scripts/build.py
```

`scripts/retheme.py` diffs the live palette against `.theme-lock.json`, rewrites
every hex in `README.md` and `SETUP.md`, and updates the lock.
`scripts/build_assets.py` and `scripts/ascii_portrait.py` repaint the SVGs.
`scripts/verify_readme.py` then **fails** if any colour outside the palette
survived — so a half-finished retheme cannot ship.

Preview the change without writing: `python scripts/retheme.py --check`.

### Three places the palette cannot be enforced

Some services ship fixed themes instead of colour parameters:

- **github-profile-trophy** — preset themes only. Uses `gruvbox` (dark) and
  `flat` (light) with `no-bg=true&no-frame=true`, which are the closest warm
  presets and blend into the page background.
- **github-profile-summary-cards** — preset themes only. Uses `gruvbox` and
  `github`.
- **github-profile-3d-contrib** — fixed palettes. Set the `SETTING_JSON` env var
  in `3d-contrib.yml` to a custom settings file if you want it repainted.

`lowlighter/metrics` has no colour parameters either, but it does accept
`extras_css`, which `metrics.yml` uses to impose the amber palette directly.

---

## 9. Camo, and why your change is not showing

GitHub proxies every external image through **Camo** and caches aggressively.
A workflow can succeed and the profile can still show yesterday's asset.

- Assets under `assets/` in this repo are served through Camo too, but bust
  automatically when the file's commit changes.
- Assets on the `output` branch keep the same URL forever, so Camo is the only
  thing deciding when you see the new one.

**To force a refresh:**

1. Hard-reload: <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd> (<kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd> on macOS).
2. Purge one image — copy its Camo URL from the rendered page and:
   ```bash
   curl -X PURGE "https://camo.githubusercontent.com/<hash>"
   ```
3. Wait. Camo TTL is minutes to a few hours; it always resolves on its own.

The **pipeline status strip** at the bottom of the profile exists for exactly
this. It prints the timestamp of the last successful `refresh` run. If that
timestamp is current, the pipeline is fine and you are looking at a cache. If
it is days old, the pipeline is broken — check the Actions tab.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| **Snake / pacman / 3D image 404s** | The `output` branch does not exist, or that workflow has never run | Create `output` (§3), then run the workflow manually. Confirm the file landed: `git ls-tree -r origin/output --name-only` |
| **Stats / top-langs / pin cards blank or "Maximum retries exceeded"** | The shared `github-readme-stats` instance is rate-limited or over quota across all its users. Not your fault and not fixable from here. **Verified returning `503 Service Unavailable` at the time this repo was built** | Wait — it usually recovers within hours. For a permanent fix, [deploy your own instance to Vercel](https://github.com/anuraghazra/github-readme-stats#deploy-on-your-own) (about 5 minutes, free tier) and replace `github-readme-stats.vercel.app` with your deployment's hostname everywhere in the README. The self-hosted charts under *Telemetry → Self-hosted instruments* never have this problem — that is exactly why they exist |
| **Trophy shelf blank** | `github-profile-trophy` runs on a Vercel account that periodically exceeds its billing limit and returns `402 Payment Required`. **Verified returning 402 at the time this repo was built** — this one is chronic, not transient | Either leave it (it returns when the quota resets) or delete the two `github-profile-trophy` lines in *Telemetry*. Nothing else depends on them, and `verify` stays green either way |
| **Private commits are not counted** | `count_private=true` only counts private commits in repos the token can see, and the shared instance cannot see yours | Already set on the card. For real private history you must self-host github-readme-stats with your own PAT |
| **Dark-mode image does not switch** | Either the `<picture>` `<source>` 404s, or the `#gh-dark-mode-only` fragment was used on a `<picture>` (it only works on a plain `<img>`) | Use `<picture>` + `<source media="(prefers-color-scheme: dark)">` for assets that exist in both themes, and the `#gh-dark-mode-only` / `#gh-light-mode-only` fragment for services that only expose preset themes. Both patterns are in this README — copy the nearest one. Note a `<picture>` does **not** fall back to its `<img>` when a `<source>` fails to *load*, only when no `<source>` *matches* |
| **`Permission to ... denied to github-actions[bot]`** | Workflow permissions are read-only | Settings → Actions → General → Workflow permissions → **Read and write** (§2) |
| **`metrics` skipped with a notice** | `METRICS_TOKEN` is not set | Add the secret (§4). Skipping rather than failing is intentional, so the profile keeps its placeholder |
| **`verify` fails on "Generated assets differ"** | An asset in `assets/` was hand-edited | Run `python scripts/build.py` and commit. Never edit generated SVGs directly — the next scheduled run overwrites them |
| **`verify` fails on `theme`** | A colour was hand-edited into the README | Put it in `scripts/theme.py` and run `python scripts/build.py` |
| **Typing / wave banner is blank** | capsule-render or readme-typing-svg is cold-starting | Both are Vercel-hosted. `assets/hero-crt.svg` is the self-hosted equivalent already on the page, so the hero never goes empty |

---

## 11. Optional integrations

None of these ship enabled. Each is a live third-party dependency on a page
that is otherwise self-contained, so turning one on is a deliberate choice.

### Spotify — now playing

Two options; **`spotify-github-profile` is the more maintained one** and needs
no deploy of your own:

1. Create an app at <https://developer.spotify.com/dashboard>.
2. Add redirect URI `https://spotify-github-profile.kittinanx.com/api/callback`.
3. Visit <https://spotify-github-profile.kittinanx.com/> and authorise.
4. Paste the generated markdown into the README, adding
   `&background_color=0B0906&bar_color=FFB000` to keep it on-theme.

The alternative, [novatorem](https://github.com/novatorem/novatorem), gives full
control but requires deploying your own Vercel instance and managing the
client id / secret / refresh-token flow yourself.

> Caveat either way: the card reads "not playing" most of the time, and it tells
> every visitor what you are listening to right now.

### LeetCode

```html
<img src="https://leetcard.jacoblin.cool/YOUR_USERNAME?theme=dark&font=JetBrains%20Mono&ext=heatmap" alt="LeetCode statistics">
```

Public API, no secret. Skip it if you do not actively practise — an empty card
is worse than no card.

### Chess

`lowlighter/metrics` has a chess plugin (`plugin_chess`) that takes a chess.com
or Lichess username. Add it to `metrics.yml` alongside the other plugins.

### Pinned-gist widgets

The [awesome-pinned-gists](https://github.com/matchai/awesome-pinned-gists)
ecosystem — `productive-box` (commit hours), `spotify-box`, `book-box` — writes
into **pinned gists**, not the README. They show up on your profile as pinned
items above the README, and each needs its own gist plus a PAT with the `gist`
scope. Note that `productive-box` duplicates what the self-hosted commit clock
already shows, without the theming.

### Community chess by GitHub Issues

Not implemented — documented here by request.

Tim Burgan's version turns a profile README into a multiplayer game with no
server:

1. The README shows a board rendered as an SVG.
2. Every square is a link that opens a pre-filled *new issue*, e.g. a title of
   `chess|move|e2e4`.
3. Submitting the issue triggers a workflow.
4. The workflow parses the title, validates the move against the current
   position, updates the stored board state, re-renders the board SVG, commits
   it, replies to the issue, and closes it.
5. The profile now shows the new position.

The plumbing is easy. The hard part is that step 4 needs a real chess engine —
legal move generation, check and checkmate detection, castling, en passant,
promotion — with no dependency you would want to trust inside a public
workflow. Budget roughly 600 lines of stdlib Python plus a test suite.

Requirements: Issues enabled, `issues: write` and `contents: write` permissions,
an `on: issues: types: [opened]` trigger, and a committed `state/board.json`.

---

## 12. If a service disappears

Every third-party card on the profile has a documented escape route. The
*Telemetry → Self-hosted instruments* section already carries the important
signal without any of them.

| Service | If it dies | Self-hosted alternative |
|---------|-----------|-------------------------|
| github-readme-stats | Stats, top-langs and pin cards 404 | `scripts/gh_charts.py` already renders the language mix. Or self-deploy the upstream to Vercel |
| streak-stats | Streak card 404s | Derivable from the contributions calendar `gh_charts.py` already fetches |
| github-readme-activity-graph | Activity chart 404s | `assets/oscilloscope.svg` covers the same data over a longer window |
| capsule-render | Wave header and footer go blank | `assets/hero-crt.svg`, already on the page |
| readme-typing-svg | Typing line goes blank | `assets/hero-crt.svg` types natively, in pure CSS |
| github-profile-trophy | Trophy shelf 404s | Delete the two lines; nothing else depends on it |
| skillicons.dev | Stack icons 404 | Replace with shields.io badges, already used for the rest of the stack |
| Platane/snk | Snake 404s | `assets/snake-placeholder.svg` shows instead |

---

## 13. Tool choices

Where two tools do the same job, the more maintained one was picked:

| Job | Chosen | Alternative | Why |
|-----|--------|-------------|-----|
| Contribution snake | `Platane/snk` | `Platane/snk-advanced` | `snk` is the maintained entry point; `snk-advanced` is deprecated |
| Publishing to a branch | `peaceiris/actions-gh-pages` | `crazy-max/ghaction-github-pages` | `keep_files: true` lets nine workflows share one branch without deleting each other |
| Committing to `main` | `stefanzweifel/git-auto-commit-action` | raw `git` shell steps | Handles the no-changes case without failing the run |
| Blog posts | `gautamkrishnar/blog-post-workflow` | `sarthology/rss-parser-action` | Actively maintained; the alternative has been dormant for years |
| Coding time | `athul/waka-readme` | `anmol098/waka-readme-stats` | `athul` is simpler and needs no PAT; `anmol098` shows more but wants `repo` scope |
| Spotify | `spotify-github-profile` | `novatorem` | Hosted, so there is no Vercel deploy to maintain |

All actions are pinned to a full commit SHA with the version in a trailing
comment. A tag can be moved to point at different code; a SHA cannot. To
upgrade, resolve the new tag to its SHA and update both.

---

## 14. The verifier

`verify.yml` runs on every push and pull request.

```bash
python scripts/verify_readme.py             # check the real README
python scripts/verify_readme.py --self-test # check the checker
python scripts/verify_readme.py --strict    # warnings fail too
```

It asserts:

| Check | What it catches |
|-------|-----------------|
| `sanitizer` | `<script>`, `<style>`, `<iframe>`, `style=`, `on*=`, any tag off GitHub's allowlist |
| `assets` | Any relative `src`/`srcset` that does not resolve on disk |
| `a11y` | Any `<img>` with missing or useless `alt` text |
| `layout` | Anything wider than 830px, and raw block art outside a code fence |
| `structure` | Unbalanced tags, and `X:START` markers that lost their `X:END` |
| `theme` | Any hex outside the palette, any badge off the `for-the-badge` family |
| `svg` | SVGs that are malformed, contain script, reference external hosts, declare a DTD, or lack a `prefers-color-scheme` rule |
| `assets` (output branch) | Any output-branch file no workflow writes, or used as a `<picture>` source without a seed line — the dark-mode-renders-nothing trap in §1 |

`--self-test` feeds it fifteen known-bad documents and asserts each is caught
for the right reason — because a linter that silently stops working is worse
than no linter.

`verify.yml` additionally regenerates the assets and fails if the result differs
from what is committed, which catches hand-edited generated files before the
next scheduled run silently reverts them.
