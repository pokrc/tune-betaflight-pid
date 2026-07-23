"""Portable local-runtime discovery for the Blackbox analysis scripts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable


def _decoder_names() -> tuple[str, ...]:
    return ("blackbox_decode.exe", "blackbox_decode") if os.name == "nt" else ("blackbox_decode",)


def _usable(path: Path) -> Path | None:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return None
    if not resolved.is_file():
        return None
    if os.name == "nt" or os.access(resolved, os.X_OK):
        return resolved
    return None


def _roots(search_roots: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in search_roots:
        try:
            root = candidate.expanduser().resolve()
        except OSError:
            continue
        if root.is_file():
            root = root.parent
        for _ in range(3):
            if root not in seen:
                seen.add(root)
                result.append(root)
            if root.parent == root:
                break
            root = root.parent
    return result


def find_blackbox_decoder(
    explicit: str | None = None,
    search_roots: Iterable[Path] = (),
) -> tuple[Path | None, str | None]:
    """Find an executable decoder without recursively scanning the filesystem.

    Return its resolved path and a short discovery source. Explicit paths take
    precedence; then use BLACKBOX_DECODE, PATH, conventional install prefixes,
    and a few predictable workspace layouts.
    """
    if explicit:
        resolved = _usable(Path(explicit))
        return resolved, "--decoder" if resolved else None

    configured = os.environ.get("BLACKBOX_DECODE")
    if configured:
        resolved = _usable(Path(configured))
        if resolved:
            return resolved, "BLACKBOX_DECODE"

    for name in _decoder_names():
        located = shutil.which(name)
        if located:
            resolved = _usable(Path(located))
            if resolved:
                return resolved, "PATH"

    for prefix in (Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path.home() / ".local" / "bin"):
        for name in _decoder_names():
            resolved = _usable(prefix / name)
            if resolved:
                return resolved, f"conventional prefix: {prefix}"

    layouts = (
        Path("."),
        Path("obj"),
        Path("blackbox-tools"),
        Path("blackbox-tools") / "obj",
        Path("blackbox-tools-src") / "obj",
        Path("work") / "blackbox-tools" / "obj",
        Path("work") / "blackbox-tools-src" / "obj",
    )
    for root in _roots(search_roots):
        for layout in layouts:
            for name in _decoder_names():
                resolved = _usable(root / layout / name)
                if resolved:
                    return resolved, f"workspace: {root / layout}"
    return None, None
