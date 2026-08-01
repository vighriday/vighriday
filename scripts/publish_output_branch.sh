#!/usr/bin/env bash

set -euo pipefail

publish_dir="${1:-./dist}"
commit_message="${2:-chore: publish output assets}"
branch_name="${3:-output}"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is required" >&2
  exit 1
fi

if [[ ! -d "$publish_dir" ]]; then
  echo "Publish directory not found: $publish_dir" >&2
  exit 1
fi

git config --global user.name "github-actions[bot]"
git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"

repo_url="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
tmp_dir="$(mktemp -d)"

if git ls-remote --exit-code --heads "$repo_url" "$branch_name" >/dev/null 2>&1; then
  git clone --depth 1 --branch "$branch_name" "$repo_url" "$tmp_dir"
else
  git clone "$repo_url" "$tmp_dir"
  git -C "$tmp_dir" checkout --orphan "$branch_name"
  git -C "$tmp_dir" rm -rf . >/dev/null 2>&1 || true
fi

rsync -a --delete --exclude '.git' "${publish_dir%/}/" "$tmp_dir"/

git -C "$tmp_dir" add -A

if git -C "$tmp_dir" diff --cached --quiet; then
  echo "No output changes to publish."
  exit 0
fi

git -C "$tmp_dir" commit -m "$commit_message"
git -C "$tmp_dir" push origin "$branch_name"