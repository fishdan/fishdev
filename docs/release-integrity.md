# Release integrity: pinned and verified downloads

Every FishDev installation path downloads one fixed release and checks it before using it. This page explains what is pinned, how to verify an install yourself, what the checks do and do not protect against, and how maintainers update pins and cut a release.

## What is pinned

| Download | Pinned to | Verified by |
| --- | --- | --- |
| `install.sh` (bootstrap) | A release tag | You, using the SHA-256 digest in the README command |
| FishDev workflow files | The same release tag | `install.sh` or the Windows guide, against digests embedded for that release |
| uv | A uv release version | SHA-256 of uv's versioned installer. The Linux and macOS installer then checks the uv archive. |
| SpecKit (`specify-cli`) | One PyPI release | SHA-256 of the wheel, installed from the local file |
| GitHub Actions in FishDev's CI | A full commit SHA | Git: a commit SHA identifies exactly one commit |

All pins live in one hand-edited file, [`.config/ai/release.json`](../.config/ai/release.json). The commands in the README, `install.sh`, `fishdev-init.md`, the [Windows guide](windows-vscode-powershell.md), and the CI workflow are generated from it. `.config/ai/release-manifest.json` lists each shipped FishDev file and its digest for the current release.

## Install and verify

Use the commands in the [README](../README.md). They download `install.sh` from the release tag, compare its SHA-256 digest with the one printed in the command, and run it only if they match.

The installer then:

1. Stops if `start.ai`, `.config/ai`, or `.specify` already exists. It sets up new projects only and never overwrites an existing FishDev or SpecKit installation.
2. Stops if neither `sha256sum` nor `shasum` is available.
3. Downloads every FishDev file to a temporary folder and checks each digest. Any mismatch, missing file, or failed transfer stops the install. The project is left unchanged and the temporary folder is removed.
4. Keeps an existing uv if it is version 0.4.0 or newer. Otherwise it downloads the pinned uv installer, checks its digest, and only then runs it.
5. Downloads the pinned SpecKit wheel, checks its digest, and installs it with `uv tool install`. If SpecKit is already installed at the pinned version, it is kept. If a different version is installed, the installer says so and replaces it.
6. Writes the FishDev files and initializes SpecKit. `specify init` uses files bundled in the wheel and does not download anything.

Every failure message names the file or URL, and a digest mismatch shows both the expected and the actual digest. Nothing in the installer skips a failed check.

On Windows, the [setup guide](windows-vscode-powershell.md) follows the same steps with `Get-FileHash`.

## What this protects against, and what it does not

It protects against:

- Upstream changes between installs. Two installs of the same release get the same bytes, or the install fails.
- Tampering or corruption in transit or in caches, including truncated downloads.
- A moved Git tag, since digests, not tags, decide what is accepted.
- Half-finished installs after a download failure.

It does **not** protect against:

- **Compromise of the FishDev repository or maintainer account.** The digests are published from the same repository as the files they describe. Anyone who can change both can change what a new install accepts. Release signing would address this and is a candidate follow-up.
- **Skipping the bootstrap check.** If you download `install.sh` and run it without comparing its digest, the transport is your only protection for that first file.
- **SpecKit's dependencies.** The SpecKit wheel is verified, but uv resolves its Python dependencies from PyPI by version range. uv does not enforce hashes from a constraints file for `uv tool install`, so FishDev does not pin them. PyPI does not allow an uploaded file to be replaced, which limits but does not remove this risk.
- **uv's Windows archive.** uv's PowerShell installer does not check the archive it downloads. On Windows that step relies on HTTPS and the versioned release URL. uv checks managed Python downloads itself.
- **Vulnerabilities in pinned versions.** A pin keeps a version fixed, including its bugs. The monthly security audit in `start.ai` reviews every pin.

## Maintainers: update a pin

1. Work on a SpecKit spec branch, as for any change.
2. Pick the newest upstream release that is at least 7 days old. This cooldown reduces exposure to a freshly compromised or broken release.
3. Compute digests from downloads you have reviewed. For example, fetch the uv installer or SpecKit wheel to a scratch folder and run `sha256sum` on it. For an action, resolve the tag with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` and record the commit SHA. If the tag object type is `tag` rather than `commit`, dereference it first.
4. Edit `.config/ai/release.json`: update the version, URL, digest or commit, source, and `reviewed` date.
5. Run `python .config/ai/tools/release.py update --release <new release>`, review the regenerated blocks, and run `python .config/ai/tools/fishdev.py verify`.

## Maintainers: cut a release

A release ID (for example `v0.5.1`) must change whenever a shipped file, `install.sh`, or a pin changes. `release.py update` refuses to change the published manifest or `install.sh` under a release ID that already has a local tag.

1. In the pull request that changes anything shipped, run `python .config/ai/tools/release.py update --release <new release>` and commit the result.
2. After merging, tag the merge commit and push the tag right away. Until the tag exists, the README command fails because it cannot download the installer.

   ```sh
   git tag <new release> <merge commit>
   git push origin <new release>
   ```

3. Test from a clean empty directory by running the README command, and record the outcome in `.config/ai/progress.ai`.

## Checks that keep this honest

- `release.py check` runs in `fishdev.py verify` locally and in CI. It fails if a shipped file, the manifest, or any generated block no longer matches `release.json`, and it prints every pin with its review date (`REVIEW DUE` after 31 days).
- Rule `SEC-001` in `.config/ai/rules.json` fails `fishdev.py check` when the installer, setup documents, or CI workflows pipe a download into a shell, fetch from a branch head, install an unversioned uv or SpecKit, or reference an action without a commit SHA.
- `.gitattributes` fixes line endings for shipped files, so a Windows checkout computes the same digests that GitHub serves.
