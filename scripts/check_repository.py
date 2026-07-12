from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_RELEASE_FILE_BYTES = 5 * 1024 * 1024
FORBIDDEN_SUFFIXES = {".key", ".pem", ".p12", ".tar", ".gz", ".zip"}


def tracked_paths() -> list[Path]:
    completed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def main() -> int:
    errors: list[str] = []
    required = ["requirements.lock", "requirements-dev.lock", "miniprogram/package-lock.json"]
    for relative in required:
        if not (ROOT / relative).is_file():
            errors.append(f"missing lock file: {relative}")

    for path in tracked_paths():
        relative = path.relative_to(ROOT)
        if not path.is_file() or str(relative).startswith(".codex/"):
            continue
        if path.stat().st_size > MAX_RELEASE_FILE_BYTES:
            errors.append(f"oversized tracked file: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden artifact or credential file: {relative}")
        if "node_modules" in relative.parts or "__pycache__" in relative.parts:
            errors.append(f"generated dependency/cache tracked: {relative}")
        if relative.name in {".env", ".env.test", ".env.prod"}:
            errors.append(f"runtime environment file tracked: {relative}")

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    if "@sha256:" not in dockerfile or "--require-hashes" not in dockerfile:
        errors.append("Dockerfile must pin its base image digest and enforce dependency hashes")
    for filename in ("requirements.txt", "requirements-dev.txt"):
        for line in (ROOT / filename).read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith(("#", "-r")) and not re.match(r"^[A-Za-z0-9_.-]+(?:\[[^]]+\])?==[^=]+$", value):
                errors.append(f"unpinned dependency in {filename}: {value}")

    if errors:
        print("repository release check failed")
        for error in errors:
            print(error)
        return 1
    print("repository release check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
