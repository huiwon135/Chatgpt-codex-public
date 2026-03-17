#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required"
  exit 1
fi

repo_name="${GITHUB_REPO_NAME:-$(basename "$PWD")}"
visibility="${GITHUB_REPO_VISIBILITY:-private}"

if [ ! -d .git ]; then
  git init
fi

git add .
if ! git diff --cached --quiet; then
  git commit -m "Initial production GPT server setup"
fi

if ! gh repo view "$repo_name" >/dev/null 2>&1; then
  gh repo create "$repo_name" --"$visibility" --source=. --remote=origin --push
else
  if ! git remote get-url origin >/dev/null 2>&1; then
    gh repo set-default "$repo_name"
    git remote add origin "https://github.com/$(gh api user --jq .login)/$repo_name.git"
  fi
  git branch -M main
  git push -u origin main
fi
