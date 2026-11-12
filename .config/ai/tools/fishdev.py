#!/usr/bin/env python3
"""Vendor-neutral FishDev verification, policy, and retrospective commands."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


CATEGORIES = ("build", "tests", "browser", "security", "performance")
REPORT_DIR = Path(".config/ai/reports")
SECRET_PATTERNS = (
    re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"(?i)\b(?:password|token|api[_-]?key|secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


def redact(value: str) -> str:
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"{path}: expected an object with version 1")
    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def profile_steps(root: Path) -> list[dict]:
    data = load_json(root / ".config/ai/verification.json")
    steps = data.get("steps")
    require(isinstance(steps, list), "verification.json: steps must be a list")
    ids: set[str] = set()
    categories: set[str] = set()
    for step in steps:
        require(isinstance(step, dict), "verification.json: every step must be an object")
        step_id = step.get("id")
        category = step.get("category")
        applicability = step.get("applicability")
        require(isinstance(step_id, str) and re.fullmatch(r"[a-z0-9_-]+", step_id) is not None,
                "verification.json: step id must use lowercase letters, digits, _ or -")
        require(step_id not in ids, f"verification.json: duplicate step {step_id}")
        require(isinstance(category, str) and category, f"{step_id}: missing category")
        require(applicability in ("required", "conditional", "inapplicable"),
                f"{step_id}: invalid applicability")
        require(step.get("failure_policy") in ("blocking", "advisory"),
                f"{step_id}: failure_policy must be blocking or advisory")
        if applicability == "inapplicable":
            require(bool(step.get("reason")), f"{step_id}: inapplicable step needs a reason")
        else:
            command = step.get("command")
            require(isinstance(command, list) and bool(command) and
                    all(isinstance(arg, str) and arg for arg in command),
                    f"{step_id}: command must be a nonempty string array")
        if applicability == "conditional":
            require(isinstance(step.get("when_env"), str) and bool(step["when_env"]),
                    f"{step_id}: conditional step needs when_env")
            require(bool(step.get("reason")), f"{step_id}: conditional step needs skip reason")
        if category == "performance" and applicability != "inapplicable":
            require(isinstance(step.get("max_value"), (int, float)) and
                    not isinstance(step["max_value"], bool),
                    f"{step_id}: performance step needs numeric max_value")
            require(bool(step.get("unit")), f"{step_id}: performance step needs unit")
        timeout = step.get("timeout_seconds", 300)
        require(isinstance(timeout, (int, float)) and 0 < timeout <= 3600,
                f"{step_id}: timeout_seconds must be between 0 and 3600")
        ids.add(step_id)
        categories.add(category)
    require(set(CATEGORIES) <= categories,
            "verification.json: missing category declarations: " +
            ", ".join(sorted(set(CATEGORIES) - categories)))
    return steps


def run_step(root: Path, step: dict) -> dict:
    result = {"id": step["id"], "category": step["category"],
              "status": "skip", "failure_policy": step["failure_policy"],
              "elapsed_seconds": 0.0, "identity": step["id"]}
    if step["applicability"] == "inapplicable":
        result["diagnostic"] = step["reason"]
        return result
    if step["applicability"] == "conditional" and not os.environ.get(step["when_env"]):
        result["diagnostic"] = step["reason"] + f" ({step['when_env']} unset)"
        return result
    command = [sys.executable if arg == "{python}" else arg for arg in step["command"]]
    start = time.monotonic()
    output = ""
    try:
        with tempfile.TemporaryFile() as capture:
            process = subprocess.Popen(command, cwd=root, stdout=capture, stderr=subprocess.STDOUT)
            try:
                return_code = process.wait(timeout=step.get("timeout_seconds", 300))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                return_code = -1
                result["diagnostic"] = "Timed out"
            capture.seek(0)
            output = capture.read(65536).decode("utf-8", errors="replace")
            if capture.read(1):
                output += "\n[output truncated]"
    except OSError as exc:
        return_code = -1
        result["diagnostic"] = f"Command unavailable: {exc}"
    result["elapsed_seconds"] = round(time.monotonic() - start, 3)
    if output:
        log_path = root / REPORT_DIR / f"{step['id']}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(redact(output), encoding="utf-8")
        result["artifact"] = str(log_path.relative_to(root))
    result["status"] = "pass" if return_code == 0 else "fail"
    if return_code and "diagnostic" not in result:
        result["diagnostic"] = f"Exit status {return_code}"
    if result["status"] == "pass" and step["category"] == "performance":
        try:
            measurement = float(output.strip().splitlines()[-1])
        except (ValueError, IndexError):
            result["status"] = "fail"
            result["diagnostic"] = "Performance command must print a numeric result on its last line"
        else:
            result["measurement"] = measurement
            result["unit"] = step["unit"]
            if measurement > step["max_value"]:
                result["status"] = "fail"
                result["diagnostic"] = f"{measurement} {step['unit']} exceeds {step['max_value']} {step['unit']}"
    return result


def verify(root: Path, ci: bool = False) -> int:
    steps = profile_steps(root)
    results = [run_step(root, step) for step in steps]
    failed = any(row["status"] == "fail" and row["failure_policy"] == "blocking"
                 for row in results)
    report = {"version": 1, "mode": "ci" if ci else "local", "status": "fail" if failed else "pass",
              "steps": results}
    write_json(root / REPORT_DIR / "verification.json", report)
    for row in results:
        print(f"{row['status'].upper():4} {row['id']} ({row['category']}): "
              f"{row.get('diagnostic', row.get('artifact', 'ok'))}")
    print(f"Verification: {report['status']}")
    return 1 if failed else 0


def all_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for folder, directories, filenames in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in (".git", "__pycache__")
                                and (Path(folder) / name).relative_to(root).as_posix()
                                not in (".config/ai/reports", ".config/ai/local"))
        for name in sorted(filenames):
            found.append((Path(folder) / name).relative_to(root))
    return found


def rule_config(root: Path) -> dict:
    data = load_json(root / ".config/ai/rules.json")
    require(isinstance(data.get("rules"), list), "rules.json: rules must be a list")
    require(isinstance(data.get("advisory_principles"), list),
            "rules.json: advisory_principles must be a list")
    ids: set[str] = set()
    for rule in data["rules"]:
        require(isinstance(rule, dict), "rules.json: every rule must be an object")
        rule_id = rule.get("id")
        require(isinstance(rule_id, str) and bool(rule_id) and rule_id not in ids,
                "rules.json: missing or duplicate rule id")
        for field in ("principle", "message", "remediation"):
            require(isinstance(rule.get(field), str) and bool(rule[field]), f"{rule_id}: missing {field}")
        require(rule.get("severity") in ("error", "warning"), f"{rule_id}: invalid severity")
        require(rule.get("kind") in ("forbid_paths", "forbid_text"), f"{rule_id}: invalid kind")
        field = "paths" if rule["kind"] == "forbid_paths" else "files"
        require(isinstance(rule.get(field), list) and bool(rule[field]) and
                all(isinstance(item, str) and item for item in rule[field]),
                f"{rule_id}: {field} must be a nonempty string array")
        if rule["kind"] == "forbid_text":
            try:
                re.compile(rule["pattern"])
            except (KeyError, TypeError, re.error) as exc:
                raise ValueError(f"{rule_id}: invalid pattern: {exc}") from exc
        ids.add(rule_id)
    exceptions = data.get("exceptions", [])
    require(isinstance(exceptions, list), "rules.json: exceptions must be a list")
    for item in exceptions:
        require(isinstance(item, dict) and item.get("rule") in ids,
                "rules.json: exception references an unknown rule")
        path = item.get("path")
        require(isinstance(path, str) and bool(path) and not any(c in path for c in "*?[]\\")
                and not path.startswith("/") and ":" not in path and ".." not in Path(path).parts,
                "rules.json: exception needs a narrow relative file path")
        require(bool(item.get("reason")) and bool(item.get("reviewer")),
                "rules.json: exception needs reason and reviewer")
        try:
            expiry = date.fromisoformat(item["expires"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("rules.json: exception needs ISO expiry date") from exc
        require(expiry >= date.today(), f"rules.json: expired exception for {path}")
    return data


def check(root: Path) -> int:
    data = rule_config(root)
    files = all_files(root)
    exceptions = {(item["rule"], item["path"]) for item in data.get("exceptions", [])}
    violations = []
    for rule in data["rules"]:
        patterns = rule["paths"] if rule["kind"] == "forbid_paths" else rule["files"]
        for path in files:
            location = path.as_posix()
            if not any(fnmatch.fnmatchcase(location, pattern) for pattern in patterns):
                continue
            if rule["kind"] == "forbid_paths":
                matches = [location]
            else:
                try:
                    lines = (root / path).read_text(encoding="utf-8").splitlines()
                except (OSError, UnicodeError):
                    continue
                regex = re.compile(rule["pattern"])
                matches = [f"{location}:{index}" for index, line in enumerate(lines, 1)
                           if regex.search(line)]
            for match in matches:
                if (rule["id"], location) in exceptions:
                    print(f"EXCEPTED {rule['id']} {location}")
                    continue
                violations.append((rule, match))
                print(f"{rule['severity'].upper()} {rule['id']} {match}: "
                      f"{rule['message']} Remedy: {rule['remediation']}")
    for rule in data["rules"]:
        print(f"COVERED {rule['principle']} by {rule['id']}")
    for principle in data["advisory_principles"]:
        print(f"ADVISORY {principle}")
    return 1 if any(rule["severity"] == "error" for rule, _ in violations) else 0


CORRECTION_LINE = re.compile(r"^\s*[-*]?\s*Human correction \[([^]]+)\] "
                             r"\((rule|script|skill|verification)\):\s*(.+)$", re.I)


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def correction_events(root: Path, imported: Path | None) -> list[dict]:
    events = []
    for relative in (Path(".config/ai/progress.ai"), Path(".config/ai/handoff.ai")):
        path = root / relative
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = CORRECTION_LINE.match(line)
            if match:
                session, target, correction = match.groups()
                events.append({"session": session, "target": target.lower(),
                               "correction": redact(correction),
                               "source": f"{relative.as_posix()}:{line_number}"})
    if imported and imported.exists():
        for line_number, line in enumerate(imported.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{imported}:{line_number}: {exc}") from exc
            require(isinstance(item, dict), f"{imported}:{line_number}: event must be an object")
            if item.get("kind") != "correction":
                continue
            require(all(isinstance(item.get(field), str) and item[field]
                        for field in ("session", "target", "correction")),
                    f"{imported}:{line_number}: correction needs session, target, correction")
            require(item["target"] in ("rule", "script", "skill", "verification"),
                    f"{imported}:{line_number}: invalid target")
            events.append({"session": redact(item["session"]), "target": item["target"],
                           "correction": redact(item["correction"]),
                           "source": f"{imported.relative_to(root)}:{line_number}"
                           if imported.is_relative_to(root) else f"import:{line_number}"})
    return events


TARGETS = {"rule": ".config/ai/rules.json or .specify/memory/constitution.md",
           "script": ".config/ai/tools/", "skill": ".config/ai/skills/",
           "verification": ".config/ai/verification.json"}


def retrospective(root: Path, imported: Path | None) -> int:
    events = correction_events(root, imported)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event in events:
        groups[(event["target"], normalized(event["correction"]))].append(event)
    path = root / ".config/ai/learning/proposals.json"
    existing = load_json(path) if path.exists() else {"version": 1, "proposals": []}
    require(isinstance(existing.get("proposals"), list), "proposals.json: proposals must be a list")
    by_id = {item["id"]: item for item in existing["proposals"]}
    created = 0
    for (target, issue), members in sorted(groups.items()):
        sessions = {item["session"] for item in members}
        if len(sessions) < 2 or not issue:
            continue
        identifier = hashlib.sha256(f"{target}:{issue}".encode()).hexdigest()[:12]
        evidence = sorted({f"{item['session']} @ {item['source']}" for item in members})
        if identifier in by_id:
            by_id[identifier]["evidence"] = evidence
            continue
        correction = members[0]["correction"]
        by_id[identifier] = {
            "id": identifier, "status": "proposed", "target": target,
            "issue": correction, "evidence": evidence,
            "rationale": f"The same human correction appeared in {len(sessions)} sessions.",
            "candidate_change": {"file_or_area": TARGETS[target],
                                 "draft": f"Add a project instruction or check: {correction}"},
            "likely_impact": "Prevents repetition if the proposed check or instruction is adopted.",
            "validation_plan": "Add a failing regression fixture, implement the change in a spec task, then run project verification.",
        }
        created += 1
    existing["proposals"] = sorted(by_id.values(), key=lambda item: item["id"])
    existing["observations"] = [
        {"target": target, "issue": members[0]["correction"],
         "evidence": sorted({f"{item['session']} @ {item['source']}" for item in members})}
        for (target, _), members in sorted(groups.items())
        if len({item["session"] for item in members}) < 2
    ]
    write_json(path, existing)
    observations = len(existing["observations"])
    print(f"Correction events: {len(events)}; single-session observations: {observations}; "
          f"new proposals: {created}; total proposals: {len(existing['proposals'])}")
    print(f"Review {path}; proposals do not change governing files.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("verify").add_argument("--ci", action="store_true")
    subcommands.add_parser("check")
    subcommands.add_parser("retro").add_argument("--events", type=Path)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    try:
        if arguments.command == "verify":
            return verify(root, arguments.ci)
        if arguments.command == "check":
            return check(root)
        imported = arguments.events.resolve() if arguments.events else root / ".config/ai/local/sessions.jsonl"
        return retrospective(root, imported)
    except ValueError as exc:
        print(f"FishDev: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
