#!/usr/bin/env python3
"""Report whether this host can analyze a Betaflight .bbl file locally."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

from runtime import find_blackbox_decoder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decoder", help="Optional path to blackbox_decode")
    parser.add_argument("--search-root", action="append", default=[], help="Extra directory to inspect for a local decoder")
    parser.add_argument("--require-ready", action="store_true", help="Exit nonzero unless NumPy and blackbox_decode are available")
    args = parser.parse_args()

    try:
        numpy_version = importlib.metadata.version("numpy")
    except importlib.metadata.PackageNotFoundError:
        numpy_version = None

    roots = [Path.cwd(), *(Path(item).expanduser() for item in args.search_root)]
    decoder, source = find_blackbox_decoder(args.decoder, roots)
    actions: list[str] = []
    if numpy_version is None:
        actions.append("Install the bundled dependency with: python -m pip install -r requirements.txt")
    if decoder is None:
        actions.append("Install or build Blackbox Tools, then pass --decoder /absolute/path/to/blackbox_decode or set BLACKBOX_DECODE.")

    payload = {
        "status": "ready" if not actions else "action_required",
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "numpy": {"available": numpy_version is not None, "version": numpy_version},
        "blackbox_decode": {"available": decoder is not None, "path": str(decoder) if decoder else None, "discovery": source},
        "next_actions": actions,
    }
    print(json.dumps(payload, indent=2))
    if args.require_ready and actions:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
