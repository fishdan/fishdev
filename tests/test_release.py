"""Fixtures for the maintainer release tool and the unpinned-download rule."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
RELEASE_TOOL = REPO / ".config/ai/tools/release.py"
FISHDEV_TOOL = REPO / ".config/ai/tools/fishdev.py"
SHA_A = "a" * 64
SHA_B = "b" * 64


def release_config():
    return {
        "version": 1,
        "release": "v0.5.0",
        "source": "https://raw.githubusercontent.com/example/fishdev",
        "files": ["start.ai"],
        "generated": ["install.sh", "README.md"],
        "pins": {
            "uv": {"version": "0.13.7", "minimum": "0.4.0", "reviewed": "2026-11-16",
                   "source": "https://github.com/astral-sh/uv/releases/tag/0.13.7",
                   "installer_sh": {"url": "https://example.com/uv/0.13.7/uv-installer.sh", "sha256": SHA_A},
                   "installer_ps1": {"url": "https://example.com/uv/0.13.7/uv-installer.ps1", "sha256": SHA_B}},
            "specify-cli": {"version": "1.3.3", "reviewed": "2026-11-16",
                            "source": "https://pypi.org/project/specify-cli/1.3.3/",
                            "wheel": {"url": "https://example.com/specify_cli-1.3.3-py3-none-any.whl",
                                      "sha256": SHA_A}},
            "actions": {"actions/checkout": {"version": "v7.0.1", "commit": "3" * 40,
                                             "reviewed": "2026-11-16",
                                             "source": "https://github.com/actions/checkout/releases/tag/v7.0.1"}},
        },
    }


class ReleaseFixture(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.write(".config/ai/release.json", json.dumps(release_config(), indent=2) + "\n")
        self.write("start.ai", "Start here.\n")
        self.write("install.sh", "#!/usr/bin/env bash\n"
                   "# BEGIN fishdev-release:installer-pins\n"
                   "placeholder\n"
                   "# END fishdev-release:installer-pins\n"
                   "echo done\n")
        self.write("README.md", "# Fixture\n\n<!-- BEGIN fishdev-release:bootstrap -->\n"
                   "<!-- END fishdev-release:bootstrap -->\n\nMore text.\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def config(self):
        return json.loads((self.root / ".config/ai/release.json").read_text(encoding="utf-8"))

    def run_release(self, *args):
        return subprocess.run([sys.executable, str(RELEASE_TOOL), "--root", str(self.root), *args],
                              text=True, capture_output=True, check=False)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in sorted(self.root.rglob("*")) if path.is_file() and ".git" not in path.parts}


class ReleaseToolTests(ReleaseFixture):
    def test_update_is_deterministic_and_check_passes(self):
        first = self.run_release("update")
        self.assertEqual(first.returncode, 0, first.stderr)
        after_first = self.snapshot()
        second = self.run_release("update")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(after_first, self.snapshot())
        checked = self.run_release("check")
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

        manifest = json.loads((self.root / ".config/ai/release-manifest.json").read_text())
        self.assertEqual(manifest["release"], "v0.5.0")
        self.assertEqual(manifest["source"], "https://raw.githubusercontent.com/example/fishdev/v0.5.0")
        self.assertEqual([entry["path"] for entry in manifest["files"]], ["start.ai"])
        installer = (self.root / "install.sh").read_text()
        self.assertIn(f"start.ai {manifest['files'][0]['sha256']}", installer)
        self.assertIn('UV_INSTALLER_SHA256="' + SHA_A + '"', installer)
        self.assertTrue(installer.endswith("# END fishdev-release:installer-pins\necho done\n"))

    def test_readme_bootstrap_digest_tracks_installer(self):
        self.assertEqual(self.run_release("update").returncode, 0)
        import hashlib
        digest = hashlib.sha256((self.root / "install.sh").read_bytes()).hexdigest()
        readme = (self.root / "README.md").read_text()
        self.assertIn(f'{digest}  fishdev-install.sh" | sha256sum -c -', readme)
        self.assertIn("raw.githubusercontent.com/example/fishdev/v0.5.0/install.sh", readme)
        self.assertTrue(readme.endswith("<!-- END fishdev-release:bootstrap -->\n\nMore text.\n"))

    def test_stale_manifest_and_blocks_fail_check_with_names(self):
        self.assertEqual(self.run_release("update").returncode, 0)
        self.write("start.ai", "Start somewhere else.\n")
        stale = self.run_release("check")
        self.assertEqual(stale.returncode, 1)
        for name in (".config/ai/release-manifest.json", "install.sh", "README.md"):
            self.assertIn(f"STALE {name}", stale.stdout)
        self.assertEqual(self.run_release("update").returncode, 0)
        self.assertEqual(self.run_release("check").returncode, 0)

    def test_hand_edit_inside_generated_block_is_stale(self):
        self.assertEqual(self.run_release("update").returncode, 0)
        text = (self.root / "install.sh").read_text().replace('UV_VERSION="0.13.7"', 'UV_VERSION="0.1.0"')
        self.write("install.sh", text)
        stale = self.run_release("check")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("STALE install.sh", stale.stdout)

    def test_invalid_pins_are_rejected(self):
        cases = {
            "short digest": ("uv", "installer_sh", "sha256", "abc"),
            "http url": ("uv", "installer_sh", "url", "http://example.com/uv/0.13.7/uv-installer.sh"),
            "url without version": ("specify-cli", "wheel", "url", "https://example.com/specify_cli-latest.whl"),
        }
        for label, (tool, artifact, field, value) in cases.items():
            with self.subTest(label):
                config = release_config()
                config["pins"][tool][artifact][field] = value
                self.write(".config/ai/release.json", json.dumps(config))
                result = self.run_release("check")
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("release.json", result.stderr)
        config = release_config()
        config["pins"]["actions"]["actions/checkout"]["commit"] = "v7"
        self.write(".config/ai/release.json", json.dumps(config))
        self.assertEqual(self.run_release("check").returncode, 2)
        config = release_config()
        config["files"].append("missing.txt")
        self.write(".config/ai/release.json", json.dumps(config))
        self.assertIn("missing.txt", self.run_release("check").stderr)

    def test_unknown_or_unclosed_block_is_rejected(self):
        self.write("README.md", "<!-- BEGIN fishdev-release:mystery -->\n<!-- END fishdev-release:mystery -->\n")
        self.assertIn("mystery", self.run_release("check").stderr)
        self.write("README.md", "<!-- BEGIN fishdev-release:bootstrap -->\nno end\n")
        self.assertIn("END", self.run_release("check").stderr)

    def test_tagged_release_cannot_change_without_new_release_id(self):
        if shutil.which("git") is None:
            self.fail("git is required for the release tag guard test")
        git = ["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]
        self.assertEqual(self.run_release("update").returncode, 0)
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "release"], check=True)
        subprocess.run([*git, "tag", "v0.5.0"], check=True)
        self.write("start.ai", "Changed after release.\n")
        refused = self.run_release("update")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("--release", refused.stderr)
        self.write("start.ai", "Start here.\n")
        config = self.config()
        config["pins"]["uv"]["installer_sh"]["sha256"] = SHA_B
        self.write(".config/ai/release.json", json.dumps(config, indent=2) + "\n")
        pin_only = self.run_release("update")
        self.assertEqual(pin_only.returncode, 2)
        self.assertIn("install.sh", pin_only.stderr)
        bumped = self.run_release("update", "--release", "v0.5.1")
        self.assertEqual(bumped.returncode, 0, bumped.stderr)
        self.assertEqual(self.config()["release"], "v0.5.1")
        self.assertIn('FISHDEV_RELEASE="v0.5.1"', (self.root / "install.sh").read_text())

    def test_action_block_keeps_indentation(self):
        config = release_config()
        config["generated"] = ["verify.yml"]
        self.write(".config/ai/release.json", json.dumps(config))
        self.write("verify.yml", "    steps:\n      # BEGIN fishdev-release:uses:actions/checkout\n"
                   "      - uses: actions/checkout@v4\n      # END fishdev-release:uses:actions/checkout\n")
        self.assertEqual(self.run_release("update").returncode, 0)
        self.assertIn(f"      - uses: actions/checkout@{'3' * 40} # v7.0.1\n",
                      (self.root / "verify.yml").read_text())


class UnpinnedDownloadRuleTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        rules = json.loads((REPO / ".config/ai/rules.json").read_text(encoding="utf-8"))
        rule = next(item for item in rules["rules"] if item["id"] == "SEC-001")
        (self.root / ".config/ai").mkdir(parents=True)
        (self.root / ".config/ai/rules.json").write_text(json.dumps(
            {"version": 1, "rules": [rule], "exceptions": [], "advisory_principles": []}))

    def check(self, text, name="install.sh"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        result = subprocess.run([sys.executable, str(FISHDEV_TOOL), "--root", str(self.root), "check"],
                                text=True, capture_output=True, check=False)
        path.unlink()
        return result

    def test_unpinned_downloads_are_reported_with_location(self):
        bad = {
            "curl to shell": "curl -fsSL https://example.com/x.sh | sh",
            "curl to bash": "curl -LsSf https://example.com/x.sh | sudo bash",
            "wget to shell": "wget -qO- https://example.com/x.sh | sh",
            "irm to iex": 'powershell -c "irm https://astral.sh/uv/install.ps1 | iex"',
            "raw main": "curl -fsSLo a https://raw.githubusercontent.com/fishdan/fishdev/main/start.ai",
            "git without ref": "uv tool install x --from git+https://github.com/github/spec-kit.git",
            "unversioned uv": "curl -fsSLo uv.sh https://astral.sh/uv/install.sh",
            "unversioned speckit": "uv tool install --python 3.11 specify-cli",
            "action tag": "      - uses: actions/checkout@v4",
        }
        for label, line in bad.items():
            with self.subTest(label):
                result = self.check(f"#!/bin/sh\n{line}\n")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("ERROR SEC-001 install.sh:2", result.stdout)
        workflow = self.check("    - uses: actions/setup-python@v5\n", ".github/workflows/ci.yml")
        self.assertIn("SEC-001 .github/workflows/ci.yml:1", workflow.stdout)

    def test_pinned_and_verified_downloads_pass(self):
        good = "\n".join([
            'curl -fsSLo f.sh https://raw.githubusercontent.com/fishdan/fishdev/v0.5.0/install.sh '
            '&& echo "abc  f.sh" | sha256sum -c - && bash f.sh',
            'echo "abc  f.sh" | shasum -a 256 -c -',
            "uv tool install specify-cli==1.3.3",
            "uv tool install x --from git+https://github.com/github/spec-kit.git@v1.3.3",
            'curl -fsSLo uv.sh https://astral.sh/uv/0.13.7/install.sh',
            "      - uses: actions/checkout@" + "3" * 40 + " # v7.0.1",
        ])
        result = self.check(good + "\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("ERROR", result.stdout)


if __name__ == "__main__":
    unittest.main()
