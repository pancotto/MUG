from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalize_version(value: str) -> tuple[str, str]:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError("version must not be empty")
    if clean.lower().startswith("v"):
        return f"v{clean[1:]}", clean[1:]
    return f"v{clean}", clean


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


class ReleaseValidator:
    def __init__(self, target_version: str, require_installer: bool = False):
        self.target_with_v, self.target_no_v = normalize_version(target_version)
        self.require_installer = require_installer
        self.failures: list[str] = []
        self.infos: list[str] = []

    def ok(self, message: str) -> None:
        self.infos.append(f"[OK] {message}")

    def info(self, message: str) -> None:
        self.infos.append(f"[INFO] {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        self.infos.append(f"[FAIL] {message}")

    def require_file(self, relative_path: str) -> Path | None:
        path = ROOT / relative_path
        if not path.exists():
            self.fail(f"{relative_path} does not exist")
            return None
        self.ok(f"{relative_path} exists")
        return path

    def require_contains(self, relative_path: str, needle: str, label: str) -> None:
        path = self.require_file(relative_path)
        if path is None:
            return
        text = read_text(path)
        if needle not in text:
            self.fail(f"{relative_path} does not contain {label}: {needle}")
            return
        self.ok(f"{relative_path} contains {label}: {needle}")

    def validate_version_files(self) -> None:
        version_file = self.require_file("VERSION")
        if version_file is not None:
            actual = read_text(version_file).strip()
            if actual != self.target_with_v:
                self.fail(
                    f"VERSION is {actual!r}, expected {self.target_with_v!r}"
                )
            else:
                self.ok(f"VERSION matches {self.target_with_v}")

        self.require_contains("README.md", self.target_with_v, "target version")
        self.require_contains("CHANGELOG.md", f"## {self.target_with_v}", "changelog heading")

        installer_path = self.require_file("installer_mug.iss")
        if installer_path is not None:
            installer_text = read_text(installer_path)
            expected_define = f'#define MyAppVersion "{self.target_no_v}"'
            if expected_define not in installer_text:
                self.fail(
                    "installer_mug.iss does not contain "
                    f"{expected_define}"
                )
            else:
                self.ok("installer_mug.iss version matches target")

    def validate_ui_fallback_versions(self) -> None:
        expected = self.target_no_v
        for relative_path in ("ui/input_page.py", "ui/graph_page.py"):
            path = self.require_file(relative_path)
            if path is None:
                continue
            text = read_text(path)
            match = re.search(r'APP_VERSION_FALLBACK\s*=\s*"([^"]+)"', text)
            if not match:
                self.fail(f"{relative_path} does not define APP_VERSION_FALLBACK")
                continue
            actual = match.group(1)
            if actual != expected:
                self.fail(
                    f"{relative_path} fallback is {actual!r}, expected {expected!r}"
                )
            else:
                self.ok(f"{relative_path} fallback matches {expected}")

    def validate_duplicate_display(self) -> None:
        duplicated = f"vv{self.target_no_v}"
        search_paths = [
            "README.md",
            "CHANGELOG.md",
            "installer_mug.iss",
            "core",
            "ui",
            "scripts",
            "benchmarks",
            "tests",
        ]
        offenders: list[str] = []
        for relative_path in search_paths:
            path = ROOT / relative_path
            if not path.exists():
                continue
            files = [path] if path.is_file() else path.rglob("*")
            for file_path in files:
                if not file_path.is_file() or file_path.suffix.lower() not in {
                    ".py",
                    ".md",
                    ".iss",
                    ".bat",
                    ".txt",
                    ".json",
                }:
                    continue
                try:
                    if duplicated in read_text(file_path):
                        offenders.append(str(file_path.relative_to(ROOT)))
                except UnicodeDecodeError:
                    continue

        if offenders:
            self.fail(
                f"duplicated display token {duplicated!r} found in: "
                + ", ".join(offenders)
            )
        else:
            self.ok(f"no duplicated display token {duplicated!r} found")

    def validate_installer_artifact(self) -> None:
        expected_name = f"MUG_Setup_{self.target_with_v}.exe"
        expected_path = ROOT / "installer" / expected_name
        self.ok(f"expected installer name is {expected_name}")

        if expected_path.exists():
            self.info(f"{expected_name} exists")
            self.info(f"{expected_name} size: {expected_path.stat().st_size} bytes")
            self.info(f"SHA256 {expected_name}: {sha256_file(expected_path)}")
        else:
            message = f"{expected_name} does not exist yet"
            if self.require_installer:
                installer_dir = ROOT / "installer"
                existing_installers = sorted(
                    path.name
                    for path in installer_dir.glob("MUG_Setup_v*.exe")
                    if path.is_file()
                ) if installer_dir.exists() else []
                if existing_installers:
                    message += "; found installer artifacts: " + ", ".join(existing_installers)
                self.fail(message)
            else:
                self.info(message)

    def validate_benchmark_latest(self) -> None:
        latest_md = ROOT / "docs" / "benchmarks" / "latest.md"
        latest_json = ROOT / "docs" / "benchmarks" / "latest.json"

        if latest_md.exists():
            text = read_text(latest_md)
            if self.target_with_v not in text:
                self.fail("docs/benchmarks/latest.md does not point to current version")
            else:
                self.ok("docs/benchmarks/latest.md points to current version")

        if latest_json.exists():
            try:
                data = json.loads(read_text(latest_json))
            except json.JSONDecodeError as exc:
                self.fail(f"docs/benchmarks/latest.json is invalid JSON: {exc}")
                return

            candidates = {
                str(data.get("run_id", "")),
                str(data.get("version", "")),
                str(data.get("release", "")),
            }
            if self.target_with_v not in candidates:
                self.fail(
                    "docs/benchmarks/latest.json does not point to current version"
                )
            else:
                self.ok("docs/benchmarks/latest.json points to current version")

    def validate_build_inputs(self) -> None:
        self.require_file("build_exe.bat")
        self.require_file("MUG.spec")

        git_dir = ROOT / ".git"
        if git_dir.exists():
            result = subprocess.run(
                ["git", "check-ignore", "-q", "MUG.spec"],
                cwd=ROOT,
                check=False,
            )
            if result.returncode == 0:
                self.fail("MUG.spec is still ignored by git")
            elif result.returncode == 1:
                self.ok("MUG.spec is not ignored by git")
            else:
                self.info("could not verify git ignore status for MUG.spec")

    def run(self) -> int:
        self.validate_version_files()
        self.validate_ui_fallback_versions()
        self.validate_duplicate_display()
        self.validate_installer_artifact()
        self.validate_benchmark_latest()
        self.validate_build_inputs()

        for line in self.infos:
            print(line)

        if self.failures:
            print()
            print("Release validation failed:")
            for failure in self.failures:
                print(f"- {failure}")
            return 1

        print()
        print(f"Release validation passed for {self.target_with_v}.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MUG release metadata.")
    parser.add_argument("--version", required=True, help="Target release version, e.g. v1.4.0")
    parser.add_argument(
        "--require-installer",
        action="store_true",
        help="Fail unless the expected installer artifact exists.",
    )
    args = parser.parse_args(argv)

    validator = ReleaseValidator(
        args.version,
        require_installer=args.require_installer,
    )
    return validator.run()


if __name__ == "__main__":
    raise SystemExit(main())
