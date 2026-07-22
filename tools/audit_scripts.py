#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCKFILE = ROOT / "third_party" / "scripts.json"
BANNED_RUNTIME_ENDPOINTS = (b".workers.dev", b"init-stream")


def validate_commit(label: str, commit: str) -> None:
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError(f"invalid commit for {label}: {commit}")


def repository_from_source(label: str, source: str) -> str:
    normalized = source.rstrip("/")
    if not normalized.startswith("https://github.com/"):
        raise ValueError(f"unsupported source for {label}: {source}")
    return normalized.removeprefix("https://github.com/")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "shadowrocket-rule-audit"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def verify_hash(label: str, body: bytes, expected_hash: str) -> None:
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


def main() -> int:
    try:
        payload = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        runtime_checked = 0
        upstream_checked = 0
        for dependency, record in sorted(payload.items()):
            repository = repository_from_source(dependency, record["source"])
            commit = record["commit"]
            validate_commit(dependency, commit)
            provenance = record["provenance"]
            if set(provenance) != set(record["files"]):
                raise ValueError(f"provenance does not match runtime files for {dependency}")

            for license_file in record["license_files"]:
                if not (ROOT / license_file).is_file():
                    raise ValueError(f"missing license file: {license_file}")

            for relative_path, expected_hash in sorted(record["files"].items()):
                url = f"https://raw.githubusercontent.com/{repository}/{commit}/{relative_path}"
                label = f"{dependency}/{relative_path}"
                body = fetch(url)
                verify_hash(label, body, expected_hash)
                verify_runtime_policy(label, body)
                local_path = ROOT / relative_path
                if not local_path.is_file():
                    raise ValueError(f"missing mirrored runtime: {relative_path}")
                verify_hash(f"local {relative_path}", local_path.read_bytes(), expected_hash)
                runtime_checked += 1
                print(f"ok runtime {label}")

            for relative_path, origin in sorted(provenance.items()):
                origin_repository = repository_from_source(relative_path, origin["source"])
                origin_commit = origin["commit"]
                validate_commit(relative_path, origin_commit)
                license_file = origin["license_file"]
                if not (ROOT / license_file).is_file():
                    raise ValueError(f"missing license file: {license_file}")
                origin_url = (
                    f"https://raw.githubusercontent.com/{origin_repository}/"
                    f"{origin_commit}/{origin['path']}"
                )
                origin_body = fetch(origin_url)
                verify_hash(f"upstream {relative_path}", origin_body, origin["sha256"])
                verify_runtime_policy(f"upstream {relative_path}", origin_body)
                upstream_checked += 1
                print(f"ok upstream {relative_path}")
        print(
            f"verified {runtime_checked} mirrored runtime(s) and "
            f"{upstream_checked} pinned upstream source(s)"
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as error:
        print(f"script audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
