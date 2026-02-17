#!/usr/bin/env bash
set -euo pipefail

GGUF_PATH="${1:-sexygpt-3.5-turbo-uncensored.gguf}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ Not inside a git repository."
  exit 1
fi

echo "Checking GGUF visibility for: $GGUF_PATH"

if [[ -f "$GGUF_PATH" ]]; then
  echo "✅ Local file exists: $GGUF_PATH"
else
  echo "❌ Local file missing: $GGUF_PATH"
  echo "   Generate or copy the GGUF file into this repository first."
fi

if git ls-files --error-unmatch "$GGUF_PATH" >/dev/null 2>&1; then
  echo "✅ File is tracked by git."
else
  echo "❌ File is not tracked by git."
  echo "   Run: git add .gitattributes '$GGUF_PATH' && git commit -m 'Add GGUF artifact'"
fi

if command -v git-lfs >/dev/null 2>&1; then
  if git lfs ls-files | awk '{print $NF}' | grep -Fx "$GGUF_PATH" >/dev/null 2>&1; then
    echo "✅ File is tracked by Git LFS."
  else
    echo "⚠️  File is not currently listed by git lfs ls-files."
    echo "   Ensure .gitattributes contains: *.gguf filter=lfs diff=lfs merge=lfs -text"
  fi
else
  echo "⚠️  git-lfs is not installed; cannot verify LFS tracking."
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "✅ origin remote: $(git remote get-url origin)"
else
  echo "❌ No origin remote configured."
  echo "   Run: git remote add origin <YOUR_GITHUB_REPO_URL>"
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
if [[ -n "$UPSTREAM" ]]; then
  AHEAD_BEHIND="$(git rev-list --left-right --count "$UPSTREAM"..."$BRANCH" 2>/dev/null || echo '0 0')"
  BEHIND="$(echo "$AHEAD_BEHIND" | awk '{print $1}')"
  AHEAD="$(echo "$AHEAD_BEHIND" | awk '{print $2}')"
  echo "ℹ️  Branch: $BRANCH (upstream: $UPSTREAM, ahead: $AHEAD, behind: $BEHIND)"
  if [[ "$AHEAD" != "0" ]]; then
    echo "❌ Local commits not pushed yet."
    echo "   Run: git push"
  fi
else
  echo "⚠️  Branch '$BRANCH' has no upstream."
  echo "   Run: git push -u origin $BRANCH"
fi
