from __future__ import annotations

import contextlib
import hashlib
import io
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_scripts import audit_dependencies, local_path, validate_runtime_references


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "scripts").mkdir()
        (self.root / "src").mkdir()
        (self.root / "license.txt").write_text("fixture license")
        self.body = b"$done({});\n"
        self.path = "scripts/test.js"
        (self.root / self.path).write_bytes(self.body)
        self.commit = "a" * 40
        self.digest = hashlib.sha256(self.body).hexdigest()
        self.payload = {"owner/mirror": {
            "source": "https://github.com/owner/mirror", "commit": self.commit,
            "files": {self.path: self.digest}, "license_files": ["license.txt"],
            "provenance": {self.path: {
                "source": "https://github.com/owner/upstream", "commit": "b" * 40,
                "path": "test.js", "sha256": self.digest, "license_file": "license.txt",
            }},
        }}
        self.reference_path = self.root / "src/script.list"
        self.reference_path.write_text(
            f"sample=script-path=https://raw.githubusercontent.com/owner/mirror/{self.commit}/{self.path}\n"
        )

    def audit(self, payload=None, local_only=True):
        with contextlib.redirect_stdout(io.StringIO()):
            return audit_dependencies(self.root, payload or self.payload, local_only)

    def test_local_audit_checks_pinned_snapshot_without_network(self):
        with patch("audit_scripts.fetch", side_effect=AssertionError("network used")), patch(
            "audit_scripts.read_pinned_runtime", return_value=self.body
        ) as pinned:
            self.assertEqual(self.audit(), (1, 0))
            pinned.assert_called_once_with(self.root, self.commit, self.path)

    def test_local_modification_is_detected(self):
        (self.root / self.path).write_bytes(b"changed locally")
        with patch("audit_scripts.read_pinned_runtime", return_value=self.body):
            with self.assertRaisesRegex(ValueError, "hash mismatch for local"):
                self.audit()

    def test_hash_update_without_repinning_is_detected(self):
        updated = b"$done({body: 'updated'});\n"
        (self.root / self.path).write_bytes(updated)
        payload = deepcopy(self.payload)
        payload["owner/mirror"]["files"][self.path] = hashlib.sha256(updated).hexdigest()
        with patch("audit_scripts.read_pinned_runtime", return_value=self.body):
            with self.assertRaisesRegex(ValueError, "hash mismatch for owner/mirror"):
                self.audit(payload)

    def test_remote_audit_still_verifies_runtime_and_upstream(self):
        with patch("audit_scripts.fetch", return_value=self.body) as fetch:
            self.assertEqual(self.audit(local_only=False), (1, 1))
            self.assertEqual(fetch.call_count, 2)

    def test_unlocked_files_and_forbidden_runtime_calls_are_detected(self):
        (self.root / "scripts/unlocked.js").write_bytes(self.body)
        with patch("audit_scripts.read_pinned_runtime", return_value=self.body):
            with self.assertRaisesRegex(ValueError, "inventory"):
                self.audit()
        (self.root / "scripts/unlocked.js").unlink()
        forbidden = b"https://example.workers.dev/init-stream"
        (self.root / self.path).write_bytes(forbidden)
        payload = deepcopy(self.payload)
        payload["owner/mirror"]["files"][self.path] = hashlib.sha256(forbidden).hexdigest()
        with self.assertRaisesRegex(ValueError, "forbidden runtime endpoint"):
            self.audit(payload)

    def test_source_and_generated_references_must_match_lockfile(self):
        self.assertEqual(validate_runtime_references(self.root, self.payload), 1)
        for revision in ("main", "c" * 40):
            self.reference_path.write_text(
                f"sample=script-path=https://raw.githubusercontent.com/owner/mirror/{revision}/{self.path}\n"
            )
            with self.assertRaisesRegex(ValueError, "does not match lockfile"):
                validate_runtime_references(self.root, self.payload)
        self.reference_path.unlink()
        (self.root / "dist").mkdir()
        (self.root / "dist/test.module").write_text(
            f"sample=script-path=https://raw.githubusercontent.com/owner/mirror/{'c' * 40}/{self.path}\n"
        )
        with self.assertRaisesRegex(ValueError, "does not match lockfile"):
            validate_runtime_references(self.root, self.payload)

    def test_paths_cannot_escape_repository(self):
        for relative_path in ("../private.js", "/tmp/private.js"):
            with self.subTest(path=relative_path), self.assertRaisesRegex(ValueError, "inside repository"):
                local_path(self.root, relative_path)


if __name__ == "__main__":
    unittest.main()
