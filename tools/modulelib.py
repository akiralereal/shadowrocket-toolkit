from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
PROFILE_ROOT = ROOT / "profiles"


class ModuleError(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    path: Path
    name: str
    description: str
    components: tuple[str, ...]
    output: Path
    mitm_h2: bool


@dataclass(frozen=True)
class ModuleData:
    rules: tuple[str, ...]
    rewrites: tuple[str, ...]
    scripts: tuple[str, ...]
    hostnames: tuple[str, ...]


def read_entries(path: Path) -> list[str]:
    if not path.exists():
        return []

    entries: list[str] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if raw != raw.rstrip():
            raise ModuleError(f"{path}:{line_number}: trailing whitespace")
        entries.append(line)
    return entries


def load_profile(path: Path) -> Profile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"name", "description", "components", "output"}
    missing = required.difference(payload)
    if missing:
        raise ModuleError(f"{path}: missing keys: {', '.join(sorted(missing))}")

    output = (ROOT / payload["output"]).resolve()
    if ROOT not in output.parents:
        raise ModuleError(f"{path}: output must stay inside repository")

    components = tuple(payload["components"])
    if not components or any(not isinstance(item, str) for item in components):
        raise ModuleError(f"{path}: components must be a non-empty string list")

    mitm_h2 = payload.get("mitm_h2", False)
    if not isinstance(mitm_h2, bool):
        raise ModuleError(f"{path}: mitm_h2 must be a boolean")

    return Profile(
        path=path,
        name=payload["name"],
        description=payload["description"],
        components=components,
        output=output,
        mitm_h2=mitm_h2,
    )


def all_profiles() -> list[Profile]:
    return [load_profile(path) for path in sorted(PROFILE_ROOT.glob("*.json"))]


def _merge_rewrites(lines: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    by_pattern: dict[str, str] = {}
    for line in lines:
        pattern = line.split(maxsplit=1)[0]
        previous = by_pattern.get(pattern)
        if previous is None:
            by_pattern[pattern] = line
            merged.append(line)
        elif previous != line:
            raise ModuleError(
                "conflicting URL Rewrite actions for pattern:\n"
                f"  {previous}\n"
                f"  {line}"
            )
    return tuple(merged)


def _merge_rules(lines: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    by_match: dict[str, str] = {}
    for line in lines:
        match, separator, _ = line.rpartition(",")
        if not separator:
            raise ModuleError(f"invalid Rule entry: {line}")
        previous = by_match.get(match)
        if previous is None:
            by_match[match] = line
            merged.append(line)
        elif previous != line:
            raise ModuleError(
                "conflicting Rule actions for matcher:\n"
                f"  {previous}\n"
                f"  {line}"
            )
    return tuple(merged)


def _merge_scripts(lines: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    by_name: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            raise ModuleError(f"invalid Script entry: {line}")
        name = line.split("=", 1)[0].strip()
        previous = by_name.get(name)
        if previous is None:
            by_name[name] = line
            merged.append(line)
        elif previous != line:
            raise ModuleError(
                f"conflicting Script entries named {name!r}:\n"
                f"  {previous}\n"
                f"  {line}"
            )
    return tuple(merged)


def _merge_hostnames(lines: Iterable[str]) -> tuple[str, ...]:
    unique: dict[str, str] = {}
    for line in lines:
        hostname = line.strip().lower()
        unique.setdefault(hostname, hostname)
    return tuple(sorted(unique.values(), key=lambda item: (not item.startswith("-"), item)))


def collect(profile: Profile) -> ModuleData:
    rules: list[str] = []
    rewrites: list[str] = []
    scripts: list[str] = []
    hostnames: list[str] = []

    for component in profile.components:
        component_path = (SOURCE_ROOT / component).resolve()
        if SOURCE_ROOT not in component_path.parents:
            raise ModuleError(f"{profile.path}: invalid component path {component!r}")
        if not component_path.is_dir():
            raise ModuleError(f"{profile.path}: component not found: {component}")

        rules.extend(read_entries(component_path / "rule.list"))
        rewrites.extend(read_entries(component_path / "url-rewrite.list"))
        scripts.extend(read_entries(component_path / "script.list"))
        hostnames.extend(read_entries(component_path / "mitm.list"))

    return ModuleData(
        rules=_merge_rules(rules),
        rewrites=_merge_rewrites(rewrites),
        scripts=_merge_scripts(scripts),
        hostnames=_merge_hostnames(hostnames),
    )


def render(profile: Profile) -> str:
    data = collect(profile)
    lines = [f"#!name={profile.name}", f"#!desc={profile.description}"]

    if data.rules:
        lines.extend(("", "[Rule]", *data.rules))
    if data.rewrites:
        lines.extend(("", "[URL Rewrite]", *data.rewrites))
    if data.scripts:
        lines.extend(("", "[Script]", *data.scripts))
    if profile.mitm_h2 and not data.hostnames:
        raise ModuleError(f"{profile.path}: mitm_h2 requires at least one MITM hostname")
    if data.hostnames:
        lines.extend(("", "[MITM]"))
        if profile.mitm_h2:
            lines.append("h2 = true")
        lines.append(f"hostname = %APPEND% {','.join(data.hostnames)}")

    return "\n".join(lines) + "\n"
