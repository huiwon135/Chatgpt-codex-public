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


def merge_dirs(src1: Path, src2: Path, dst: Path, *, overwrite_dst: bool) -> tuple[int, int, int]:
    """Merge *src1* and *src2* into *dst*.

    Returns a tuple of:
    - files_from_src1
    - files_from_src2
    - skipped_conflicts_from_src2
    """
    if not src1.is_dir() or not src2.is_dir():
        raise FileNotFoundError("Both source paths must be existing directories")

    if dst.exists():
        if not overwrite_dst:
            raise FileExistsError(
                f"Destination already exists: {dst}. Use --overwrite-dst to replace it."
            )
        shutil.rmtree(dst)

    shutil.copytree(src1, dst)

    files_from_src1 = sum(1 for p in src1.rglob("*") if p.is_file())
    files_from_src2 = 0
    skipped_conflicts = 0

    for path in src2.rglob("*"):
        rel = path.relative_to(src2)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists():
            skipped_conflicts += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        files_from_src2 += 1

    return files_from_src1, files_from_src2, skipped_conflicts


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_vocab_size(dst: Path) -> tuple[int | None, str]:
    """Read config.vocab_size from *dst*.

    Returns (vocab_size, reason_if_missing).
    """
    config_path = dst / "config.json"
    if not config_path.exists():
        return None, "config.json not found"

    config = _read_json(config_path)
    if config is None:
        return None, "failed to parse config.json"

    vocab_size = config.get("vocab_size")
    if not isinstance(vocab_size, int) or vocab_size <= 0:
        return None, "config.vocab_size is missing or invalid"

    return vocab_size, ""


def fix_incompatible_tokenizer(dst: Path) -> tuple[bool, str]:
    """Remove tokenizer.json when it is incompatible with config vocab_size.

    Returns (removed, reason_message).
    """
    tok_json_path = dst / "tokenizer.json"

    if not tok_json_path.exists():
        return False, "tokenizer.json not found"

    vocab_size, vocab_reason = _read_vocab_size(dst)
    if vocab_size is None:
        return False, vocab_reason

    tokenizer_data = _read_json(tok_json_path)
    if tokenizer_data is None:
        return False, "failed to parse tokenizer.json"

    tok_vocab = tokenizer_data.get("model", {}).get("vocab", {})
    if not isinstance(tok_vocab, dict) or not tok_vocab:
        return False, "tokenizer vocab is missing or empty"

    try:
        max_token_id = max(int(v) for v in tok_vocab.values())
    except (TypeError, ValueError):
        return False, "tokenizer vocab ids are non-numeric"

    if max_token_id < vocab_size:
        return False, "tokenizer ids fit config.vocab_size"

    tok_json_path.unlink()
    return True, f"removed incompatible tokenizer.json (max token id {max_token_id} >= vocab_size {vocab_size})"


def fix_incompatible_added_tokens(dst: Path) -> tuple[bool, str]:
    """Remove added_tokens.json when token ids exceed config vocab_size.

    Returns (removed, reason_message).
    """
    added_tokens_path = dst / "added_tokens.json"
    if not added_tokens_path.exists():
        return False, "added_tokens.json not found"

    vocab_size, vocab_reason = _read_vocab_size(dst)
    if vocab_size is None:
        return False, vocab_reason

    added_tokens = _read_json(added_tokens_path)
    if added_tokens is None:
        return False, "failed to parse added_tokens.json"

    ids: list[int] = []
    if isinstance(added_tokens, dict):
        try:
            ids = [int(v) for v in added_tokens.values()]
        except (TypeError, ValueError):
            return False, "added_tokens.json has non-numeric ids"
    elif isinstance(added_tokens, list):
        try:
            ids = [int(item["id"]) for item in added_tokens if isinstance(item, dict) and "id" in item]
        except (TypeError, ValueError):
            return False, "added_tokens.json list has non-numeric ids"
    else:
        return False, "added_tokens.json has unsupported structure"

    if not ids:
        return False, "added_tokens.json contains no token ids"

    max_added_token_id = max(ids)
    if max_added_token_id < vocab_size:
        return False, "added token ids fit config.vocab_size"

    added_tokens_path.unlink()
    return (
        True,
        "removed incompatible added_tokens.json "
        f"(max added token id {max_added_token_id} >= vocab_size {vocab_size})",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src1", type=Path, help="Primary source directory")
    parser.add_argument("src2", type=Path, help="Secondary source directory")
    parser.add_argument("dst", type=Path, help="Output directory")
    parser.add_argument(
        "--overwrite-dst",
        action="store_true",
        help="Overwrite destination directory if it already exists",
    )
    args = parser.parse_args()

    from_src1, from_src2, conflicts = merge_dirs(
        args.src1, args.src2, args.dst, overwrite_dst=args.overwrite_dst
    )
    tok_removed, tok_reason = fix_incompatible_tokenizer(args.dst)
    added_removed, added_reason = fix_incompatible_added_tokens(args.dst)
    total = sum(1 for p in args.dst.rglob("*") if p.is_file())

    print(f"Merged into {args.dst} ({total} files)")
    print(f"- copied from primary: {from_src1}")
    print(f"- copied from secondary: {from_src2}")
    print(f"- skipped secondary conflicts: {conflicts}")
    if tok_removed:
        print(f"Tokenizer fix: {tok_reason}")
    else:
        print(f"Tokenizer fix: skipped ({tok_reason})")
    if added_removed:
        print(f"Added tokens fix: {added_reason}")
    else:
        print(f"Added tokens fix: skipped ({added_reason})")


if __name__ == "__main__":
    main()
