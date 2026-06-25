from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INNO_SETUP = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
MUTATING_FLAGS = ("commit", "tag", "push", "publish_github")


def normalize_version(value: str) -> tuple[str, str]:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError("version must not be empty")
    if clean.lower().startswith("v"):
        return f"v{clean[1:]}", clean[1:]
    return f"v{clean}", clean


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_command(command: list[str], *, label: str, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n==> {label}")
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=ROOT, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {result.returncode}")
    return result


def run_capture(command: list[str], *, label: str, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n==> {label}")
    print("$ " + " ".join(command))
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    if check and result.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {result.returncode}")
    return result


def installer_path(version_with_v: str) -> Path:
    return ROOT / "installer" / f"MUG_Setup_{version_with_v}.exe"


def find_inno_setup(explicit_path: str | None) -> Path | None:
    if explicit_path:
        candidate = Path(explicit_path)
        return candidate if candidate.exists() else None

    if DEFAULT_INNO_SETUP.exists():
        return DEFAULT_INNO_SETUP

    discovered = shutil.which("ISCC.exe") or shutil.which("iscc.exe")
    return Path(discovered) if discovered else None


def extract_changelog_section(version_with_v: str) -> str:
    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    heading = f"## {version_with_v}"
    start = text.find(heading)
    if start < 0:
        raise ValueError(f"CHANGELOG.md does not contain {heading}")

    next_start = text.find("\n## ", start + len(heading))
    section = text[start:next_start if next_start >= 0 else len(text)]
    return section.strip()


def parse_changelog_groups(version_with_v: str) -> dict[str, list[str]]:
    section = extract_changelog_section(version_with_v)
    groups: dict[str, list[str]] = {}
    current_heading = ""

    for raw_line in section.splitlines()[1:]:
        line = raw_line.strip()
        if line.startswith("### "):
            current_heading = line[4:].strip()
            groups.setdefault(current_heading, [])
            continue
        if line.startswith("- ") and current_heading:
            groups.setdefault(current_heading, []).append(line)

    return groups


def first_available_group(groups: dict[str, list[str]], headings: tuple[str, ...]) -> list[str]:
    for heading in headings:
        items = groups.get(heading)
        if items:
            return items
    return []


def bullet_block(items: list[str]) -> str:
    return "\n".join(items) if items else "None."


def build_release_notes(version_with_v: str, checksum: str | None = None) -> str:
    groups = parse_changelog_groups(version_with_v)
    quality = first_available_group(groups, ("Quality and Infrastructure", "Infrastructure"))
    improvements = first_available_group(groups, ("Improvements",))
    tests = first_available_group(groups, ("Tests",))
    features = first_available_group(groups, ("New Features", "Features"))
    compatibility = first_available_group(groups, ("Compatibility",))

    if not tests:
        tests = [
            item for item in quality
            if any(keyword in item.lower() for keyword in ("test", "coverage", "smoke", "regression"))
        ]

    checksum_text = f"`{checksum}`" if checksum else "Not available yet."

    return "\n".join(
        [
            "## Release Description",
            "",
            (
                f"MUG {version_with_v} is an operational infrastructure release focused on "
                "safer release automation, update-check reliability and preparation for future "
                "architecture work."
            ),
            "",
            "## Main Features",
            "",
            bullet_block(features),
            "",
            "## Improvements",
            "",
            bullet_block(improvements),
            "",
            "## Infrastructure",
            "",
            bullet_block(quality),
            "",
            "## Tests",
            "",
            bullet_block(tests),
            "",
            "## Breaking Changes",
            "",
            "None.",
            "",
            "## Compatibility",
            "",
            bullet_block(compatibility),
            "",
            "## SHA256",
            "",
            checksum_text,
            "",
        ]
    )


def require_confirmation(args: argparse.Namespace) -> None:
    requested = [name for name in MUTATING_FLAGS if getattr(args, name)]
    if requested and not args.yes:
        joined = ", ".join(f"--{name.replace('_', '-')}" for name in requested)
        raise SystemExit(f"Refusing {joined} without --yes")
    if args.publish_github and args.skip_tests:
        raise SystemExit("Refusing --publish-github with --skip-tests")


def validate_release(version_with_v: str) -> None:
    run_command(
        [sys.executable, "scripts/validate_release.py", "--version", version_with_v],
        label=f"Validate release metadata for {version_with_v}",
    )


def run_tests() -> None:
    run_command(
        [sys.executable, "-m", "compileall", "app.py", "core", "ui", "tests", "benchmarks", "scripts", "-q"],
        label="Compile Python sources",
    )
    run_command(
        [sys.executable, "-m", "pytest", "tests", "-q", "--basetemp", str(ROOT / ".tmp_pytest"), "-p", "no:cacheprovider"],
        label="Run tests",
    )


def run_benchmark(version_with_v: str) -> None:
    run_command(
        [sys.executable, "benchmarks/benchmark_release.py", "--version", version_with_v],
        label=f"Run benchmark for {version_with_v}",
    )


def build_executable() -> None:
    run_command(["cmd", "/c", "build_exe.bat"], label="Build executable")


def build_installer(inno_setup: Path, version_with_v: str) -> None:
    exe_path = ROOT / "dist" / "MUG" / "MUG.exe"
    if not exe_path.exists():
        raise SystemExit("dist/MUG/MUG.exe does not exist. Run with --build first or build manually.")

    run_command([str(inno_setup), "installer_mug.iss"], label=f"Build installer for {version_with_v}")


def inspect_git_status() -> None:
    run_command(["git", "status", "--short", "--ignored"], label="Inspect git status", check=False)
    run_command(["git", "diff", "--stat"], label="Inspect git diff stat", check=False)


def commit_release(version_with_v: str) -> None:
    staged = run_capture(["git", "diff", "--cached", "--name-only"], label="Inspect staged files", check=False)
    if not staged.stdout.strip():
        raise SystemExit("--commit requires intended files to be staged first")
    run_command(["git", "commit", "-m", f"Release {version_with_v}"], label="Create release commit")


def tag_release(version_with_v: str) -> None:
    existing = run_capture(["git", "rev-parse", "--verify", "--quiet", version_with_v], label="Check existing tag", check=False)
    if existing.returncode == 0:
        raise SystemExit(f"Tag {version_with_v} already exists")
    run_command(["git", "tag", "-a", version_with_v, "-m", f"MUG {version_with_v}"], label="Create annotated tag")


def push_release(version_with_v: str) -> None:
    run_command(["git", "push", "origin", "main"], label="Push main")
    run_command(["git", "push", "origin", version_with_v], label=f"Push tag {version_with_v}")


def publish_github_release(version_with_v: str, notes: str, installer: Path) -> None:
    if not installer.exists():
        raise SystemExit(f"Cannot publish: installer not found at {installer}")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as handle:
        handle.write(notes)
        notes_path = Path(handle.name)

    try:
        view = run_capture(
            ["gh", "release", "view", version_with_v, "--repo", "pancotto/MUG", "--json", "url"],
            label="Check existing GitHub Release",
            check=False,
        )
        if view.returncode == 0:
            run_command(
                [
                    "gh", "release", "edit", version_with_v,
                    "--repo", "pancotto/MUG",
                    "--title", f"MUG {version_with_v}",
                    "--notes-file", str(notes_path),
                    "--draft=false",
                    "--prerelease=false",
                    "--latest",
                ],
                label="Update GitHub Release",
            )
            run_command(
                ["gh", "release", "upload", version_with_v, str(installer), "--repo", "pancotto/MUG", "--clobber"],
                label="Upload installer asset",
            )
        else:
            run_command(
                [
                    "gh", "release", "create", version_with_v, str(installer),
                    "--repo", "pancotto/MUG",
                    "--title", f"MUG {version_with_v}",
                    "--notes-file", str(notes_path),
                    "--verify-tag",
                    "--latest",
                ],
                label="Create GitHub Release",
            )
    finally:
        notes_path.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely orchestrate a MUG release.")
    parser.add_argument("--version", required=True, help="Release version, e.g. v1.4.1")
    parser.add_argument("--skip-tests", action="store_true", help="Skip compileall and pytest.")
    parser.add_argument("--skip-benchmark", action="store_true", help="Skip benchmark generation.")
    parser.add_argument("--build", action="store_true", help="Run build_exe.bat.")
    parser.add_argument("--installer", action="store_true", help="Build installer with Inno Setup CLI.")
    parser.add_argument("--inno", default=None, help="Path to ISCC.exe. Defaults to the standard Inno Setup path or PATH lookup.")
    parser.add_argument("--commit", action="store_true", help="Commit currently staged release files.")
    parser.add_argument("--tag", action="store_true", help="Create annotated release tag.")
    parser.add_argument("--push", action="store_true", help="Push main and the release tag.")
    parser.add_argument("--publish-github", action="store_true", help="Create or update the public GitHub Release.")
    parser.add_argument("--notes-file", default=None, help="Write generated release notes to this file.")
    parser.add_argument("--yes", action="store_true", help="Required for commit/tag/push/publish actions.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    version_with_v, _ = normalize_version(args.version)
    require_confirmation(args)

    print(f"MUG release orchestrator: {version_with_v}")
    print("Safe mode: commit/tag/push/publish require explicit flags plus --yes.")

    if not args.skip_tests:
        run_tests()
    else:
        print("\n==> Skipping tests by request")

    if not args.skip_benchmark:
        run_benchmark(version_with_v)
    else:
        print("\n==> Skipping benchmark by request")

    validate_release(version_with_v)

    if args.build:
        build_executable()
    else:
        print("\n==> Dry run: executable build not requested. Pass --build to run build_exe.bat.")

    if args.installer:
        inno_setup = find_inno_setup(args.inno)
        if inno_setup is None:
            raise SystemExit("Inno Setup CLI was not found. Install it or pass --inno <path-to-ISCC.exe>.")
        build_installer(inno_setup, version_with_v)
    else:
        print("\n==> Dry run: installer build not requested. Pass --installer to run Inno Setup.")

    validate_release(version_with_v)

    installer = installer_path(version_with_v)
    checksum = sha256_file(installer) if installer.exists() else None
    if checksum:
        print(f"\nInstaller: {installer}")
        print(f"SHA256: {checksum}")
    else:
        print(f"\nInstaller not found yet: {installer}")

    notes = build_release_notes(version_with_v, checksum)
    print("\n==> Generated release notes")
    print(notes)

    if args.notes_file:
        notes_path = Path(args.notes_file)
        notes_path.write_text(notes, encoding="utf-8")
        print(f"Release notes written to {notes_path}")

    inspect_git_status()

    if args.commit:
        commit_release(version_with_v)
    if args.tag:
        tag_release(version_with_v)
    if args.push:
        push_release(version_with_v)
    if args.publish_github:
        publish_github_release(version_with_v, notes, installer)

    print("\nRelease orchestration completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
