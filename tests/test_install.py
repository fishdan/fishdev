"""Offline fixtures for install.sh: verified staging, fail-closed behavior, and pinned tools."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "install.sh"
BASH = shutil.which("bash")
CURL = shutil.which("curl")

STUB_UV = """#!/usr/bin/env bash
echo "uv $*" >> "$STUB_LOG"
case "$1 $2" in
  "--version "*) echo "uv ${STUB_UV_VERSION:-0.13.7} (fixture)" ;;
  "tool list") [ -n "${STUB_SPECIFY_VERSION:-}" ] && printf 'specify-cli v%s\\n- specify\\n' "$STUB_SPECIFY_VERSION" ;;
  "tool dir") echo "$STUB_BIN" ;;
  "tool install") ;;
  *) exit 3 ;;
esac
exit 0
"""

STUB_SPECIFY = """#!/usr/bin/env bash
echo "specify $*" >> "$STUB_LOG"
if [ "$1" = init ]; then mkdir -p .specify/memory .config/ai/commands; fi
"""


@unittest.skipUnless(BASH and CURL, "install.sh tests need bash and curl")
class InstallerFixture(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.base = Path(workspace.name)
        self.source = self.base / "source"
        self.target = self.base / "target"
        self.bin = self.base / "bin"
        self.home = self.base / "home"
        for folder in (self.target, self.bin, self.home):
            folder.mkdir()
        manifest = json.loads((REPO / ".config/ai/release-manifest.json").read_text(encoding="utf-8"))
        self.shipped = [entry["path"] for entry in manifest["files"]]
        for path in self.shipped:
            (self.source / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / path, self.source / path)
        self.stub("uv", STUB_UV)
        self.stub("specify", STUB_SPECIFY)
        self.log = self.base / "stub.log"
        self.log.touch()
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.home),
                    "STUB_LOG": str(self.log), "STUB_BIN": str(self.bin), "STUB_SPECIFY_VERSION": "1.3.3",
                    "FISHDEV_SOURCE": self.source.as_uri()}

    def stub(self, name, text, folder=None):
        path = (folder or self.bin) / name
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)
        return path

    def run_installer(self, **env):
        return subprocess.run([BASH, str(INSTALLER)], cwd=self.target, env={**self.env, **env},
                              text=True, capture_output=True, check=False)

    def run_function(self, script, **env):
        command = f'FISHDEV_INSTALL_LIBRARY=1; source "{INSTALLER}"; {script}'
        return subprocess.run([BASH, "-c", command], cwd=self.target, env={**self.env, **env},
                              text=True, capture_output=True, check=False)

    def snapshot(self):
        return {path.relative_to(self.target).as_posix(): path.read_bytes()
                for path in sorted(self.target.rglob("*")) if path.is_file()}

    def assert_failed_cleanly(self, result, *messages):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for message in messages:
            self.assertIn(message, result.stderr)
        self.assertEqual(self.snapshot(), {})
        self.assertNotIn("tool install", self.log.read_text())


class VerifiedInstallTests(InstallerFixture):
    def test_correct_release_installs_every_verified_file(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in self.shipped:
            self.assertEqual((self.target / path).read_bytes(), (REPO / path).read_bytes(), path)
        for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".config/ai/progress.ai",
                     ".config/ai/handoff.ai", ".config/ai/repo.ai", ".config/ai/verification.json",
                     ".config/ai/rules.json", ".specify/memory/constitution.md"):
            self.assertTrue((self.target / name).is_file(), name)
        self.assertIn(".config/ai/reports/", (self.target / ".gitignore").read_text())
        log = self.log.read_text()
        self.assertIn("specify init . --here --force --ignore-agent-tools --script sh --integration generic", log)
        self.assertNotIn("tool install", log)
        self.assertIn("Using existing specify-cli 1.3.3", result.stdout)

    def test_single_byte_change_stops_before_writing(self):
        target = self.source / "start.ai"
        data = bytearray(target.read_bytes())
        data[0] ^= 1
        target.write_bytes(bytes(data))
        expected = hashlib.sha256((REPO / "start.ai").read_bytes()).hexdigest()
        self.assert_failed_cleanly(self.run_installer(), "start.ai", expected, "digest mismatch")

    def test_missing_file_stops_before_writing(self):
        (self.source / "docs/verification-and-learning.md").unlink()
        self.assert_failed_cleanly(self.run_installer(), "docs/verification-and-learning.md")

    def test_truncated_transfer_stops_before_writing(self):
        path = self.source / ".config/ai/tools/fishdev.py"
        path.write_bytes(path.read_bytes()[:100])
        self.assert_failed_cleanly(self.run_installer(), ".config/ai/tools/fishdev.py", "digest mismatch")

    def test_missing_hash_tool_stops_before_downloading(self):
        restricted = self.base / "restricted"
        restricted.mkdir()
        for tool in ("curl", "mktemp", "mkdir", "rm", "cp", "cat", "grep", "touch", "sed", "dirname"):
            found = shutil.which(tool)
            if found:
                os.symlink(found, restricted / tool)
        result = self.run_installer(PATH=f"{self.bin}:{restricted}")
        self.assert_failed_cleanly(result, "sha256sum", "shasum")

    def test_existing_installation_is_refused(self):
        (self.target / "start.ai").write_text("local edits\n")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.snapshot(), {"start.ai": b"local edits\n"})

    def test_plain_http_source_is_refused(self):
        result = self.run_installer(FISHDEV_SOURCE="http://127.0.0.1:9/fishdev")
        self.assert_failed_cleanly(result, "start.ai")


class PinnedToolTests(InstallerFixture):
    def artifact(self, name, text):
        path = self.base / "artifacts" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path.as_uri(), hashlib.sha256(path.read_bytes()).hexdigest()

    def test_missing_uv_runs_only_a_verified_installer(self):
        (self.bin / "uv").unlink()
        installer = f'mkdir -p "$HOME/.local/bin"; cp "{self.base}/uv-stub" "$HOME/.local/bin/uv"\n'
        self.stub("uv-stub", STUB_UV, self.base)
        url, sha = self.artifact("uv-installer.sh", installer)
        ok = self.run_function(f"UV_INSTALLER_URL={url}; UV_INSTALLER_SHA256={sha}; ensure_uv && command -v uv")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn(str(self.home / ".local/bin/uv"), ok.stdout)

        (self.home / ".local/bin/uv").unlink()
        bad = self.run_function(f"UV_INSTALLER_URL={url}; UV_INSTALLER_SHA256={'0' * 64}; ensure_uv")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("digest mismatch", bad.stderr)
        self.assertFalse((self.home / ".local/bin/uv").exists())

    def test_old_uv_is_reported_not_used(self):
        result = self.run_function("ensure_uv", STUB_UV_VERSION="0.3.5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uv 0.3.5 is older than 0.4.0", result.stderr)

    def test_existing_uv_is_respected(self):
        result = self.run_function("ensure_uv", STUB_UV_VERSION="0.20.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Using existing uv 0.20.1", result.stdout)

    def test_other_speckit_version_is_replaced_by_verified_wheel(self):
        url, sha = self.artifact("specify_cli-1.3.3-py3-none-any.whl", "fixture wheel")
        result = self.run_function(f"SPECIFY_WHEEL_URL={url}; SPECIFY_WHEEL_SHA256={sha}; install_speckit",
                                   STUB_SPECIFY_VERSION="1.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Replacing specify-cli 1.2.0 with pinned 1.3.3", result.stdout)
        self.assertRegex(self.log.read_text(), r"uv tool install --force .*/specify_cli-1\.3\.3-py3-none-any\.whl")

        tampered = self.run_function(f"SPECIFY_WHEEL_URL={url}; SPECIFY_WHEEL_SHA256={'0' * 64}; install_speckit",
                                     STUB_SPECIFY_VERSION="")
        self.assertNotEqual(tampered.returncode, 0)
        self.assertIn("digest mismatch", tampered.stderr)

    def test_version_comparison(self):
        cases = {("0.4.0", "0.4.0"): 0, ("0.13.7", "0.4.0"): 0, ("1.0", "0.4.0"): 0,
                 ("0.3.9", "0.4.0"): 1, ("0.4", "0.4.1"): 1}
        for (found, minimum), status in cases.items():
            with self.subTest(found=found, minimum=minimum):
                result = self.run_function(f"version_at_least {found} {minimum}")
                self.assertEqual(result.returncode, status)


if __name__ == "__main__":
    unittest.main()
