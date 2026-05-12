#!/usr/bin/env python3
"""Invert one or more channels of tangent-space normalmap PNGs in-place.

Common use-cases
----------------
  Alpha (heightmap) inverted  -- parallax depth looks wrong; bumps sunken
    python invert_z.py -d textures/quake --channel a

  Y (green) inverted  -- lighting/shading on wrong side (OpenGL vs DirectX)
    python invert_z.py -d textures/quake --channel g

  Multiple channels at once
    python invert_z.py -d textures/quake --channel ga

  Default channel is 'a' (alpha/heightmap) -- the most common fix.

Usage:
  python invert_z.py  FILE [FILE ...]           # explicit files
  python invert_z.py  -d DIRECTORY              # all *_norm.png under dir
  python invert_z.py  -d DIRECTORY --filter rock
  python invert_z.py  -d DIRECTORY --dry-run    # preview only
  python invert_z.py  -d DIRECTORY --channel rgb  # invert specific channels
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

CHANNEL_INDEX = {"r": 0, "g": 1, "b": 2, "a": 3}


def invert_channels(path: Path, channels: list[int], *, dry_run: bool = False) -> bool:
    """Invert the given channel indices of a normalmap PNG. Returns True on success."""
    try:
        with Image.open(path) as img:
            img.load()
            arr = np.array(img.convert("RGBA"))
    except Exception as exc:
        print(f"  ! load failed {path.name}: {exc}", file=sys.stderr)
        return False

    for ch in channels:
        arr[:, :, ch] = 255 - arr[:, :, ch]

    if dry_run:
        print(f"  (dry) {path}")
        return True

    try:
        Image.fromarray(arr, mode="RGBA").save(path, optimize=True)
        print(f"  + {path}")
        return True
    except Exception as exc:
        print(f"  ! save failed {path.name}: {exc}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument("-d", "--directory", type=Path,
                       help="Recursively process all *_norm.png files under this directory.")
    group.add_argument("files", nargs="*", type=Path,
                       help="Explicit normalmap PNG file(s) to process.")
    ap.add_argument("--channel", metavar="CHANNELS", default="a",
                    help="Channel(s) to invert: any combination of r/g/b/a (default: a).")
    ap.add_argument("--filter", metavar="SUBSTR",
                    help="Only process files whose basename contains SUBSTR (case-insensitive).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be changed without writing anything.")
    args = ap.parse_args()

    channel_str = args.channel.lower()
    unknown = set(channel_str) - CHANNEL_INDEX.keys()
    if unknown:
        print(f"Unknown channel(s): {''.join(sorted(unknown))}  (valid: r g b a)",
              file=sys.stderr)
        return 2
    channels = [CHANNEL_INDEX[c] for c in channel_str]

    if args.directory:
        if not args.directory.is_dir():
            print(f"Not a directory: {args.directory}", file=sys.stderr)
            return 2
        targets = sorted(args.directory.rglob("*_norm.png"))
    elif args.files:
        targets = list(args.files)
    else:
        ap.print_help()
        return 2

    if args.filter:
        needle = args.filter.lower()
        targets = [p for p in targets if needle in p.name.lower()]

    if not targets:
        print("No matching files found.")
        return 0

    ch_names = "/".join(c.upper() for c in channel_str)
    print(f"{'Dry run: ' if args.dry_run else ''}Inverting {ch_names} on "
          f"{len(targets)} file(s)...")

    ok = 0
    errors = 0
    for path in targets:
        if invert_channels(path, channels, dry_run=args.dry_run):
            ok += 1
        else:
            errors += 1

    suffix = " (dry run)" if args.dry_run else ""
    print(f"Done: {ok} processed, {errors} errors{suffix}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
