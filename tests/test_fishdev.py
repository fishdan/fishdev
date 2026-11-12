"""Behavioral fixtures for the repository-owned FishDev commands."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / ".config/ai/tools/fishdev.py"
CATEGORIES = ("build", "tests", "browser", "security", "performance")


class FishdevFixture(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        (self.root / ".config/ai").mkdir(parents=True)

    def write_json(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "--root", str(self.root), *args],
                              text=True, capture_output=True, check=False)

    def profile(self):
        steps = []
        for category in CATEGORIES:
            steps.append({"id": category, "category": category,
                          "applicability": "inapplicable", "reason": "fixture has no surface",
                          "failure_policy": "blocking"})
        return {"version": 1, "steps": steps}

    def rules(self):
        return {"version": 1, "advisory_principles": ["IV Clean Code"],
                "exceptions": [], "rules": [
                    {"id": "VENDOR-001", "principle": "AI neutrality", "kind": "forbid_paths",
                     "paths": [".claude/*"], "severity": "error", "message": "Vendor workflow file",
                     "remediation": "Move it under .config/ai"},
                    {"id": "ARCH-001", "principle": "Layer boundary", "kind": "forbid_text",
                     "files": ["src/*"], "pattern": "^import tests$", "severity": "error",
                     "message": "Runtime imports tests", "remediation": "Remove the import"}]}


class VerificationTests(FishdevFixture):
    def test_required_failure_and_visible_skip_are_identical_in_ci(self):
        profile = self.profile()
        profile["steps"][0].update(applicability="required", command=["{python}", "-c", "print('build')"])
        profile["steps"][0].pop("reason")
        profile["steps"][1].update(applicability="required", command=["{python}", "-c", "raise SystemExit(1)"])
        profile["steps"][1].pop("reason")
        self.write_json(".config/ai/verification.json", profile)
        local = self.run_tool("verify")
        local_report = json.loads((self.root / ".config/ai/reports/verification.json").read_text())
        ci = self.run_tool("verify", "--ci")
        ci_report = json.loads((self.root / ".config/ai/reports/verification.json").read_text())
        self.assertEqual(local.returncode, 1)
        self.assertEqual(ci.returncode, 1)
        self.assertEqual([x["status"] for x in local_report["steps"]],
                         [x["status"] for x in ci_report["steps"]])
        self.assertEqual([x["status"] for x in ci_report["steps"]],
                         ["pass", "fail", "skip", "skip", "skip"])
        self.assertIn("fixture has no surface", ci.stdout)

    def test_missing_command_and_category_fail_validation(self):
        profile = self.profile()
        profile["steps"].pop()
        self.write_json(".config/ai/verification.json", profile)
        self.assertIn("missing category", self.run_tool("verify").stderr)
        profile = self.profile()
        profile["steps"][0].update(applicability="required")
        self.write_json(".config/ai/verification.json", profile)
        result = self.run_tool("verify")
        self.assertEqual(result.returncode, 2)
        self.assertIn("command", result.stderr)

    def test_unavailable_tool_fails_and_advisory_failure_is_visible(self):
        profile = self.profile()
        profile["steps"][0].update(applicability="required", command=["fishdev_missing_command_98765"])
        self.write_json(".config/ai/verification.json", profile)
        self.assertEqual(self.run_tool("verify").returncode, 1)
        profile["steps"][0]["failure_policy"] = "advisory"
        self.write_json(".config/ai/verification.json", profile)
        result = self.run_tool("verify")
        self.assertEqual(result.returncode, 0)
        self.assertIn("FAIL", result.stdout)

    def test_browser_script_runs_and_performance_budget_blocks(self):
        profile = self.profile()
        profile["steps"][2].update(applicability="required", command=["{python}", "browser.py"])
        profile["steps"][4].update(applicability="required", command=["{python}", "-c", "print(11)"],
                                   max_value=10, unit="ms")
        (self.root / "browser.py").write_text("from pathlib import Path\nPath('browser-ran').write_text('yes')\n")
        self.write_json(".config/ai/verification.json", profile)
        result = self.run_tool("verify")
        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.root / "browser-ran").exists())
        self.assertIn("exceeds", result.stdout)

    def test_timeout_and_starter_profile_fail_visibly(self):
        profile = self.profile()
        profile["steps"][0].update(applicability="required",
                                   command=["{python}", "-c", "import time; time.sleep(1)"],
                                   timeout_seconds=0.01)
        self.write_json(".config/ai/verification.json", profile)
        self.assertIn("Timed out", self.run_tool("verify").stdout)
        defaults = TOOL.parents[1] / "defaults"
        shutil.copy(defaults / "verification.json", self.root / ".config/ai/verification.json")
        shutil.copy(defaults / "rules.json", self.root / ".config/ai/rules.json")
        tool_copy = self.root / ".config/ai/tools/fishdev.py"
        tool_copy.parent.mkdir(parents=True)
        shutil.copy(TOOL, tool_copy)
        result = self.run_tool("verify")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Configure the project build command", (self.root / ".config/ai/reports/build.log").read_text())


class RuleTests(FishdevFixture):
    def test_path_and_dependency_boundary_violations(self):
        self.write_json(".config/ai/rules.json", self.rules())
        (self.root / ".claude").mkdir()
        (self.root / ".claude/workflow.md").write_text("vendor workflow")
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text("import tests\n")
        first = self.run_tool("check")
        second = self.run_tool("check")
        self.assertEqual(first.returncode, 1)
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("VENDOR-001 .claude/workflow.md", first.stdout)
        self.assertIn("ARCH-001 src/app.py:1", first.stdout)
        (self.root / ".claude/workflow.md").unlink()
        (self.root / "src/app.py").write_text("print('ok')\n")
        clean = self.run_tool("check")
        self.assertEqual(clean.returncode, 0)
        self.assertIn("ADVISORY IV Clean Code", clean.stdout)

    def test_exception_is_narrow_and_expires(self):
        rules = self.rules()
        rules["exceptions"] = [{"rule": "ARCH-001", "path": "src/app.py",
                                "reason": "migration", "reviewer": "maintainer",
                                "expires": "2999-01-01"}]
        self.write_json(".config/ai/rules.json", rules)
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text("import tests\n")
        self.assertIn("EXCEPTED ARCH-001", self.run_tool("check").stdout)
        rules["exceptions"][0]["expires"] = "2000-01-01"
        self.write_json(".config/ai/rules.json", rules)
        self.assertEqual(self.run_tool("check").returncode, 2)


class RetrospectiveTests(FishdevFixture):
    def test_empty_history_reports_evidence_limit(self):
        result = self.run_tool("retro")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Correction events: 0", result.stdout)
        data = json.loads((self.root / ".config/ai/learning/proposals.json").read_text())
        self.assertEqual(data["proposals"], [])

    def test_recurring_correction_proposes_once_and_preserves_disposition(self):
        events = self.root / ".config/ai/local/sessions.jsonl"
        events.parent.mkdir(parents=True)
        events.write_text("\n".join(json.dumps(x) for x in [
            {"kind": "correction", "session": "one", "target": "rule",
             "correction": "Keep policy under .config/ai"},
            {"kind": "correction", "session": "two", "target": "rule",
             "correction": "Keep policy under .config/ai!"},
            {"kind": "correction", "session": "three", "target": "script",
             "correction": "Use a timeout"}]) + "\n")
        first = self.run_tool("retro")
        self.assertEqual(first.returncode, 0)
        path = self.root / ".config/ai/learning/proposals.json"
        data = json.loads(path.read_text())
        self.assertEqual(len(data["proposals"]), 1)
        self.assertEqual(len(data["proposals"][0]["evidence"]), 2)
        data["proposals"][0]["status"] = "rejected"
        path.write_text(json.dumps(data))
        self.assertEqual(self.run_tool("retro").returncode, 0)
        data = json.loads(path.read_text())
        self.assertEqual(len(data["proposals"]), 1)
        self.assertEqual(data["proposals"][0]["status"], "rejected")

    def test_project_history_is_read_and_secrets_are_redacted(self):
        progress = self.root / ".config/ai/progress.ai"
        handoff = self.root / ".config/ai/handoff.ai"
        correction = "Never print token=supersecret"
        progress.write_text(f"- Human correction [one] (script): {correction}\n")
        handoff.write_text(f"- Human correction [two] (script): {correction}\n")
        result = self.run_tool("retro")
        self.assertEqual(result.returncode, 0)
        text = (self.root / ".config/ai/learning/proposals.json").read_text()
        self.assertNotIn("supersecret", text)
        self.assertIn("[REDACTED]", text)

    def test_no_transcripts_or_single_correction_is_not_a_proposal(self):
        (self.root / ".config/ai/progress.ai").write_text(
            "- Human correction [one] (skill): Document test failures\n")
        result = self.run_tool("retro")
        self.assertEqual(result.returncode, 0)
        self.assertIn("single-session observations: 1", result.stdout)
        data = json.loads((self.root / ".config/ai/learning/proposals.json").read_text())
        self.assertEqual(data["proposals"], [])
        self.assertEqual(len(data["observations"]), 1)


if __name__ == "__main__":
    unittest.main()
