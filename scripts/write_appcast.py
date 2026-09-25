#!/usr/bin/env python3
"""Write TradeDesky NinjaTrader Receiver appcast XML into a release directory."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    release: Path = args.release
    version: str = args.version

    setup = release / f"TradeDeskyNinjaTraderReceiver-{version}-setup.exe"
    zip_path = release / f"TradeDeskyNinjaTraderReceiver-{version}-win.zip"
    setup_len = setup.stat().st_size if setup.is_file() else 0
    zip_len = zip_path.stat().st_size if zip_path.is_file() else 0
    setup_url = (
        "https://trade-receiver.chapilabs.com/desktop/"
        f"TradeDeskyNinjaTraderReceiver-{version}-setup.exe"
    )
    zip_url = (
        "https://trade-receiver.chapilabs.com/desktop/"
        f"TradeDeskyNinjaTraderReceiver-{version}-win.zip"
    )
    pub_date = format_datetime(datetime.now(timezone.utc))
    desc = (
        "System-tray webhook receiver for NinjaTrader. "
        f"Portable zip: {zip_url} ({zip_len} bytes)."
    )
    appcast = f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <title>Trade Desky NinjaTrader Receiver</title>
    <language>en</language>
    <item>
      <title>Version {version}</title>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{setup_url}" sparkle:version="{version}" length="{setup_len}" type="application/octet-stream" />
      <sparkle:version>{version}</sparkle:version>
      <description><![CDATA[{desc}]]></description>
    </item>
  </channel>
</rss>
"""
    versioned = release / f"TradeDeskyNinjaTraderReceiver-{version}-appcast.xml"
    stable = release / "TradeDeskyNinjaTraderReceiver-appcast.xml"
    versioned.write_text(appcast, encoding="utf-8")
    stable.write_text(appcast, encoding="utf-8")
    print(f"Wrote {versioned.name} and {stable.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
