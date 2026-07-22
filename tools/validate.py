#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

from modulelib import ModuleData, ModuleError, all_profiles, collect, render


BLOCK_ACTIONS = {
    "reject",
    "reject-200",
    "reject-array",
    "reject-dict",
    "reject-img",
}
PINNED_RAW_SCRIPT = re.compile(
    r"^https://raw\.githubusercontent\.com/[^/]+/[^/]+/[0-9a-f]{40}/.+$"
)
HOSTNAME = re.compile(r"^(?:\*\.)?(?:[a-z0-9-]+\.)+[a-z0-9-]+$|^(?:\d{1,3}\.){3}\d{1,3}$")
NEGATIVE_HOSTNAME = re.compile(
    r"^-(?:(?:\*|[a-z0-9-]+\*)\.)?(?:[a-z0-9-]+\.)+[a-z0-9-]+$"
)
BANNED_STABLE_TEXT = (
    "#!author=",
    "#!homepage=",
    "#!icon=",
    "gist.githubusercontent.com",
    "/master/",
    "/main/",
)
HIGH_RISK = re.compile(
    r"(?:login|passport|oauth|payment|wallet|creditcard|bank|alipay|"
    r"weixin110|security\.wechat|versioncheck|upgrade)",
    re.IGNORECASE,
)
SCOPED_UDP_REJECT = re.compile(
    r"^AND,\(\((?:DOMAIN|DOMAIN-SUFFIX),"
    r"(?:[a-z0-9-]+\.)+[a-z0-9-]+\),"
    r"\(PROTOCOL,UDP\)\),(?:REJECT|REJECT-NO-DROP)$"
)
INLINE_RESPONSE_SCRIPT = "script-response-body"


def validate_rule(line: str) -> None:
    if not SCOPED_UDP_REJECT.fullmatch(line):
        raise ModuleError(f"unsupported or unscoped Rule entry: {line}")


def validate_rewrite(line: str) -> None:
    parts = line.split()
    if len(parts) == 2:
        if parts[1] not in BLOCK_ACTIONS:
            raise ModuleError(f"unsupported URL Rewrite action: {line}")
    elif len(parts) == 3 and parts[1] in {"_", "-"}:
        if parts[2].lower() not in BLOCK_ACTIONS:
            raise ModuleError(f"unsupported URL Rewrite action: {line}")
    elif len(parts) == 4 and parts[1:3] == ["url", INLINE_RESPONSE_SCRIPT]:
        script_path = parts[3]
        if script_path.endswith(",append"):
            raise ModuleError(f"inline response Script URL must not use an append suffix: {line}")
        if not PINNED_RAW_SCRIPT.fullmatch(script_path):
            raise ModuleError(f"inline response Script is not pinned to a Git commit: {line}")
    elif len(parts) == 3:
        if parts[2] not in {"302", "307"} or not parts[1].startswith(("http://", "https://", "$")):
            raise ModuleError(f"invalid redirect URL Rewrite: {line}")
    else:
        raise ModuleError(f"invalid URL Rewrite field count: {line}")

    try:
        re.compile(parts[0])
    except re.error as error:
        raise ModuleError(f"invalid URL Rewrite regex {parts[0]!r}: {error}") from error


def parse_script(line: str) -> tuple[str, dict[str, str]]:
    name, payload = line.split("=", 1)
    fields: dict[str, str] = {}
    for item in payload.split(","):
        if "=" not in item:
            raise ModuleError(f"invalid Script option in {name!r}: {item}")
        key, value = item.split("=", 1)
        fields[key.strip()] = value.strip()
    return name.strip(), fields


def validate_script(line: str) -> None:
    name, fields = parse_script(line)
    required = {"type", "pattern", "script-path"}
    missing = required.difference(fields)
    if not name or missing:
        raise ModuleError(f"invalid Script entry {name!r}; missing {sorted(missing)}")
    if fields["type"] not in {"http-request", "http-response"}:
        raise ModuleError(f"unsupported Script type in {name!r}: {fields['type']}")
    try:
        re.compile(fields["pattern"])
    except re.error as error:
        raise ModuleError(f"invalid Script regex in {name!r}: {error}") from error
    if not PINNED_RAW_SCRIPT.fullmatch(fields["script-path"]):
        raise ModuleError(f"Script {name!r} is not pinned to a Git commit")


