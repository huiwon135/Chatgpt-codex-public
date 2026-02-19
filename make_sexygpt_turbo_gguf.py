#!/usr/bin/env python3
"""Build GGUF from sexyGPT-Uncensored + gpt-3.5-turbo local dirs.

Workflow:
1) Merge model directories with sexyGPT as primary.
2) Remove incompatible tokenizer/added_tokens artifacts when needed.
3) Run llama.cpp convert_hf_to_gguf.py to generate GGUF.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from merge_hf_model_dirs import (
    fix_incompatible_added_tokens,
    fix_incompatible_tokenizer,
    merge_dirs,
)


def _resolve_convert_script(llama_cpp_dir: Path) -> Path:
    script = llama_cpp_dir / "convert_hf_to_gguf.py"
    if not script.is_file():
        raise FileNotFoundError(f"convert_hf_to_gguf.py not found: {script}")
    return script


def _ensure_existing_dir(path: Path, label: str) -> None:
    if not path.is_dir():
        raise FileNotFoundError(f"{label} directory not found: {path}")


def _maybe_clone_llama_cpp(llama_cpp_dir: Path, clone_if_missing: bool) -> None:
    if llama_cpp_dir.is_dir():
        return
    if not clone_if_missing:
        raise FileNotFoundError(
            f"llama.cpp directory not found: {llama_cpp_dir}. "
            "Pass --clone-llama-cpp-if-missing to clone automatically."
        )

    subprocess.run(
        ["git", "clone", "https://github.com/ggerganov/llama.cpp.git", str(llama_cpp_dir)],
        check=True,
    )


def build_gguf(
    sexygpt_dir: Path,
    turbo_dir: Path,
    merged_dir: Path,
    output_gguf: Path,
    llama_cpp_dir: Path,
    outtype: str,
    overwrite_merged: bool,
    clone_llama_cpp_if_missing: bool,
) -> None:
    _ensure_existing_dir(sexygpt_dir, "sexyGPT-Uncensored")
    _ensure_existing_dir(turbo_dir, "gpt-3.5-turbo")
    _maybe_clone_llama_cpp(llama_cpp_dir, clone_llama_cpp_if_missing)

    from_src1, from_src2, conflicts = merge_dirs(
        sexygpt_dir, turbo_dir, merged_dir, overwrite_dst=overwrite_merged
    )
    tok_removed, tok_reason = fix_incompatible_tokenizer(merged_dir)
    added_removed, added_reason = fix_incompatible_added_tokens(merged_dir)

    print(f"Merged directory: {merged_dir}")
    print(f"- copied from sexyGPT-Uncensored: {from_src1}")
    print(f"- copied from gpt-3.5-turbo: {from_src2}")
    print(f"- skipped conflicts from secondary: {conflicts}")
    print(f"- tokenizer fix: {'applied' if tok_removed else 'skipped'} ({tok_reason})")
    print(f"- added_tokens fix: {'applied' if added_removed else 'skipped'} ({added_reason})")

    convert_script = _resolve_convert_script(llama_cpp_dir)
    output_gguf.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(convert_script),
        str(merged_dir),
        "--outfile",
        str(output_gguf),
        "--outtype",
        outtype,
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"GGUF created: {output_gguf}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sexygpt-dir", type=Path, default=Path("sexyGPT-Uncensored"))
    parser.add_argument("--turbo-dir", type=Path, default=Path("gpt-3.5-turbo"))
    parser.add_argument(
        "--merged-dir",
        type=Path,
        default=Path("sexygpt-3.5-turbo-uncensored"),
        help="Directory to write merged HF model files",
    )
    parser.add_argument(
        "--output-gguf",
        type=Path,
        default=Path("sexygpt-3.5-turbo-uncensored.gguf"),
        help="Output GGUF path",
    )
    parser.add_argument(
        "--llama-cpp-dir",
        type=Path,
        default=Path("llama.cpp"),
        help="Path containing convert_hf_to_gguf.py",
    )
    parser.add_argument(
        "--outtype",
        default="f16",
        choices=["f32", "f16", "bf16", "q8_0", "tq1_0", "tq2_0", "auto"],
        help="GGUF output type passed to convert_hf_to_gguf.py",
    )
    parser.add_argument(
        "--overwrite-merged",
        action="store_true",
        help="Overwrite merged directory if it already exists",
    )
    parser.add_argument(
        "--clone-llama-cpp-if-missing",
        action="store_true",
        help="Clone llama.cpp automatically when --llama-cpp-dir does not exist",
    )

    args = parser.parse_args()

    build_gguf(
        sexygpt_dir=args.sexygpt_dir,
        turbo_dir=args.turbo_dir,
        merged_dir=args.merged_dir,
        output_gguf=args.output_gguf,
        llama_cpp_dir=args.llama_cpp_dir,
        outtype=args.outtype,
        overwrite_merged=args.overwrite_merged,
        clone_llama_cpp_if_missing=args.clone_llama_cpp_if_missing,
    )


if __name__ == "__main__":
    main()
