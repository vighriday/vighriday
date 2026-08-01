# Profile README operating manual

This profile is authored for **Hriday Vig** / **`vighriday`** and uses a single indigo system:

| Token | Value | Role |
| --- | --- | --- |
| Accent | `#7C5CFC` | Actions, lines, badge body |
| Accent light | `#A78BFA` | Dark-mode highlights |
| Light ink / muted | `#21174A` / `#675E87` | Light-mode cards |
| Dark ink / muted | `#EEEAFF` / `#BDB4DA` | Dark-mode cards |
| Light / dark grid | `#DDD7F2` / `#352D55` | Borders and structure |

## 1. Make GitHub display the profile

GitHub only renders a profile README from a **public repository whose owner and repository names match exactly**. The checked-out repository is currently `vighriday/hriday29`; it will not render as the profile README. Create or rename to `vighriday/vighriday`, then push this project there.

1. On GitHub, create a public repository called `vighriday` under the `vighriday` account. Do not initialise it with a README.
2. Change this local remote to the new URL, or copy the files into that repository.
3. Push `main`. The static profile, typed hero, local portrait placeholder, stat cards, tech stack, and project cards work immediately.
4. In **Settings -> Actions -> General**, choose **Read and write permissions** and allow GitHub Actions to create and approve pull requests if your organisation requires it. The workflows use the more precise `contents: write` permission as well.
5. Create an empty `output` branch once (`git switch --orphan output`, commit a `.gitkeep`, and push), or let the first generator workflow create it. It holds generated assets only; do not merge it into `main`.

The README intentionally points generated images at `raw.githubusercontent.com/vighriday/vighriday/output/...`. If you keep a different account/repository name, replace every occurrence of that path and the username query parameter in `README.md` plus workflow inputs.

## 2. First 10-minute go-live

1. Create the special repository and push `main`.
2. Add the optional secret/variable values below that you plan to use.
3. Open **Actions** and manually run, in order: **Refresh profile signal**, **Regenerate ASCII portrait**, **Generate contribution snake**, **Generate Pacman contribution graph**, **Generate 3D contribution graph**, and **Generate full metrics dashboard**.
4. Reload the profile after each workflow completes. The local “dynamic asset pending” SVGs are deliberate safe fallbacks until `output` exists.
5. Add a real portrait, rerun the ASCII workflow, and verify both GitHub light and dark appearance.
6. If you write online, add `BLOG_RSS_URL`, then run **Update latest blog posts**.
7. Verify the activity and WakaTime sections after their first successful jobs.
8. Pin `Veris`, `Pulse`, and `offside-june-2026` on GitHub if they are your preferred public showcase set.
9. View the profile on a narrow mobile viewport. All primary assets are capped at 800px and the only table is a flexible two-column neofetch layout.
10. Return here occasionally to update immutable action pins as maintainers release security fixes.

## 3. Replace the ASCII portrait

`assets/portrait-placeholder.ppm` is a committed abstract avatar so the README works before you supply a photo. It is not a claim that it depicts you.

Put a square-ish JPG or PNG at `assets/portrait-source.jpg` (or `assets/portrait-source.png`), then run:

```powershell
python -m pip install -r requirements.txt
python scripts/ascii_portrait.py assets/portrait-source.jpg --output-dir assets --name ascii-portrait --ramp blocks --edge --color --animation all
```

The script generates:

- `ascii-portrait.txt`: plain text for terminal use, never embedded in the README.
- `ascii-portrait-color.txt`: ANSI-coloured terminal output when `--color` is set.
- `ascii-portrait-static.svg`: non-animated SVG, with built-in dark/light CSS.
- `ascii-portrait-scanline.svg`: row-by-row terminal reveal.
- `ascii-portrait-shimmer.svg`: subtle per-cell glow/matrix shimmer.

Useful variants:

```powershell
# Classic punctuation ramp, wide and clean
python scripts/ascii_portrait.py assets/portrait-source.jpg --width 72 --ramp classic

# High-detail Braille characters, no edge pass
python scripts/ascii_portrait.py assets/portrait-source.png --width 80 --ramp braille --animation shimmer
```

