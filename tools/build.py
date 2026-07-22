#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from modulelib import ModuleError, all_profiles, render


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Shadowrocket modules")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when dist output differs from generated content",
    )
    args = parser.parse_args()

    try:
        profiles = all_profiles()
        if not profiles:
            raise ModuleError("no profiles found")

        stale: list[str] = []
        for profile in profiles:
            content = render(profile)
            if args.check:
                if not profile.output.exists() or profile.output.read_text(encoding="utf-8") != content:
                    stale.append(str(profile.output.relative_to(profile.output.parents[1])))
                continue

            profile.output.parent.mkdir(parents=True, exist_ok=True)
            with profile.output.open("w", encoding="utf-8", newline="\n") as output_file:
                output_file.write(content)
            print(f"built {profile.output}")

        if stale:
            print("stale generated files:", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
    except (ModuleError, OSError, ValueError) as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
