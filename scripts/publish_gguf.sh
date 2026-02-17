#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/publish_gguf.sh <path-to-gguf> [commit-message] [--push]

Examples:
  ./scripts/publish_gguf.sh sexygpt-3.5-turbo-uncensored.gguf
  ./scripts/publish_gguf.sh sexygpt-3.5-turbo-uncensored.gguf "Add GGUF artifact" --push
USAGE
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

GGUF_PATH="$1"
shift

COMMIT_MSG="Add GGUF artifact"
DO_PUSH="false"

for arg in "$@"; do
  if [[ "$arg" == "--push" ]]; then
    DO_PUSH="true"
  else
    COMMIT_MSG="$arg"
  fi
done

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

echo "\nStaged files:"
git diff --cached --name-status

if git diff --cached --quiet; then
  echo "No staged changes. Nothing to commit."
else
  git commit -m "$COMMIT_MSG"
fi

echo "\nLFS-tracked files:"
git lfs ls-files || true

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "\nNo origin remote configured."
  echo "Run: git remote add origin <YOUR_GITHUB_REPO_URL>"
  echo "Then: git push -u origin $CURRENT_BRANCH"
  exit 0
fi

if [[ "$DO_PUSH" == "true" ]]; then
  echo "\nUploading LFS object(s) first..."
  git lfs push origin "$CURRENT_BRANCH"

  echo "Pushing git refs..."
  git push -u origin "$CURRENT_BRANCH"
  echo "\nPush completed."
else
  echo "\nReady to push."
  echo "Recommended (avoid missing-LFS-pointer errors):"
  echo "  git lfs push origin $CURRENT_BRANCH"
  echo "  git push -u origin $CURRENT_BRANCH"
fi