The `ascii-regen.yml` workflow selects your JPG, then PNG, then the safe placeholder. It publishes regenerated files to `output`; the committed local SVGs keep the README non-broken before an Action has ever run. CSS and SMIL live **inside** each SVG, not inside the README, so GitHub’s sanitizer cannot strip the animation.

## 4. Dynamic feeds

| Capability | Add this | What happens |
| --- | --- | --- |
| Blog posts | Repository variable `BLOG_RSS_URL` | `blog-posts.yml` runs every six hours and updates the `BLOG-POST-LIST` block with five posts. It stays inert until the variable is non-empty. |
| GitHub activity | Nothing | `activity.yml` runs every twelve hours and updates the activity comment block. |
| WakaTime | Repository secret `WAKATIME_API_KEY` and variable `ENABLE_WAKATIME=true` | `wakatime.yml` runs daily. Create an API key in WakaTime, save it as a secret, then enable the explicit repository variable. |
| Total-star badge / refresh status | Nothing for public repos | `refresh.yml` sums public repository stars through GitHub’s API, writes Shields Endpoint JSON, and regenerates a timestamped status SVG daily. |
| Metrics dashboard | Prefer secret `METRICS_TOKEN` | `metrics.yml` runs daily. A fine-grained PAT with read access to your profile-visible repositories reduces API limits and unlocks private contribution data where GitHub permits it. Without it, the workflow falls back to the ephemeral workflow token. |

For a classic PAT, use minimum necessary access: `read:user`, read access to the relevant repositories, and `repo` only if you deliberately need private repository statistics. Keep it as `METRICS_TOKEN`; never paste it into a workflow or README. `GITHUB_TOKEN` is generated by GitHub and needs no manual secret.

### Optional integrations

None of these are enabled until you choose to configure them; the README is intentionally quiet rather than displaying a broken external card.

