#!/usr/bin/env python3
"""
Download the v86 runtime assets (JS, wasm, BIOS, sample kernel) into web/vendor/v86.
Running this script avoids CORS issues by hosting the files locally.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = REPO_ROOT / "web" / "vendor" / "v86"

ASSETS = {
    "libv86.js": "https://copy.sh/v86/build/libv86.js",
    "v86.wasm": "https://copy.sh/v86/build/v86.wasm",
    "seabios.bin": "https://copy.sh/v86/bios/seabios.bin",
    "vgabios.bin": "https://copy.sh/v86/bios/vgabios.bin",
    "buildroot-bzimage.bin": "https://i.copy.sh/buildroot-bzimage.bin",
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch v86 runtime assets into web/vendor/v86.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they already exist.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def download(url: str, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        logging.info("Using cached %s", destination.name)
        return

    logging.info("Downloading %s -> %s", url, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)
    logging.info("Saved %s (%.1f MB)", destination.name, destination.stat().st_size / 1e6)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    logging.basicConfig(format="[%(levelname)s] %(message)s", level=getattr(logging, args.log_level))

    for name, url in ASSETS.items():
        dest = DEST_DIR / name
        try:
            download(url, dest, args.force)
        except Exception as exc:  # pragma: no cover - network dependent
            logging.error("Failed to download %s: %s", name, exc)
            return 1
    logging.info("All assets downloaded to %s", DEST_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
