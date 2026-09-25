#!/usr/bin/env python3
"""Upload NT bridge desktop assets to trade-receiver for public /desktop/ hosting."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ASSET_SUFFIXES = {".dmg", ".exe", ".zip", ".xml"}


def _multipart(files: list[Path]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for path in files:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'.encode()
        )
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receiver", default=os.environ.get("RECEIVER_API_URL", "").rstrip("/"))
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--secret", default=os.environ.get("INTERNAL_API_SECRET", ""))
    args = parser.parse_args()
    if not args.receiver:
        raise SystemExit("RECEIVER_API_URL / --receiver is required")
    if not args.secret:
        raise SystemExit("INTERNAL_API_SECRET / --secret is required")
    files = sorted(
        path
        for path in args.dir.iterdir()
        if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
        and path.name.startswith("TradeDeskyNinjaTraderReceiver")
    )
    if not files:
        raise SystemExit(f"No TradeDeskyNinjaTraderReceiver assets in {args.dir}")
    print("Uploading:", ", ".join(p.name for p in files))
    payload, content_type = _multipart(files)
    request = Request(
        f"{args.receiver}/v1/internal/desktop/assets",
        data=payload,
        method="POST",
        headers={
            "Content-Type": content_type,
            "X-Internal-Secret": args.secret,
        },
    )
    try:
        with urlopen(request, timeout=300) as response:
            print(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SystemExit(
            f"Upload failed: {exc.code} {exc.read().decode('utf-8', errors='replace')}"
        ) from exc
    except URLError as exc:
        raise SystemExit(f"Upload failed: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
