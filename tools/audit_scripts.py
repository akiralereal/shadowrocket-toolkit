#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from modulelib import ModuleError, read_entries


ROOT = Path(__file__).resolve().parents[1]
LOCKFILE = ROOT / "third_party" / "scripts.json"
BANNED_RUNTIME_ENDPOINTS = (b".workers.dev", b"init-stream")


def validate_commit(label: str, commit: str) -> None:
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"invalid commit for {label}: {commit}")


def repository_from_source(label: str, source: str) -> str:
    normalized = source.rstrip("/")
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", normalized):
        raise ValueError(f"unsupported source for {label}: {source}")
    return normalized.removeprefix("https://github.com/")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "shadowrocket-rule-audit"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def verify_hash(label: str, body: bytes, expected_hash: str) -> None:
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError(f"invalid SHA-256 for {label}")
    actual_hash = hashlib.sha256(body).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(
            f"hash mismatch for {label}: expected {expected_hash}, got {actual_hash}"
        )


def verify_runtime_policy(label: str, body: bytes) -> None:
    lowered_body = body.lower()
    for endpoint in BANNED_RUNTIME_ENDPOINTS:
        if endpoint in lowered_body:
            raise ValueError(
                f"forbidden runtime endpoint in {label}: {endpoint.decode('ascii')}"
            )


def local_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if Path(relative_path).is_absolute() or root.resolve() not in path.parents:
        raise ValueError(f"path must stay inside repository: {relative_path}")
    return path


def read_pinned_runtime(root: Path, commit: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            f"pinned runtime unavailable locally: {commit}:{relative_path}; "
            "fetch repository history before using --local-only"
        )
    return result.stdout


def validate_runtime_references(root: Path, payload: dict) -> int:
    reference = re.compile(
        r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/"
        r"([^/]+)/([^\s,]+)"
    )
    checked = 0
    paths = sorted((root / "src").glob("**/*.list")) + sorted((root / "dist").glob("*.module"))
    for path in paths:
        for line in read_entries(path):
            for match in reference.finditer(line):
                dependency, commit, relative_path = match.groups()
                record = payload.get(dependency)
                if (
                    record is None
                    or commit != record["commit"]
                    or relative_path not in record["files"]
                ):
                    raise ValueError(f"runtime reference does not match lockfile in {path}: {match.group()}")
                checked += 1
    return checked


def audit_dependencies(root: Path, payload: dict, local_only: bool = False) -> tuple[int, int]:
    runtime_checked = 0
    upstream_checked = 0
    declared_files: set[str] = set()
    for dependency, record in sorted(payload.items()):
        repository = repository_from_source(dependency, record["source"])
        commit = record["commit"]
        validate_commit(dependency, commit)
        provenance = record["provenance"]
        if set(provenance) != set(record["files"]):
            raise ValueError(f"provenance does not match runtime files for {dependency}")

        if repository != dependency:
            raise ValueError(f"runtime source does not match dependency: {dependency}")

        for license_file in record["license_files"]:
            if not local_path(root, license_file).is_file():
                raise ValueError(f"missing license file: {license_file}")

        for relative_path, expected_hash in sorted(record["files"].items()):
            url = f"https://raw.githubusercontent.com/{repository}/{commit}/{relative_path}"
            label = f"{dependency}/{relative_path}"
            mirrored_path = local_path(root, relative_path)
            if not mirrored_path.is_file():
                raise ValueError(f"missing mirrored runtime: {relative_path}")
            local_body = mirrored_path.read_bytes()
            verify_hash(f"local {relative_path}", local_body, expected_hash)
            verify_runtime_policy(f"local {relative_path}", local_body)
            body = (
                read_pinned_runtime(root, commit, relative_path)
                if local_only else fetch(url)
            )
            verify_hash(label, body, expected_hash)
            verify_runtime_policy(label, body)
            declared_files.add(relative_path)
            runtime_checked += 1
            print(f"ok runtime {label}")

        for relative_path, origin in sorted(provenance.items()):
            origin_repository = repository_from_source(relative_path, origin["source"])
            origin_commit = origin["commit"]
            validate_commit(relative_path, origin_commit)
            license_file = origin["license_file"]
            if not local_path(root, license_file).is_file():
                raise ValueError(f"missing license file: {license_file}")
            if not re.fullmatch(r"[0-9a-f]{64}", origin["sha256"]):
                raise ValueError(f"invalid upstream SHA-256: {relative_path}")
            if local_only:
                continue
            origin_url = (
                f"https://raw.githubusercontent.com/{origin_repository}/"
                f"{origin_commit}/{origin['path']}"
            )
            origin_body = fetch(origin_url)
            verify_hash(f"upstream {relative_path}", origin_body, origin["sha256"])
            verify_runtime_policy(f"upstream {relative_path}", origin_body)
            upstream_checked += 1
            print(f"ok upstream {relative_path}")
    actual_files = {str(path.relative_to(root)) for path in (root / "scripts").glob("*.js")}
    if actual_files != declared_files:
        raise ValueError("runtime files do not match lockfile inventory")
    validate_runtime_references(root, payload)
    return runtime_checked, upstream_checked


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit mirrored runtime scripts")
    parser.add_argument(
        "--local-only", action="store_true",
        help="verify local files, references and pinned Git snapshots without network access",
    )
    args = parser.parse_args()
    try:
        payload = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        runtime_checked, upstream_checked = audit_dependencies(ROOT, payload, args.local_only)
        print(f"verified {runtime_checked} mirrored runtime(s) and {upstream_checked} pinned upstream source(s)")
    except (OSError, ValueError, KeyError, ModuleError, urllib.error.URLError) as error:
        print(f"script audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
