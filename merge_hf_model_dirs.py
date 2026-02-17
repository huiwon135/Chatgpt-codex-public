#!/usr/bin/env python3
"""Merge two local Hugging Face model directories into one output directory.

The first source directory wins on filename conflicts; files missing in source1 are
copied from source2.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def merge_dirs(src1: Path, src2: Path, dst: Path) -> None:
    if not src1.is_dir() or not src2.is_dir():
        raise FileNotFoundError("Both source paths must be existing directories")

    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src1, dst)

    for path in src2.rglob("*"):
        rel = path.relative_to(src2)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def fix_incompatible_tokenizer(dst: Path) -> bool:
    """Remove tokenizer.json when it is incompatible with config vocab_size.

    Returns True if a file was removed.
    """
    config_path = dst / "config.json"
    tok_json_path = dst / "tokenizer.json"
    vocab_json_path = dst / "vocab.json"

    if not (config_path.exists() and tok_json_path.exists() and vocab_json_path.exists()):
        return False

    config = json.loads(config_path.read_text(encoding="utf-8"))
    vocab_size = config.get("vocab_size")
    if not isinstance(vocab_size, int):
        return False

    tokenizer_data = json.loads(tok_json_path.read_text(encoding="utf-8"))
    tok_vocab = tokenizer_data.get("model", {}).get("vocab", {})
    if not tok_vocab:
        return False

    max_token_id = max(tok_vocab.values())
    if max_token_id < vocab_size:
        return False

    tok_json_path.unlink()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src1", type=Path, help="Primary source directory")
    parser.add_argument("src2", type=Path, help="Secondary source directory")
    parser.add_argument("dst", type=Path, help="Output directory")
    args = parser.parse_args()

    merge_dirs(args.src1, args.src2, args.dst)
    removed = fix_incompatible_tokenizer(args.dst)
    total = sum(1 for p in args.dst.rglob("*") if p.is_file())
    print(f"Merged into {args.dst} ({total} files)")
    if removed:
        print("Removed incompatible tokenizer.json (vocab exceeds config vocab_size)")


if __name__ == "__main__":
    main()
