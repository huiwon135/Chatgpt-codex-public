#!/usr/bin/env python3
"""Reliable artifact downloader for large ZIP/GGUF files.

Features:
- retry with exponential backoff
- resume partially downloaded files via HTTP Range
- optional auth token header
"""

from __future__ import annotations

import argparse
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


CHUNK_SIZE = 1024 * 1024  # 1 MiB
CONTENT_RANGE_RE = re.compile(r"^bytes\s+(\d+)-(\d+)/(\d+|\*)$")


def _remote_size(url: str, headers: dict[str, str]) -> int | None:
    req = urllib.request.Request(url, method="HEAD", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            value = response.headers.get("Content-Length")
            return int(value) if value and value.isdigit() else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _parse_content_range_start(value: str | None) -> int | None:
    if not value:
        return None

    matched = CONTENT_RANGE_RE.match(value.strip())
    if not matched:
        return None

    try:
        return int(matched.group(1))
    except ValueError:
        return None


def _download_once(url: str, out: Path, headers: dict[str, str], expected_size: int | None) -> bool:
    """Download once, returning True if completed.

    Handles resume logic safely even when server ignores Range requests.
    """
    current_size = out.stat().st_size if out.exists() else 0
    if expected_size is not None and current_size == expected_size:
        return True
    if expected_size is not None and current_size > expected_size:
        out.unlink()
        current_size = 0

    req_headers = dict(headers)
    requested_resume = current_size > 0
    if requested_resume:
        req_headers["Range"] = f"bytes={current_size}-"

    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        status = getattr(response, "status", response.getcode())
        content_range_start = _parse_content_range_start(response.headers.get("Content-Range"))

        # If we requested resume but server returned full body, start from scratch.
        mode = "ab"
        if requested_resume and status == 200:
            mode = "wb"
        elif requested_resume and status == 206 and content_range_start != current_size:
            mode = "wb"
        elif not requested_resume:
            mode = "wb"

        with out.open(mode) as fp:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                fp.write(chunk)

    final_size = out.stat().st_size
    if expected_size is None:
        # Without a known size, treat non-empty file as success.
        return final_size > 0
    return final_size == expected_size


def download_with_resume(url: str, out: Path, *, token: str | None, retries: int, backoff_sec: float) -> None:
    headers = {"User-Agent": "codex-downloader/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    out.parent.mkdir(parents=True, exist_ok=True)

    expected_size = _remote_size(url, headers)

    for attempt in range(1, retries + 1):
        try:
            done = _download_once(url, out, headers, expected_size)
            if done:
                return
            raise RuntimeError("download incomplete")
        except urllib.error.HTTPError as exc:
            # If file is already complete and server returns 416 on resume,
            # accept existing file when its size matches expectation.
            if exc.code == 416 and expected_size is not None and out.exists() and out.stat().st_size == expected_size:
                return
            if attempt == retries:
                raise RuntimeError(f"download failed after {retries} attempts: {exc}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            if attempt == retries:
                raise RuntimeError(f"download failed after {retries} attempts: {exc}") from exc

        sleep_for = backoff_sec * (2 ** (attempt - 1))
        print(f"Attempt {attempt}/{retries} failed. Retrying in {sleep_for:.1f}s...")
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
