"""Export docs/data/*.json for the web app from existing pipeline outputs (read-only; ~10 s).

Usage:  python scripts/export_site.py [--dry-run]
"""
from __future__ import annotations

import argparse

from gnm.export.build_site_data import FILES, SITE, build_all, dumps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="build and report sizes without writing")
    args = ap.parse_args()
    data = build_all(write=not args.dry_run)
    total = 0
    for name in FILES:
        n = len(dumps(data[name]).encode())
        total += n
        print(f"{name:16s} {n / 1024:8.1f} KB")
    print(f"{'total':16s} {total / 1024:8.1f} KB  -> {SITE}{' (dry run, nothing written)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
