#!/usr/bin/env python3
"""Reliable artifact downloader for large ZIP/GGUF files.

Features:
- retry with exponential backoff
- resume partially downloaded files via HTTP Range
- optional auth token header
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path


CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _remote_size(url: str, headers: dict[str, str]) -> int | None:
    req = urllib.request.Request(url, method="HEAD", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            value = response.headers.get("Content-Length")
            return int(value) if value and value.isdigit() else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def download_with_resume(url: str, out: Path, *, token: str | None, retries: int, backoff_sec: float) -> None:
    headers = {"User-Agent": "codex-downloader/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    out.parent.mkdir(parents=True, exist_ok=True)

    expected_size = _remote_size(url, headers)

    for attempt in range(1, retries + 1):
        current_size = out.stat().st_size if out.exists() else 0
        req_headers = dict(headers)
        mode = "wb"
        if current_size > 0:
            req_headers["Range"] = f"bytes={current_size}-"
            mode = "ab"

        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as response, out.open(mode) as fp:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fp.write(chunk)

            final_size = out.stat().st_size
            if expected_size is None or final_size >= expected_size:
                return
            raise RuntimeError(
                f"download incomplete: expected {expected_size} bytes, got {final_size} bytes"
            )
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            if attempt == retries:
                raise RuntimeError(f"download failed after {retries} attempts: {exc}") from exc
            sleep_for = backoff_sec * (2 ** (attempt - 1))
            print(f"Attempt {attempt}/{retries} failed: {exc}. Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Direct download URL (.zip, .gguf, etc.)")
    parser.add_argument("out", type=Path, help="Output file path")
    parser.add_argument("--token", default=None, help="Optional Bearer token")
    parser.add_argument("--retries", type=int, default=5, help="Max retry attempts")
    parser.add_argument("--backoff-sec", type=float, default=1.5, help="Initial backoff seconds")
    args = parser.parse_args()

    download_with_resume(
        args.url,
        args.out,
        token=args.token,
        retries=max(1, args.retries),
        backoff_sec=max(0.1, args.backoff_sec),
    )
    print(f"Downloaded successfully: {args.out}")


if __name__ == "__main__":
    main()
