#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path-to-gguf> [commit-message]" >&2
  exit 1
fi

GGUF_PATH="$1"
COMMIT_MSG="${2:-Add GGUF artifact}"

if [[ ! -f "$GGUF_PATH" ]]; then
  echo "Error: GGUF file not found: $GGUF_PATH" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is not installed." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: current directory is not a git repository." >&2
  exit 1
fi

if ! command -v git-lfs >/dev/null 2>&1; then
  echo "Error: git-lfs is required. Install it first (e.g. apt-get install git-lfs)." >&2
  exit 1
fi

git lfs install >/dev/null

if ! grep -q '^\*\.gguf filter=lfs diff=lfs merge=lfs -text$' .gitattributes 2>/dev/null; then
  echo '*.gguf filter=lfs diff=lfs merge=lfs -text' >> .gitattributes
fi

git add .gitattributes "$GGUF_PATH"

if git diff --cached --quiet; then
  echo "No staged changes. Nothing to commit."
else
  git commit -m "$COMMIT_MSG"
fi

echo
echo "Ready to push."
if git remote get-url origin >/dev/null 2>&1; then
  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  echo "Run: git push -u origin $CURRENT_BRANCH"
else
  echo "No origin remote configured."
  echo "Run: git remote add origin <YOUR_GITHUB_REPO_URL>"
  echo "Then: git push -u origin $(git rev-parse --abbrev-ref HEAD)"
fi

echo "Verify LFS tracking with: git lfs ls-files"