def validate_hostname(hostname: str) -> None:
    if not HOSTNAME.fullmatch(hostname) and not NEGATIVE_HOSTNAME.fullmatch(hostname):
        raise ModuleError(f"invalid MITM hostname: {hostname}")


def literal_https_hostname(pattern: str) -> str | None:
    marker = "://"
    if marker not in pattern or not pattern.startswith("^https"):
        return None
    host_expression = pattern.split(marker, 1)[1].split("/", 1)[0]
    if not re.fullmatch(r"(?:[A-Za-z0-9-]+\\\.)+[A-Za-z0-9-]+", host_expression):
        return None
    return host_expression.replace(r"\.", ".").lower()


def hostname_is_covered(hostname: str, configured: set[str]) -> bool:
    if hostname in configured:
        return True
    return any(
        not item.startswith("-")
        and item.startswith("*.")
        and hostname.endswith(item[1:])
        and hostname != item[2:]
        for item in configured
    )


def validate_data(data: ModuleData) -> list[str]:
    warnings: list[str] = []
    configured_hostnames = set(data.hostnames)
    for line in data.rules:
        validate_rule(line)
        if HIGH_RISK.search(line):
            raise ModuleError(f"high-risk Rule is not allowed in stable source: {line}")
    for line in data.rewrites:
        validate_rewrite(line)
        pattern = line.split(maxsplit=1)[0]
        if re.search(r"https?[^/]*://(?:\.\*|\.\+|\[\^?/\]+\])", pattern):
            warnings.append(f"broad host regex: {pattern}")
        if HIGH_RISK.search(line):
            raise ModuleError(f"high-risk endpoint is not allowed in stable source: {line}")
        literal_hostname = literal_https_hostname(pattern.replace(r"\/", "/"))
        if literal_hostname and not hostname_is_covered(literal_hostname, configured_hostnames):
            raise ModuleError(f"HTTPS Rewrite hostname missing from MITM: {literal_hostname}")
    for line in data.scripts:
        validate_script(line)
        if HIGH_RISK.search(line):
            raise ModuleError(f"high-risk Script is not allowed in stable source: {line}")
        _, fields = parse_script(line)
        literal_hostname = literal_https_hostname(fields["pattern"])
        if literal_hostname and not hostname_is_covered(literal_hostname, configured_hostnames):
            raise ModuleError(f"HTTPS Script hostname missing from MITM: {literal_hostname}")
    for hostname in data.hostnames:
        validate_hostname(hostname)
        if HIGH_RISK.search(hostname):
            raise ModuleError(f"high-risk MITM hostname is not allowed: {hostname}")
    return warnings


def validate_rendered(path: Path, expected: str) -> None:
    if not path.exists():
        raise ModuleError(f"missing generated module: {path}")
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise ModuleError(f"generated module is stale: {path}")
    if actual.startswith("\ufeff") or "\r" in actual:
        raise ModuleError(f"module must use UTF-8 without BOM and LF newlines: {path}")
    lowered = actual.lower()
    for marker in BANNED_STABLE_TEXT:
        if marker.lower() in lowered:
            raise ModuleError(f"forbidden branding or floating dependency {marker!r} in {path}")


def main() -> int:
    try:
        profiles = all_profiles()
        total_warnings = 0
        for profile in profiles:
            data = collect(profile)
            warnings = validate_data(data)
            total_warnings += len(warnings)
            validate_rendered(profile.output, render(profile))
            print(
                f"ok {profile.output.name}: "
                f"{len(data.rules)} rules, "
                f"{len(data.rewrites)} rewrites, "
                f"{len(data.scripts)} scripts, "
                f"{len(data.hostnames)} hostnames"
            )
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
        if total_warnings:
            print(f"validation completed with {total_warnings} warning(s)", file=sys.stderr)
    except (ModuleError, OSError, ValueError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
