#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from modulelib import ModuleError, Profile, all_profiles, render


def update_profile_dates(
    profiles: list[Profile], requested: list[str], today: str
) -> list[Path]:
    try:
        parsed_today = date.fromisoformat(today)
    except ValueError as error:
        raise ModuleError("update date must use YYYY-MM-DD") from error
    if parsed_today.isoformat() != today:
        raise ModuleError("update date must use YYYY-MM-DD")

    by_name = {profile.path.stem: profile for profile in profiles}
    unknown = set(requested).difference({*by_name, "all"})
    if unknown:
        raise ModuleError(
            "unknown profile for --update-date: " + ", ".join(sorted(unknown))
        )

    selected = set(by_name) if "all" in requested else set(requested)
    changed: list[Path] = []
    for name in sorted(selected):
        path = by_name[name].path
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("updated") == today:
            continue
        payload["updated"] = today
        with path.open("w", encoding="utf-8", newline="\n") as output_file:
            output_file.write(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            )
        changed.append(path)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Shadowrocket modules")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when dist output differs from generated content",
    )
    parser.add_argument(
        "--update-date",
        action="append",
        metavar="PROFILE",
        help="stamp adblock, youtube, or all with today's local date; repeatable",
    )
    args = parser.parse_args()
    if args.check and args.update_date:
        parser.error("--check cannot be combined with --update-date")

    try:
        profiles = all_profiles()
        if not profiles:
            raise ModuleError("no profiles found")

        if args.update_date:
            changed = update_profile_dates(
                profiles,
                args.update_date,
                date.today().isoformat(),
            )
            for path in changed:
                print(f"dated {path}")
            profiles = all_profiles()

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
