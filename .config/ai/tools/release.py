#!/usr/bin/env python3
"""Maintainer tool: generate and check FishDev's release manifest and pinned download blocks.

`.config/ai/release.json` is the only hand-edited input. `update` writes
`.config/ai/release-manifest.json` and regenerates every region between
`BEGIN fishdev-release:<block>` and `END fishdev-release:<block>` marker lines in the
files listed under `generated`. `check` renders the same output in memory and fails
on any difference. This module is not shipped to projects that adopt FishDev.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


CONFIG = PurePosixPath(".config/ai/release.json")
MANIFEST = PurePosixPath(".config/ai/release-manifest.json")
BOOTSTRAP = PurePosixPath("install.sh")
BEGIN = re.compile(r"BEGIN fishdev-release:(\S+)")
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
RELEASE = re.compile(r"v\d+\.\d+\.\d+")
VERSION = re.compile(r"\d+(?:\.\d+)+")
REVIEW_DAYS = 31


class ReleaseError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(f"{CONFIG}: {message}")


def relative_path(value: object, label: str) -> str:
    require(isinstance(value, str) and bool(value), f"{label} must be a nonempty path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in value,
            f"{label} must be a relative POSIX path: {value}")
    return value


def check_date(value: object, label: str) -> None:
    try:
        date.fromisoformat(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        require(False, f"{label} needs an ISO reviewed date")


def check_artifact(artifact: object, label: str, version: str) -> None:
    require(isinstance(artifact, dict), f"{label} must be an object with url and sha256")
    url, digest = artifact.get("url"), artifact.get("sha256")
    require(isinstance(url, str) and url.startswith("https://"), f"{label}.url must use https")
    require(version in url, f"{label}.url must name pinned version {version}")
    require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None,
            f"{label}.sha256 must be 64 lowercase hex characters")


def load_config(root: Path) -> dict:
    try:
        data = json.loads((root / CONFIG).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"Cannot read {CONFIG}: {exc}") from exc
    require(isinstance(data, dict) and data.get("version") == 1, "expected an object with version 1")
    require(isinstance(data.get("release"), str) and RELEASE.fullmatch(data["release"]) is not None,
            "release must look like v1.2.3")
    source = data.get("source")
    require(isinstance(source, str) and source.startswith("https://") and not source.endswith("/"),
            "source must be an https URL without a trailing slash")
    for key in ("files", "generated"):
        items = data.get(key)
        require(isinstance(items, list) and bool(items), f"{key} must be a nonempty list")
        require(len(set(items)) == len(items), f"{key} has duplicate entries")
        for item in items:
            relative_path(item, key)
            require((root / item).is_file(), f"{key} entry does not exist: {item}")
    require(str(BOOTSTRAP) not in data["files"], "install.sh is the bootstrap and cannot be a shipped file")
    pins = data.get("pins")
    require(isinstance(pins, dict), "pins must be an object")
    uv = pins.get("uv")
    require(isinstance(uv, dict), "pins.uv is required")
    for field in ("version", "minimum"):
        require(isinstance(uv.get(field), str) and VERSION.fullmatch(uv[field]) is not None,
                f"pins.uv.{field} must be a dotted version")
    check_date(uv.get("reviewed"), "pins.uv")
    for artifact in ("installer_sh", "installer_ps1"):
        check_artifact(uv.get(artifact), f"pins.uv.{artifact}", uv["version"])
    speckit = pins.get("specify-cli")
    require(isinstance(speckit, dict), "pins.specify-cli is required")
    require(isinstance(speckit.get("version"), str) and VERSION.fullmatch(speckit["version"]) is not None,
            "pins.specify-cli.version must be a dotted version")
    check_date(speckit.get("reviewed"), "pins.specify-cli")
    check_artifact(speckit.get("wheel"), "pins.specify-cli.wheel", f"-{speckit['version']}-")
    require(speckit["wheel"]["url"].endswith(".whl"), "pins.specify-cli.wheel.url must be a wheel")
    actions = pins.get("actions", {})
    require(isinstance(actions, dict), "pins.actions must be an object")
    for name, action in actions.items():
        require(isinstance(action, dict) and isinstance(action.get("version"), str) and bool(action["version"]),
                f"pins.actions.{name} needs a version")
        require(isinstance(action.get("commit"), str) and COMMIT.fullmatch(action["commit"]) is not None,
                f"pins.actions.{name}.commit must be a full 40-character commit SHA")
        check_date(action.get("reviewed"), f"pins.actions.{name}")
    return data


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wheel_name(config: dict) -> str:
    return config["pins"]["specify-cli"]["wheel"]["url"].rsplit("/", 1)[-1]


def build_manifest(config: dict, contents: dict[str, str]) -> dict:
    return {"version": 1, "release": config["release"],
            "source": f"{config['source']}/{config['release']}",
            "files": [{"path": path, "sha256": digest(contents[path])} for path in config["files"]]}


def render_installer_pins(config: dict, manifest: dict, contents: dict[str, str]) -> list[str]:
    uv, speckit = config["pins"]["uv"], config["pins"]["specify-cli"]
    lines = [f'FISHDEV_RELEASE="{config["release"]}"',
             f'FISHDEV_RELEASE_SOURCE="{manifest["source"]}"',
             "FISHDEV_FILES=("]
    lines += [f'    "{entry["path"]} {entry["sha256"]}"' for entry in manifest["files"]]
    lines += [")",
              f'UV_VERSION="{uv["version"]}"',
              f'UV_MINIMUM_VERSION="{uv["minimum"]}"',
              f'UV_INSTALLER_URL="{uv["installer_sh"]["url"]}"',
              f'UV_INSTALLER_SHA256="{uv["installer_sh"]["sha256"]}"',
              f'SPECIFY_VERSION="{speckit["version"]}"',
              f'SPECIFY_WHEEL_URL="{speckit["wheel"]["url"]}"',
              f'SPECIFY_WHEEL_SHA256="{speckit["wheel"]["sha256"]}"']
    return lines


def render_bootstrap(config: dict, manifest: dict, contents: dict[str, str]) -> list[str]:
    url = f"{manifest['source']}/{BOOTSTRAP}"
    installer = digest(contents[str(BOOTSTRAP)])

    def command(check: str) -> str:
        return (f'curl -fsSLo fishdev-install.sh {url} && echo "{installer}  fishdev-install.sh" | '
                f"{check} && bash fishdev-install.sh && rm fishdev-install.sh")

    return [f"Install FishDev {config['release']} from the root of a new project directory. "
            "These commands download the installer, check its SHA-256 digest, and run it only if the check passes.",
            "", "Linux:", "", "```bash", command("sha256sum -c -"), "```",
            "", "macOS:", "", "```bash", command("shasum -a 256 -c -"), "```",
            "", "The installer then verifies every FishDev file, the uv installer, and the SpecKit wheel "
            "against digests pinned for this release. See [release integrity](docs/release-integrity.md) "
            "for what this protects against and its limits."]


def powershell_fetch(variable: str, url: str, sha: str, label: str) -> list[str]:
    return [f"Invoke-WebRequest -UseBasicParsing '{url}' -OutFile {variable}",
            f"$actual = (Get-FileHash -Algorithm SHA256 {variable}).Hash.ToLowerInvariant()",
            f"if ($actual -ne '{sha}') {{ Remove-Item {variable}; "
            f"throw \"{label} digest mismatch: expected {sha}, got $actual\" }}"]


def render_windows_uv(config: dict, manifest: dict, contents: dict[str, str]) -> list[str]:
    uv = config["pins"]["uv"]
    fetch = powershell_fetch("$uvInstaller", uv["installer_ps1"]["url"], uv["installer_ps1"]["sha256"],
                             "uv installer")
    return ["```powershell", "$ErrorActionPreference = 'Stop'",
            "if (Get-Command uv -ErrorAction SilentlyContinue) {",
            "    $found = [version]((uv --version).Split(' ')[1])",
            f"    if ($found -lt [version]'{uv['minimum']}') {{ "
            f"throw \"uv $found is older than {uv['minimum']}. Run: uv self update {uv['version']}\" }}",
            "    Write-Host \"Using existing uv $found\"",
            "} else {",
            f"    $uvInstaller = Join-Path ([System.IO.Path]::GetTempPath()) 'uv-installer-{uv['version']}.ps1'",
            *[f"    {line}" for line in fetch],
            "    powershell -ExecutionPolicy Bypass -File $uvInstaller",
            "    Remove-Item $uvInstaller",
            "}", "```"]


def render_windows_speckit(config: dict, manifest: dict, contents: dict[str, str]) -> list[str]:
    wheel = config["pins"]["specify-cli"]["wheel"]
    return ["```powershell", "$ErrorActionPreference = 'Stop'", "uv --version", "uv python install 3.11",
            f"$wheel = Join-Path ([System.IO.Path]::GetTempPath()) '{wheel_name(config)}'",
            *powershell_fetch("$wheel", wheel["url"], wheel["sha256"], "SpecKit wheel"),
            "uv tool install --force --python 3.11 $wheel", "Remove-Item $wheel", "specify version", "```"]


def render_windows_files(config: dict, manifest: dict, contents: dict[str, str]) -> list[str]:
    lines = ["```powershell", "$ErrorActionPreference = 'Stop'",
             f"$fishDevSource = '{manifest['source']}'", "$fishDevFiles = [ordered]@{"]
    lines += [f"    '{entry['path']}' = '{entry['sha256']}'" for entry in manifest["files"]]
    lines += ["}",
              "$stage = Join-Path ([System.IO.Path]::GetTempPath()) ('fishdev-' + [guid]::NewGuid())",
              "try {",
              "    foreach ($path in $fishDevFiles.Keys) {",
              "        $staged = Join-Path $stage $path",
              "        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $staged) | Out-Null",
              "        Invoke-WebRequest -UseBasicParsing \"$fishDevSource/$path\" -OutFile $staged",
              "        $actual = (Get-FileHash -Algorithm SHA256 $staged).Hash.ToLowerInvariant()",
              "        if ($actual -ne $fishDevFiles[$path]) { "
              "throw \"Digest mismatch for ${path}: expected $($fishDevFiles[$path]), got $actual\" }",
              "    }",
              "    foreach ($path in $fishDevFiles.Keys) {",
              "        $parent = Split-Path -Parent $path",
              "        if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }",
              "        Copy-Item (Join-Path $stage $path) $path",
              "    }",
              "} finally {",
              "    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }",
              "}", "```"]
    return lines


def render_repair_tools(config: dict, manifest: dict, contents: dict[str, str]) -> list[str]:
    uv, wheel = config["pins"]["uv"], config["pins"]["specify-cli"]["wheel"]
    name = wheel_name(config)
    return ["```bash",
            f"# Install uv {uv['version']} if missing. The installer is checked before it runs.",
            f"curl -fsSLo uv-installer.sh {uv['installer_sh']['url']}",
            f'echo "{uv["installer_sh"]["sha256"]}  uv-installer.sh" | sha256sum -c - && sh uv-installer.sh',
            "rm -f uv-installer.sh", "",
            f"# Install the pinned SpecKit {config['pins']['specify-cli']['version']} wheel.",
            f"curl -fsSLo {name} {wheel['url']}",
            f'echo "{wheel["sha256"]}  {name}" | sha256sum -c - && uv tool install --force {name}',
            f"rm -f {name}", "```", "",
            "On macOS, replace `sha256sum -c -` with `shasum -a 256 -c -`. "
            "On Windows, follow the SpecKit steps in FishDev's `docs/windows-vscode-powershell.md`."]


def render_action(name: str):
    def render(config: dict, manifest: dict, contents: dict[str, str]) -> list[str]:
        action = config["pins"]["actions"].get(name)
        if action is None:
            raise ReleaseError(f"{CONFIG}: no pins.actions entry for block uses:{name}")
        return [f"- uses: {name}@{action['commit']} # {action['version']}"]
    return render


RENDERERS = {"installer-pins": render_installer_pins, "bootstrap": render_bootstrap,
             "windows-uv": render_windows_uv, "windows-speckit": render_windows_speckit,
             "windows-files": render_windows_files, "repair-tools": render_repair_tools}


def renderer(block: str):
    if block.startswith("uses:"):
        return render_action(block[len("uses:"):])
    if block not in RENDERERS:
        raise ReleaseError(f"unknown generated block '{block}'")
    return RENDERERS[block]


def render_file(path: str, text: str, config: dict, manifest: dict, contents: dict[str, str]) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        index += 1
        match = BEGIN.search(line)
        if not match:
            continue
        block = match.group(1)
        end = f"END fishdev-release:{block}"
        closing = next((i for i in range(index, len(lines)) if end in lines[i]), None)
        if closing is None:
            raise ReleaseError(f"{path}: missing '{end}' marker")
        indent = line[:len(line) - len(line.lstrip())]
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        for rendered in renderer(block)(config, manifest, contents):
            output.append((indent + rendered if rendered else "") + newline)
        output.append(lines[closing])
        index = closing + 1
    return "".join(output)


def read(root: Path, path: str) -> str:
    return (root / path).read_bytes().decode("utf-8")


def build(root: Path, config: dict) -> dict[str, str]:
    """Render generated files and the manifest until the output stops changing."""
    contents = {path: read(root, path) for path in {*config["files"], *config["generated"]}}
    if (root / BOOTSTRAP).is_file():
        contents.setdefault(str(BOOTSTRAP), read(root, str(BOOTSTRAP)))
    for _ in range(5):
        manifest = build_manifest(config, contents)
        updated = dict(contents)
        for path in config["generated"]:
            updated[path] = render_file(path, contents[path], config, manifest, updated)
        if updated == contents:
            outputs = {path: contents[path] for path in config["generated"]}
            outputs[str(MANIFEST)] = json.dumps(manifest, indent=2) + "\n"
            return outputs
        contents = updated
    raise ReleaseError("generated blocks did not converge; a shipped file may embed its own digest")


def stale_paths(root: Path, outputs: dict[str, str]) -> list[str]:
    return [path for path, text in outputs.items()
            if not (root / path).is_file() or read(root, path) != text]


def report_pins(config: dict) -> None:
    pins = config["pins"]
    rows = [("uv", pins["uv"]), ("specify-cli", pins["specify-cli"]),
            *sorted(pins.get("actions", {}).items())]
    for name, pin in rows:
        age = (date.today() - date.fromisoformat(pin["reviewed"])).days
        note = f" REVIEW DUE ({age} days)" if age > REVIEW_DAYS else ""
        print(f"PIN {name} {pin['version']} reviewed {pin['reviewed']}{note}")


def check(root: Path) -> int:
    config = load_config(root)
    stale = stale_paths(root, build(root, config))
    for path in stale:
        print(f"STALE {path}: run `python .config/ai/tools/release.py update` and review the diff")
    report_pins(config)
    print(f"Release {config['release']}: {'stale' if stale else 'current'}")
    return 1 if stale else 0


def tagged_text(root: Path, release: str, path: str) -> str | None:
    """Return a file's content at an existing local release tag, or None if there is no such tag."""
    try:
        tags = subprocess.run(["git", "-C", str(root), "tag", "--list", release],
                              capture_output=True, text=True, check=False)
        if tags.returncode or not tags.stdout.strip():
            return None
        shown = subprocess.run(["git", "-C", str(root), "show", f"refs/tags/{release}:{path}"],
                               capture_output=True, check=False)
    except OSError:
        return None
    return shown.stdout.decode("utf-8") if shown.returncode == 0 else ""