- **Spotify:** deploy [novatorem](https://github.com/novatorem/novatorem) to your own Vercel account. Create a Spotify developer app with a local redirect URI, get a refresh token through Novatorem’s documented login flow, and add `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_REFRESH_TOKEN` to Vercel (not this repository). When the deployment works, add its `api/spotify` card URL inside the “Optional integrations” details section. `spotify-github-profile` is a simpler alternative but has less control over theming and ownership.
- **LeetCode / chess.com / Lichess / AniList / MAL / Stack Overflow:** enable the matching `lowlighter/metrics` plugin only after adding its public username or required token. Change `plugin_leetcode`, `plugin_chess`, `plugin_music`, or `plugin_rss` from `no` in both metrics jobs, then supply that plugin’s documented inputs. Keeping the defaults disabled avoids failed daily runs.
- **Community chess through Issues:** it is deliberately not installed because you have not opted in. The complete implementation would add an issue template with move coordinates, an `issues: write` workflow that validates legal moves, stores game state, regenerates a board SVG into `output`, and closes/comment-replies to the issue. This needs anti-spam decisions and an issue moderation policy, so add it only when you explicitly want that community surface.
- **Pinned gist widgets:** productive-box, spotify-box, and book-box belong in public pinned gists, not in this README. Create and pin those gists on your profile if you want that ecosystem.

## 5. How the visual system works

Change the palette first in the HTML comment at the beginning of `README.md`, then update the `THEME` dictionary in `scripts/build_assets.py`. That script produces the signature divider, fallback cards, profile status signal, and placeholder avatar. It embeds `@media (prefers-color-scheme: dark)` into every self-authored SVG.

External SVG/card services use paired `<picture>` sources where they accept custom colours. GitHub Profile Trophy and Profile Summary Cards instead use GitHub's `#gh-light-mode-only` / `#gh-dark-mode-only` fragment mechanism. Those services only expose named themes (not arbitrary hex values), so their GitHub/Dracula variants are the closest stable match; the fully colour-controlled Readme Stats cards and self-authored metrics SVG are the indigo-perfect alternatives. Snake and 3D contribution actions have the same colour-palette limitation. Skill Icons exposes product colours by design; its surrounding badge system retains the indigo palette.

Run this whenever you change local theme assets:

```powershell
python scripts/build_assets.py
```

### Cache behaviour

GitHub proxies remote images through **Camo** and caches aggressively. A successful Action can take several minutes to appear even though `raw.githubusercontent.com/.../output/...` already has the new SVG. Do not add random query strings to every card: that defeats useful caching and can be ignored by Camo. Instead, regenerate on the supplied schedules, confirm the raw URL first, and use a one-off query suffix such as `?v=20260801` only while troubleshooting a known stale visual. A changed generated filename is the most reliable hard refresh.

## 6. Workflow notes and service fallbacks

Every workflow has `workflow_dispatch`, an explicit cron schedule, a narrow permissions block, and a full commit SHA for each external action. Cron times are staggered in UTC to avoid a daily thundering herd.

| Service | If it is unavailable | Self-hosted / low-dependency alternative |
| --- | --- | --- |
| `github-readme-stats` / streak / activity graph | The corresponding remote card can 404 or rate-limit. | Use `lowlighter/metrics` output in `output`, or generate a static SVG with GitHub API data. |
| Snake / Pacman / 3D graph | The local animated placeholder remains visible before the workflow’s first run. | Keep a last-known-good SVG in `output`, or use the metrics isocalendar. |
| Summary cards / trophies | Named themes may drift or card URLs may fail. | Rely on the custom-colour stats and metrics dashboard. |
| Skill Icons | An icon service outage affects the icon row only. | Replace it with indigo Shields badges; the needed badge pattern is already used below it. |
| Capsule / typing / quote cards | They are decorative and can be temporarily unavailable. | `assets/hero-fallback.svg`, plain README headings, and the self-generated `assets/quote-card.svg` are safe substitutes. |

The Pacman project is now branded as Arcade Graph but preserves the Pacman action and output names used here. Snake, Pacman, 3D, and metrics all deploy only generated outputs to the dedicated `output` branch; they do not rewrite your authored README on `main`.

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Snake/Pacman/3D shows a pending card or 404 | `output` does not exist yet, or Actions lack write permission. | Enable read/write workflow permissions, manually run the workflow, then confirm the named file exists on `output`. |
| Stats cards rate-limit or omit private counts | The public demo endpoint is shared; private data needs a token and GitHub profile setting. | Wait for the limit, use the metrics SVG, add `METRICS_TOKEN`, and enable “Include private contributions” in GitHub profile settings. |
| Private commits still do not count | GitHub only exposes eligible contributions and the repository/action token cannot override account privacy. | Verify contribution settings and author email; treat `count_private=true` as a request, not a bypass. |
| Dark image does not switch | Browser/GitHub cache, a malformed `<picture>`, or SVG rendered from a stale Camo copy. | Open the raw asset, test GitHub dark mode, wait briefly, then use a temporary one-off cache suffix while diagnosing. |
| Action says permission denied | Repository Actions permissions are read-only, or the workflow token is restricted by an organisation. | Set Actions to read/write, check the workflow’s `contents: write`, and use a scoped PAT only if organisation policy requires it. |
| Metrics jobs clash while committing | Both variants attempt to commit to `output` at once. | Keep the dark job dependent on the light job (already configured) and rerun the failed job once. |
| Blog workflow does nothing | `BLOG_RSS_URL` has not been set or the feed is invalid. | Add a public, valid feed URL as a repository variable and run it manually. |

## 8. Content maintenance

The résumé-driven content in the README reflects: B.Tech CSE at MSIT (expected 2028), NIIT MTS internship, BluOryn platform work, Proofr Startup Catalyst, Offside’s first-place IBM SkillsBuild x BeMyApp result, and the Veris/Pulse/Scrybe AI projects. Update those sections as your story changes; do not let automation overwrite them.

Before adding a new card or badge, ask two questions: does it support the indigo theme or have a documented limitation, and is its failure mode graceful? If either answer is no, prefer a self-authored SVG in `scripts/build_assets.py`.
