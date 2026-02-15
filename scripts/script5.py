#!/usr/bin/env python3
"""
generate_bat_from_csv.py

Read data/element_coverage_plan_joyo.csv and produce word_clouds_kanjivg.bat.

Usage:
    python generate_bat_from_csv.py \
        --csv data/element_coverage_plan_joyo.csv \
        --out word_clouds_kanjivg.bat \
        --script "scripts/word_cloud.py" \
        --image-dir word_clouds \
        --text-dir word_clouds

The produced .bat will include:
  @echo off
  chcp 65001 >nul

  python "scripts/word_cloud.py" --element "口" --top all --out-dir word_clouds --image-out-dir word_clouds --include-sources
"""
from __future__ import annotations
import csv
import argparse
import os
from typing import Iterable, List

DEFAULT_CSV = "data/element_coverage_plan_joyo.csv"
DEFAULT_OUT = "word_clouds_kanjivg.bat"
DEFAULT_SCRIPT = "scripts/word_cloud_v2.py"
DEFAULT_IMAGE_DIR = "word_clouds"
DEFAULT_TEXT_DIR = "word_clouds"

def read_elements_from_csv(path: str, column_name: str = "element") -> List[str]:
    elems: List[str] = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row:
                continue
            val = row.get(column_name)
            if val is None:
                # fallback: try first column if header missing
                first = next(iter(row.values()), "")
                val = first
            if val is None:
                continue
            val = val.strip()
            if not val:
                continue
            elems.append(val)
    return elems

def make_command(script: str, element: str, top: str = "all",
                 out_dir: str = DEFAULT_TEXT_DIR, image_out_dir: str = DEFAULT_IMAGE_DIR,
                 include_sources: bool = True) -> str:
    """
    Build a single command line for the batch file.
    - script: path to word_cloud.py (will be quoted)
    - element: element character or key (will be quoted)
    """
    parts = []
    # Use plain 'python' so the user's PATH determines which python runs.
    parts.append("python")
    # Quote script path in case it contains spaces
    parts.append(f'"{script}"')
    # element argument quoted to preserve unicode and spaces
    parts.append(f'--element "{element}"')
    parts.append(f'--top {top}')
    # text output directory (optional; mirrors --image-out-dir semantics)
    parts.append(f'--out-dir {out_dir}')
    parts.append(f'--image-out-dir {image_out_dir}')
    if include_sources:
        parts.append("--include-sources")
    return " ".join(parts)

def write_bat(path: str, commands: Iterable[str]) -> None:
    # Write with CRLF line endings for Windows compatibility
    header = ["@echo off", "chcp 65001 >nul", ""]
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        for line in header:
            fh.write(line + "\r\n")
        for cmd in commands:
            fh.write(cmd + "\r\n")
    # Make file executable on POSIX if needed (no effect on Windows)
    try:
        os.chmod(path, 0o644)
    except Exception:
        pass

def main():
    p = argparse.ArgumentParser(description="Generate a .bat to run word_cloud.py for each element in a CSV.")
    p.add_argument("--csv", default=DEFAULT_CSV, help="Input CSV (expects 'element' column).")
    p.add_argument("--out", default=DEFAULT_OUT, help="Output .bat path.")
    p.add_argument("--script", default=DEFAULT_SCRIPT, help="Path to word_cloud.py to call.")
    p.add_argument("--image-dir", default=DEFAULT_IMAGE_DIR, help="Directory to pass to --image-out-dir.")
    p.add_argument("--text-dir", default=DEFAULT_TEXT_DIR, help="Directory to pass to --out-dir.")
    p.add_argument("--top", default="all", help="Top argument to pass (e.g., 'all' or integer).")
    p.add_argument("--include-sources", action="store_true", help="Add --include-sources to each command.")
    args = p.parse_args()

    elems = read_elements_from_csv(args.csv, column_name="element")
    if not elems:
        print(f"No elements found in {args.csv}. Exiting.")
        return

    commands = []
    for e in elems:
        # skip header-like values accidentally read
        if e.lower() in ("element", "elements", ""):
            continue
        cmd = make_command(
            script=args.script,
            element=e,
            top=args.top,
            out_dir=args.text_dir,
            image_out_dir=args.image_dir,
            include_sources=args.include_sources
        )
        commands.append(cmd)

    write_bat(args.out, commands)
    print(f"Wrote {len(commands)} commands to {args.out}")

if __name__ == "__main__":
    main()