def published_changes(root: Path, release: str, outputs: dict[str, str]) -> list[str]:
    """Paths whose published content would differ from what the existing release tag serves."""
    changed = []
    for path in (str(MANIFEST), str(BOOTSTRAP)):
        if path not in outputs and not (root / path).is_file():
            continue
        tagged = tagged_text(root, release, path)
        if tagged is None:
            return []
        current = outputs[path] if path in outputs else read(root, path)
        if tagged != current:
            changed.append(path)
    return changed


def update(root: Path, release: str | None) -> int:
    config = load_config(root)
    if release is not None:
        if RELEASE.fullmatch(release) is None:
            raise ReleaseError("--release must look like v1.2.3")
        config["release"] = release
        (root / CONFIG).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        config = load_config(root)
    outputs = build(root, config)
    changed = published_changes(root, config["release"], outputs)
    if changed:
        raise ReleaseError(f"{config['release']} is already tagged and {', '.join(changed)} would change. "
                           "Rerun with --release <new version>.")
    for path in stale_paths(root, outputs):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes(outputs[path].encode("utf-8"))
        print(f"UPDATED {path}")
    print(f"Release {config['release']}: current")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("update").add_argument("--release", help="new release ID, for example v0.5.1")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    try:
        if arguments.command == "check":
            return check(root)
        return update(root, arguments.release)
    except ReleaseError as exc:
        print(f"FishDev release: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
